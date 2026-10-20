"""限时收集本次任务的独立产物，并以一次合并转发投递。"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import unquote, urlparse

from ...shared.trace_context import TraceContext
from ...utils.logger import logger

if TYPE_CHECKING:
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.platform.bot_manager import BotManager


@dataclass(frozen=True)
class PreparedForwardMessage:
    """尚未投递的单个图文节点，成功回调仅在平台确认发送后执行。"""

    kind: Literal["report", "wordcloud", "comic"]
    text: str = ""
    image_url: str = ""
    after_send: Callable[[], Awaitable[None]] | None = None
    after_failure: Callable[[], Awaitable[None]] | None = None


ForwardProducer = Callable[[], Awaitable[list[PreparedForwardMessage]]]


class MergedForwardDeliveryService:
    """按任务隔离收集结果，超时取消准备工作，不拆成多条普通消息。"""

    def __init__(self, config_manager: ConfigManager, bot_manager: BotManager) -> None:
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self._cleanup_tasks: set[asyncio.Task[None]] = set()

    def enabled_for(
        self,
        platform_id: str | None,
        kind: Literal["report", "wordcloud", "comic"] | None = None,
    ) -> bool:
        """只为用户选中的产物及支持图文转发的平台启用合并发送。

        Args:
            platform_id: 目标平台实例。
            kind: 指定产物类型；留空时检查是否选择了任意类型。

        Returns:
            当前产物是否应通过合并转发投递。
        """
        selected = self.config_manager.get_merged_forward_types()
        if not selected or (kind is not None and kind not in selected):
            return False
        adapter = self.bot_manager.get_adapter(platform_id)
        return bool(adapter and adapter.capabilities.supports_forward_message)

    @staticmethod
    async def _image_source(source: str) -> str:
        """将本地图转为 Base64，避免协议端与 AstrBot 不共享文件系统。

        Args:
            source: 本地图片路径、URL 或 Base64 图片。

        Returns:
            OneBot 可直接接收的图片来源。

        Raises:
            OSError: 本地图片不存在或无法读取。
        """
        if source.startswith(("https://", "http://", "base64://")):
            return source
        if source.startswith("data:image/") and ";base64," in source:
            return "base64://" + source.split(";base64,", 1)[1]
        if source.startswith("file://"):
            parsed = urlparse(source)
            source = unquote(parsed.path)
            if parsed.netloc:
                source = f"//{parsed.netloc}{source}"
            elif len(source) > 2 and source[0] == "/" and source[2] == ":":
                source = source[1:]
        data = await asyncio.to_thread(Path(source).read_bytes)
        return "base64://" + base64.b64encode(data).decode("ascii")

    def _consume_task(self, task: asyncio.Task[list[PreparedForwardMessage]]) -> None:
        """收尾拒绝取消的准备协程，避免后台未读取异常。"""
        if not task.cancelled() and task.exception() is None:
            for message in task.result():
                if message.after_failure:
                    self._schedule_finish(message, False)

    def _schedule_finish(
        self, message: PreparedForwardMessage, sent: bool
    ) -> asyncio.Task[None]:
        """保留后处理任务引用，调用方取消时仍完成状态落库。"""
        cleanup = asyncio.create_task(self._finish(message, sent))
        self._cleanup_tasks.add(cleanup)
        cleanup.add_done_callback(self._cleanup_tasks.discard)
        return cleanup

    async def _cancel_preparations(
        self, tasks: set[asyncio.Task[list[PreparedForwardMessage]]]
    ) -> None:
        """有界取消，不让忽略取消的提供商拖住其他产物。"""
        for task in tasks:
            task.cancel()
            task.add_done_callback(self._consume_task)
        if tasks:
            await asyncio.wait(tasks, timeout=1.0)

    @staticmethod
    async def _finish(message: PreparedForwardMessage, sent: bool) -> None:
        """独立执行状态落库与附加归档，一项失败不影响其他项。"""
        callback = message.after_send if sent else message.after_failure
        if callback:
            try:
                async with asyncio.timeout(60):
                    await callback()
            except Exception as exc:
                logger.warning(f"合并转发后处理失败 ({message.kind})：{exc}")

    async def deliver(
        self,
        group_id: str,
        platform_id: str | None,
        producers: dict[str, ForwardProducer],
    ) -> set[str]:
        """并发准备并限时发送成功产物，即使只有一项也使用合并转发。

        Args:
            group_id: 目标群号。
            platform_id: 目标平台实例。
            producers: 当前任务各类产物的只准备函数，不得自行发送消息。

        Returns:
            平台确认成功发送的产物类型集合。
        """
        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter or not adapter.capabilities.supports_forward_message:
            return set()
        if not producers:
            return set()

        async def prepare(producer: ForwardProducer) -> list[PreparedForwardMessage]:
            return await producer()

        tasks = {
            name: asyncio.create_task(prepare(producer))
            for name, producer in producers.items()
        }
        pending = set(tasks.values())
        done: set[asyncio.Task[list[PreparedForwardMessage]]] = set()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.config_manager.get_merged_forward_timeout()
        messages: list[PreparedForwardMessage] = []
        finalizers: dict[int, asyncio.Task[None]] = {}
        consumed: set[asyncio.Task[list[PreparedForwardMessage]]] = set()

        def finish(message: PreparedForwardMessage, sent: bool) -> asyncio.Task[None]:
            """先同步登记终态，再等待后处理，避免回执成功与取消之间的竞态。"""
            key = id(message)
            if key not in finalizers:
                finalizers[key] = self._schedule_finish(message, sent)
            return finalizers[key]

        try:
            while pending and (remaining := deadline - loop.time()) > 0:
                trace = TraceContext.current()
                if trace:
                    trace.touch_heartbeat()
                completed, pending = await asyncio.wait(
                    pending, timeout=min(20, remaining)
                )
                done.update(completed)
            # 取消后的迟到结果由回调消费，不参与本次发送。
            consumed.update(pending)
            await self._cancel_preparations(pending)
            unavailable: list[str] = []
            for name, task in tasks.items():
                if task not in done or task.cancelled():
                    unavailable.append(name)
                    continue
                consumed.add(task)
                try:
                    messages.extend(task.result())
                except Exception as exc:
                    unavailable.append(name)
                    logger.warning(f"群 {group_id} 合并产物 {name} 生成失败：{exc}")

            nodes: list[dict] = []
            prepared: list[PreparedForwardMessage] = []
            titles = {
                "report": "📊 群聊分析报告",
                "wordcloud": "☁️ 群聊词云",
                "comic": "🎬 每日群漫画",
            }
            bot_id = adapter.bot_self_ids[0] if adapter.bot_self_ids else "10000"
            for message in messages:
                content: list[dict] = []
                if message.text:
                    content.append({"type": "text", "data": {"text": message.text}})
                if message.image_url:
                    try:
                        async with asyncio.timeout(15):
                            image_source = await self._image_source(message.image_url)
                        content.append(
                            {"type": "image", "data": {"file": image_source}}
                        )
                    except Exception as exc:
                        unavailable.append(message.kind)
                        logger.warning(
                            f"群 {group_id} 合并图片准备失败 ({message.kind})：{exc}"
                        )
                        await asyncio.shield(finish(message, False))
                        continue
                if content:
                    nodes.append(
                        {
                            "type": "node",
                            "data": {
                                "user_id": str(bot_id),
                                "nickname": titles[message.kind],
                                "content": content,
                            },
                        }
                    )
                    prepared.append(message)
                else:
                    await asyncio.shield(finish(message, False))
            if unavailable:
                logger.warning(
                    f"群 {group_id} 合并转发跳过失败或超时的产物：{', '.join(unavailable)}"
                )
                trace = TraceContext.current()
                if trace:
                    trace.metadata["has_warnings"] = True
                    trace.metadata["merged_forward_unavailable"] = unavailable
            if not nodes:
                return set()
            # 只调用一次；发送超时无法确定平台是否已入队，不自动拆分补发。
            try:
                async with asyncio.timeout(60):
                    sent = await adapter.send_forward_msg(group_id, nodes)
            except Exception as exc:
                logger.warning(f"群 {group_id} 合并转发失败，不自动重复投递：{exc}")
                sent = False
            await asyncio.gather(
                *(asyncio.shield(finish(message, bool(sent))) for message in prepared)
            )
            return {message.kind for message in prepared} if sent else set()
        except BaseException:
            await self._cancel_preparations(set(tasks.values()) - consumed)
            await asyncio.gather(
                *(asyncio.shield(finish(message, False)) for message in messages)
            )
            raise
