"""
群日常分析指令处理器 (Analysis Command Handler)
处理 /群分析 指令触发、权限前置判定、跨平台分析生命周期、报告渲染与群文件/相册分发。
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import tempfile
import time
from contextlib import nullcontext
from datetime import datetime
from inspect import isawaitable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast
from urllib.parse import quote

# File is only available via astrbot.core (internal API — may change).
from astrbot.core.message.components import File

from ...domain.repositories.platform_adapter_repository import (
    GroupAlbumSupportProtocol,
    GroupFileSupportProtocol,
    PlatformAdapterProtocol,
)
from ...domain.value_objects.task_event import TaskEvent
from ...infrastructure.reporting.html_renderer import bind_group_html_renderer
from ...shared.constants import PLUGIN_NAME, AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..services.analysis_application_service import (
    AnalysisApplicationService,
    DuplicateGroupTaskError,
)
from ..services.stop_request import StopRequest

STOP_GRACE_SECONDS = 5.0
"""取消子任务后等待其退出的上限；超时仍继续收尾，避免 handler 无限挂住。"""

T = TypeVar("T")


def _consume_orphan_task_exception(task: asyncio.Task[object]) -> None:
    """取回孤儿任务的异常。

    宽限期结束后仍未退出的子任务会被放弃等待，若它随后以异常结束，
    没有回调取回就会由事件循环打印 Task exception was never retrieved。

    Args:
        task: 被放弃等待的后台任务。
    """
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning(f"孤儿前台任务结束后抛出异常（已取回）: {error!r}")


class AnalysisStoppedError(BaseException):
    """用户通过宿主 /stop 中止了前台分析。

    继承 BaseException 是刻意的：这是控制流信号而非错误，必须穿过各处
    ``except Exception``（渲染失败回退、发送兜底）继续上抛，否则停止会被
    当成渲染失败吞掉，用户按了停止仍会收到报告。
    """


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from astrbot.api.event import AstrMessageEvent, MessageEventResult

    from ...domain.repositories.plugin_host_repository import PluginHostProtocol
    from ...domain.value_objects import AnalysisResultPayload
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.messaging.message_sender import MessageSender
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ...infrastructure.platform.bot_manager import BotManager
    from ...infrastructure.reporting.generators import ReportGenerator
    from ...infrastructure.webui.active_task_manager import ActiveTaskManager
    from ..services.stop_request import StopWatcher
    from .comic_command_handler import ComicCommandHandler


class AnalysisCommandHandler:
    """日常分析指令应用层处理器。"""

    config_manager: ConfigManager
    bot_manager: BotManager
    analysis_service: AnalysisApplicationService
    report_generator: ReportGenerator
    html_render: Callable
    active_task_manager: ActiveTaskManager | None
    trace_store: TraceSQLiteStore | None
    message_sender: MessageSender | None
    comic_handler: ComicCommandHandler | None
    plugin_data_dir: Path
    plugin_instance: PluginHostProtocol | None
    terminating: bool

    def __init__(
        self,
        config_manager: ConfigManager,
        bot_manager: BotManager,
        analysis_service: AnalysisApplicationService,
        report_generator: ReportGenerator,
        html_render: Callable,
        active_task_manager: ActiveTaskManager | None = None,
        trace_store: TraceSQLiteStore | None = None,
        message_sender: MessageSender | None = None,
        comic_handler: ComicCommandHandler | None = None,
        plugin_data_dir: Path | None = None,
        plugin_instance: PluginHostProtocol | None = None,
        stop_watcher_factory: Callable[[AstrMessageEvent], StopWatcher] | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.analysis_service = analysis_service
        self.report_generator = report_generator
        self.html_render = html_render
        self.active_task_manager = active_task_manager
        self.trace_store = trace_store
        self.message_sender = message_sender
        self.comic_handler = comic_handler
        self.plugin_data_dir = (
            plugin_data_dir or Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME
        )
        self.plugin_instance = plugin_instance
        self.stop_watcher_factory = stop_watcher_factory
        self.terminating: bool = False

    def set_terminating(self, terminating: bool) -> None:
        self.terminating = terminating

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str:
        try:
            return event.get_platform_id()
        except Exception:
            if (
                hasattr(event, "platform_meta")
                and event.platform_meta
                and hasattr(event.platform_meta, "id")
            ):
                return event.platform_meta.id
            return "default"

    async def handle_daily_analysis(
        self, event: AstrMessageEvent, days: int | None = None
    ) -> AsyncGenerator[MessageEventResult]:
        """处理 /群分析 核心指令流程。

        Args:
            event: AstrBot 消息事件对象。
            days: 分析回溯天数（可选）。

        Returns:
            AsyncGenerator[object, None]: 指令响应消息生成器。
        """
        if self.terminating:
            return

        current_task = asyncio.current_task()
        trace = None
        trace_id = ""
        group_id: str | None = None
        task_finalized = False
        stop_watcher: StopWatcher | None = None
        stop_request = StopRequest()

        try:
            event.should_call_llm(True)
            group_id = self._get_group_id_from_event(event)
            platform_id = self._get_platform_id_from_event(event)

            if not group_id:
                yield event.plain_result("❌ 请在群聊中使用此命令")
                return

            self.bot_manager.update_from_event(event)

            check_target = (
                event.unified_msg_origin or f"{platform_id}:GroupMessage:{group_id}"
            )

            if not self.config_manager.is_group_allowed(check_target):
                yield event.plain_result("❌ 此群未启用日常分析功能")
                return

            if self.analysis_service.is_group_running(group_id, "daily"):
                yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
                return

            # 在第一个准备阶段等待前开始监听；只取消工作子任务，保留宿主发送与收尾。
            if self.stop_watcher_factory is not None:
                stop_watcher = self.stop_watcher_factory(event)
                stop_request = stop_watcher.stop_request
                await stop_watcher.start()

            group_name = ""
            try:
                adapter = self.bot_manager.get_adapter(platform_id)
                if adapter:
                    info = await self._await_with_stop(
                        adapter.get_group_info(group_id), stop_request
                    )
                    if info and info.group_name:
                        group_name = info.group_name
            except Exception:
                pass

            trace_id = TraceContext.generate(
                prefix="manual", group_name=group_name or group_id
            )
            trace = await TraceContext.set_async(
                trace_id=trace_id,
                group_id=group_id,
                group_name=group_name,
                platform=platform_id or "",
                trigger_type="manual",
            )
            if self.active_task_manager:
                await self._await_with_stop(
                    self.active_task_manager.register_task(
                        task_id=trace_id,
                        group_id=group_id,
                        group_name=group_name,
                        platform=platform_id or "",
                        trigger_type="manual",
                        current_stage=AnalysisStage.FETCH_MESSAGES,
                        asyncio_task=current_task,
                    ),
                    stop_request,
                )

            adapter = self.bot_manager.get_adapter(platform_id)
            orig_msg_id = getattr(event.message_obj, "message_id", None)
            adapter_platform_name = (
                (adapter.get_platform_name() if adapter else "").strip().lower()
            )
            use_text_reply = (
                adapter_platform_name in {"qq_official", "qq_official_webhook"}
                or self.config_manager.get_enable_analysis_reply()
            )

            if use_text_reply:
                yield event.plain_result("🔍 正在启动分析引擎，正在拉取最近消息...")
            elif adapter and orig_msg_id:
                await self._await_with_stop(
                    adapter.set_reaction(
                        event.get_group_id(), orig_msg_id, "analysis_started"
                    ),
                    stop_request,
                )

            result = await self._await_with_stop(
                self.analysis_service.execute_daily_analysis(
                    group_id=group_id, platform_id=platform_id, manual=True, days=days
                ),
                stop_request,
            )

            if not result.get("success"):
                reason = result.get("reason")
                if trace and trace.status == "running":
                    err_msg = (
                        str(result.get("error"))
                        if result.get("error")
                        else f"Analysis skipped/failed: {reason}"
                    )
                    await asyncio.to_thread(
                        trace.finish,
                        event=TaskEvent.FAIL,
                        error_message=err_msg,
                    )
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到足够的群聊记录")
                elif reason == "llm_analysis_failed":
                    yield event.plain_result(
                        "❌ 大模型文本分析失败：所有已开启的分析模块均调用失败或重试耗尽（请检查大模型 API Key 及服务商连通性）"
                    )
                elif reason == "muted":
                    logger.warning(
                        f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过回复以防抛出发送异常"
                    )
                else:
                    yield event.plain_result(
                        f"❌ 分析失败: {result.get('error', '原因未知')}"
                    )
                return

            if not use_text_reply and adapter and orig_msg_id:
                await self._await_with_stop(
                    adapter.set_reaction(
                        event.get_group_id(), orig_msg_id, "analysis_done"
                    ),
                    stop_request,
                )

            if self.active_task_manager:
                await self._await_with_stop(
                    self.active_task_manager.update_stage(trace_id, "RENDER_REPORT"),
                    stop_request,
                )

            async for res in self.send_analysis_report(event, result, stop_request):
                yield res

            if stop_request.refresh():
                raise AnalysisStoppedError

            if trace and trace.status == "running":
                (await asyncio.to_thread(trace.finish, event=TaskEvent.SUCCEED))

        except AnalysisStoppedError:
            if stop_watcher is not None:
                await stop_watcher.stop()
            await self._finalize_stopped_analysis(trace_id, trace, group_id)
            task_finalized = True
            return
        except DuplicateGroupTaskError:
            if trace and trace.status == "running":
                await asyncio.to_thread(
                    trace.finish,
                    event=TaskEvent.ABORT,
                    error_message="Task already running in group",
                )
            yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
        except asyncio.CancelledError:
            if trace and trace.status == "running":
                try:
                    await asyncio.to_thread(
                        trace.finish,
                        event=TaskEvent.ABORT,
                        error_message="Task cancelled by system",
                    )
                except RuntimeError as transition_error:
                    logger.info(f"取消收尾时任务已由并发事件收敛: {transition_error}")
            logger.info("群分析任务被取消 (插件重载或卸载)")
        except Exception as e:
            if trace and trace.status == "running":
                await asyncio.to_thread(
                    trace.finish, event=TaskEvent.FAIL, error_message=str(e)
                )
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {e!s}。请检查网络连接和LLM配置，或联系管理员"
            )
        finally:
            # 收尾路径全部用同步或单次 await，避免二次取消跳过后续清理。
            if stop_watcher is not None:
                stop_watcher.stop_now()
            if not task_finalized and trace_id and self.active_task_manager:
                try:
                    await self.active_task_manager.finish_task(trace_id)
                except asyncio.CancelledError:
                    logger.warning("收尾时被二次取消，活跃任务记录可能残留")
                    raise

    async def _await_with_stop(
        self, awaitable: Coroutine[object, object, T], stop_request: StopRequest | None
    ) -> T:
        """等待协程的同时监听宿主停止请求。

        命中停止时取消协程并等待其退出（最长 STOP_GRACE_SECONDS），随后抛出
        AnalysisStoppedError，由调用链统一收尾。分析与渲染都走这里，避免渲染
        这类几十秒的长请求成为不可中断的盲区。

        Args:
            awaitable: 需要执行的前台工作协程。
            stop_request: 停止请求；为 None 时退化为普通 await。

        Returns:
            协程的返回值。

        Raises:
            AnalysisStoppedError: 宿主请求停止。
        """
        if stop_request is None:
            return await awaitable
        if stop_request.refresh():
            awaitable.close()
            raise AnalysisStoppedError

        work = asyncio.create_task(awaitable)
        stop_task = asyncio.create_task(stop_request.wait())
        try:
            done, _ = await asyncio.wait(
                {work, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            # 宿主取消（插件重载/卸载）时也要收掉子任务，避免群锁被泄漏。
            await self._stop_work(work)
            raise
        finally:
            if not stop_task.done():
                stop_task.cancel()

        if stop_request.refresh():
            # 停止与完成同时到：用户按了停止就丢弃这次结果，不再进入保存与发送。
            await self._stop_work(work)
            raise AnalysisStoppedError

        if work in done:
            if work.cancelled():
                raise RuntimeError("分析子任务被内部取消")
            return work.result()

        await self._stop_work(work)
        raise AnalysisStoppedError

    async def _stop_work(self, work: asyncio.Task[object]) -> None:
        """取消子任务并等它退出，超时则放弃等待并接管其异常。

        Args:
            work: 需要终止的前台工作子任务。

        Returns:
            None

        Raises:
            asyncio.CancelledError: 等待期间宿主再次取消当前任务。
        """
        if work.done():
            _consume_orphan_task_exception(work)
            return
        work.cancel()
        try:
            exited, _ = await asyncio.wait({work}, timeout=STOP_GRACE_SECONDS)
            if work not in exited:
                logger.error(
                    f"前台任务在取消后 {STOP_GRACE_SECONDS}s 内未退出，继续收尾"
                )
        finally:
            # 即使宽限期等待被二次取消，也必须接管子任务的后续异常。
            if work.done():
                _consume_orphan_task_exception(work)
            else:
                work.add_done_callback(_consume_orphan_task_exception)

    async def _finalize_stopped_analysis(
        self, trace_id: str, trace: TraceContext | None, group_id: str | None
    ) -> None:
        """收尾被用户停止的分析任务。

        先收敛已创建的 Trace，再移除活跃任务记录；准备阶段可能尚未创建 Trace。
        群锁仍由实际工作子任务退出时释放，停止回执由宿主负责。

        Args:
            trace_id: 本次分析的链路追踪 ID。
            trace: 当前链路追踪对象，未建立时为空。
            group_id: 群号，仅用于日志。
        """
        if trace is not None and trace.status == "running":
            try:
                await asyncio.to_thread(
                    trace.finish,
                    event=TaskEvent.CANCEL,
                    error_message="用户通过 stop 中止了本次分析",
                )
            except RuntimeError as transition_error:
                logger.info(f"停止收尾时任务已由并发事件收敛: {transition_error}")
        if trace_id and self.active_task_manager:
            await self.active_task_manager.finish_task(trace_id)
        logger.info(f"群 {group_id} 的群分析被用户停止 (宿主 /stop)")

    async def send_analysis_report(
        self,
        event: AstrMessageEvent,
        result: dict[str, object],
        stop_request: StopRequest | None = None,
    ) -> AsyncGenerator[MessageEventResult]:
        """处理分析结果的渲染和发送。

        Args:
            event: AstrBot 消息事件对象。
            result: 分析服务产出的结果字典。
            stop_request: 本次手动分析的停止请求；为 None 时不监听宿主停止。

        Returns:
            AsyncGenerator[object, None]: 结果消息生成器。
        """
        if self.terminating or not self.config_manager:
            logger.warning("插件正在关闭，停止发送报告")
            return
        if stop_request is not None and stop_request.refresh():
            raise AnalysisStoppedError

        group_id = str(result.get("group_id", ""))
        platform_id = str(result["platform_id"]) if result.get("platform_id") else None
        raw_analysis = result.get("analysis_result")
        analysis_result = cast(
            "AnalysisResultPayload",
            raw_analysis if isinstance(raw_analysis, dict) else {},
        )
        raw_adapter = result.get("adapter")
        adapter = cast("PlatformAdapterProtocol | None", raw_adapter)

        if not adapter:
            logger.warning(f"群 {group_id} 未找到对应的平台适配器，无法发送报告")
            return

        comic_handler = self.comic_handler or (
            self.plugin_instance.comic_command_handler if self.plugin_instance else None
        )
        if comic_handler:
            if stop_request is None:
                comic_handler.try_trigger_comic_generation(
                    group_id, platform_id, analysis_result
                )
            else:
                comic_handler.try_trigger_comic_generation(
                    group_id, platform_id, analysis_result, stop_request=stop_request
                )

        output_format_list = self.config_manager.get_output_format()
        output_format = output_format_list[0] if output_format_list else "image"
        is_qq_official = adapter.get_platform_name() in {
            "qq_official",
            "qq_official_webhook",
        }

        async def avatar_url_getter(
            user_id: str, avatar_size: int | None = None
        ) -> str | None:
            return await adapter.get_user_avatar_url(user_id, size=avatar_size or 40)

        async def nickname_getter(user_id: str) -> str | None:
            try:
                member = await adapter.get_member_info(group_id, user_id)
                if member:
                    return member.card or member.nickname
            except Exception:
                pass
            return None

        trace = TraceContext.current()
        override_theme = trace.metadata.get("override_template_name") if trace else None
        tpl_getter = getattr(self.config_manager, "get_report_template", None)
        raw_theme = override_theme or (
            tpl_getter() if callable(tpl_getter) else "default"
        )
        template_theme = str(raw_theme) if raw_theme else "default"

        if output_format == "image":
            html_render = bind_group_html_renderer(
                self.html_render, group_id, platform_id
            )
            async with (
                trace.span_async(
                    "RENDER_REPORT",
                    {"format": "image", "template": template_theme},
                )
                if trace
                else nullcontext()
            ):
                (
                    image_url,
                    _html_content,
                ) = await self._await_with_stop(
                    self.report_generator.generate_image_report(
                        analysis_result,
                        group_id,
                        html_render,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                        template_theme=template_theme,
                    ),
                    stop_request,
                )

            if stop_request is not None and stop_request.refresh():
                raise AnalysisStoppedError

            if image_url:
                save_history = getattr(
                    self.plugin_instance, "_save_report_to_history", None
                )
                cur_tid = trace.trace_id if trace else None
                if callable(save_history):
                    try:
                        await asyncio.to_thread(
                            save_history, image_url, group_id, trace_id=cur_tid
                        )
                    except TypeError:
                        await asyncio.to_thread(save_history, image_url, group_id)
                else:
                    await asyncio.to_thread(
                        self._save_report_to_history,
                        image_url,
                        group_id,
                        trace_id=cur_tid,
                    )

                caption = (
                    TraceContext.make_report_caption()
                    if self.config_manager.get_show_report_caption()
                    else ""
                )
                sent = await adapter.send_image(group_id, image_url, caption=caption)
                if sent:
                    if stop_request is not None and stop_request.refresh():
                        raise AnalysisStoppedError
                    upload_img = getattr(
                        self.plugin_instance, "_try_upload_image", None
                    )
                    if callable(upload_img):
                        res = upload_img(group_id, image_url, platform_id)
                        if isawaitable(res):
                            await res
                    else:
                        await self._try_upload_image(group_id, image_url, platform_id)
                    return

            logger.warning(f"图片报告发送失败，正在发送文本回退报告。群: {group_id}")

        if output_format == "html":
            cur_trace_id = trace.trace_id if trace else None
            async with (
                trace.span_async(
                    "RENDER_REPORT",
                    {"format": "html", "template": template_theme},
                )
                if trace
                else nullcontext()
            ):
                (
                    html_path,
                    _json_path,
                ) = await self._await_with_stop(
                    self.report_generator.generate_html_report(
                        analysis_result,
                        group_id,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                        template_theme=template_theme,
                        trace_id=cur_trace_id,
                    ),
                    stop_request,
                )
            if stop_request is not None and stop_request.refresh():
                raise AnalysisStoppedError
            if html_path:
                is_only_url = self.config_manager.get_html_only_url()
                base_url = self.config_manager.get_html_base_url()
                should_send_file = True

                if is_only_url:
                    if base_url and base_url.strip():
                        html_output_dir = self.config_manager.get_html_output_dir()
                        if not html_output_dir:
                            html_output_dir = os.path.join(
                                str(self.plugin_data_dir),
                                "self_hosted_html_reports",
                            )

                        rel_path = os.path.relpath(html_path, html_output_dir)
                        url_path = rel_path.replace(os.sep, "/")
                        encoded_url_path = quote(url_path.lstrip("/"), safe="/")
                        report_url = f"{base_url.rstrip('/')}/{encoded_url_path}"

                        yield event.plain_result(
                            f"📊 今日群聊分析报告已生成：\n{report_url}"
                        )
                        should_send_file = False
                    else:
                        logger.warning(
                            f"手动触发群 {group_id} 开启了仅发送外链，但未配置 html_base_url，回退至发送文件。"
                        )

                if should_send_file:
                    caption = self.report_generator.build_html_caption(html_path)
                    sent = False
                    if self.message_sender:
                        sent = await self.message_sender.send_file(
                            group_id,
                            html_path,
                            caption=caption,
                            platform_id=platform_id,
                        )
                        if stop_request is not None and stop_request.refresh():
                            raise AnalysisStoppedError
                    elif isinstance(adapter, GroupFileSupportProtocol):
                        sent = await adapter.upload_group_file_to_folder(
                            group_id, html_path, filename=Path(html_path).name
                        )
                        if stop_request is not None and stop_request.refresh():
                            raise AnalysisStoppedError
                        if sent and caption:
                            await adapter.send_text(group_id, caption)

                    if not sent:
                        yield event.chain_result(
                            [File(name=Path(html_path).name, file=html_path)]
                        )
                        if caption:
                            if stop_request is not None and stop_request.refresh():
                                raise AnalysisStoppedError
                            yield event.plain_result(caption)
            else:
                yield event.plain_result("⚠️ HTML 生成失败。")

        else:
            await self._send_text_reports(
                group_id, analysis_result, is_qq_official, adapter, stop_request
            )

    async def _send_text_reports(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        is_qq_official: bool,
        adapter: PlatformAdapterProtocol,
        stop_request: StopRequest | None = None,
    ) -> None:
        """发送纯文本分析报告。

        Args:
            group_id: 目标群号。
            analysis_result: 分析结果字典。
            is_qq_official: 是否为 QQ 官方平台。
            adapter: 平台适配器。
            stop_request: 本次手动分析的停止请求；为 None 时沿用原有发送流程。
        """
        try:
            if stop_request is not None and stop_request.refresh():
                raise AnalysisStoppedError
            if is_qq_official and hasattr(
                self.report_generator, "generate_markdown_report"
            ):
                (
                    text_report,
                    fallback_report,
                ) = await self._await_with_stop(
                    self.report_generator.generate_markdown_report(
                        analysis_result,
                        bind_group_html_renderer(
                            self.html_render, group_id, adapter.platform_id
                        ),
                        mention_style="qq",
                    ),
                    stop_request,
                )
                if stop_request is not None and stop_request.refresh():
                    raise AnalysisStoppedError
                await adapter.send_text_report(
                    group_id, text_report, fallback_content=fallback_report
                )
                return

            text = self.report_generator.generate_text_report(analysis_result)
            if stop_request is not None and stop_request.refresh():
                raise AnalysisStoppedError
            if text and text.strip():
                await adapter.send_text_report(group_id, text)
        except Exception as e:
            logger.error(f"发送纯文本报告失败 (群 {group_id}): {e}", exc_info=True)

    def _save_report_to_history(
        self, image_url: str, group_id: str, trace_id: str | None = None
    ) -> Path | None:
        """将生成的图片报告副本保存到持久化 reports 目录并关联 Trace 链路。

        Args:
            image_url: 图片本地路径或 base64 URI。
            group_id: 目标群号。
            trace_id: 可选的关联链路 TraceID。

        Returns:
            生成的报告文件 Path 对象（若成功），否则返回 None。
        """
        try:
            reports_dir = self.plugin_data_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            cur_trace = TraceContext.current()
            eff_trace_id = trace_id or (cur_trace.trace_id if cur_trace else "")
            trace_suffix = f"_{eff_trace_id}" if eff_trace_id else ""
            dest = reports_dir / f"report_{group_id}_{ts_str}{trace_suffix}.jpg"
            if Path(image_url).exists():
                import shutil

                shutil.copy2(image_url, dest)
            elif image_url.startswith("base64://"):
                data = base64.b64decode(image_url[9:])
                dest.write_bytes(data)

            if cur_trace:
                rfiles = cur_trace.metadata.setdefault("report_files", [])
                if isinstance(rfiles, list) and not any(
                    isinstance(rf, dict) and rf.get("filename") == dest.name
                    for rf in rfiles
                ):
                    rfiles.append(
                        {
                            "filename": dest.name,
                            "path": str(dest.resolve()),
                            "format": "image",
                            "size_bytes": dest.stat().st_size if dest.exists() else 0,
                            "created_at": time.time(),
                        }
                    )
                try:
                    cur_trace.persist_snapshot()
                except Exception as e:
                    logger.warning(f"保存报告追踪快照失败: {e}")
            return dest
        except Exception as e:
            logger.warning(f"保存历史报告副本失败: {e}")
            return None

    async def _try_upload_image(
        self,
        group_id: str,
        image_url: str,
        platform_id: str | None,
        is_comic: bool = False,
    ) -> None:
        """尝试将图片报告上传到群文件和/或群相册。

        Args:
            group_id: 目标群号。
            image_url: 图片本地路径或 base64 URI。
            platform_id: 当前平台标识。
            is_comic: 是否为漫画图片。
        """
        enable_file = (
            self.config_manager.get_enable_group_file_upload()
            if not is_comic
            else False
        )
        enable_album = (
            self.config_manager.get_enable_comic_album_upload()
            if is_comic
            else self.config_manager.get_enable_group_album_upload()
        )

        if not enable_file and not enable_album:
            return

        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            return
        if enable_file and not isinstance(adapter, GroupFileSupportProtocol):
            enable_file = False
        if enable_album and not isinstance(adapter, GroupAlbumSupportProtocol):
            enable_album = False
        if not enable_file and not enable_album:
            return

        now = datetime.now()
        timestamp = now.strftime("%H%M")
        date_str = now.strftime("%Y-%m-%d")
        filename_stem = f"群分析报告_{group_id}_{date_str}_{timestamp}"
        try:
            group_info = await adapter.get_group_info(group_id)
            if group_info and group_info.group_name:
                safe_name = re.sub(r'[\\/:*?"<>|]', "", group_info.group_name).strip()
                if safe_name:
                    filename_stem = f"群分析报告_{safe_name}_{date_str}_{timestamp}"
        except Exception:
            pass

        image_file = None
        created_temp = False
        MAX_PAYLOAD_SIZE = 20 * 1024 * 1024

        try:
            data = None
            if image_url.startswith("base64://"):
                base64_str = image_url[len("base64://") :]
                if len(base64_str) * 3 / 4 > MAX_PAYLOAD_SIZE:
                    return
                data = base64.b64decode(base64_str)
            elif image_url.startswith("data:"):
                parts = image_url.split(",", 1)
                if len(parts) == 2:
                    if len(parts[1]) * 3 / 4 > MAX_PAYLOAD_SIZE:
                        return
                    data = base64.b64decode(parts[1])
            elif os.path.isfile(image_url):
                image_file = os.path.abspath(image_url)

            ext = (
                ".jpg"
                if (".jpg" in image_url.lower() or ".jpeg" in image_url.lower())
                else ".png"
            )
            nice_filename = f"{filename_stem}{ext}"

            if data and not image_file:
                fd, image_file = tempfile.mkstemp(suffix=ext, prefix="group_report_")
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                    created_temp = True
                except Exception:
                    os.close(fd)
                    raise

            if not image_file:
                return

            if enable_file and isinstance(adapter, GroupFileSupportProtocol):
                try:
                    folder_name = self.config_manager.get_group_file_folder()
                    folder_id = None
                    if folder_name:
                        folder_id = await adapter.find_or_create_folder(
                            group_id, folder_name
                        )
                    await adapter.upload_group_file_to_folder(
                        group_id=group_id,
                        file_path=image_file,
                        folder_id=folder_id,
                        filename=nice_filename,
                    )
                except Exception as e:
                    logger.warning(f"群文件上传失败 (群 {group_id}): {e}")

            if enable_album and isinstance(adapter, GroupAlbumSupportProtocol):
                try:
                    album_name = (
                        self.config_manager.get_comic_album_name()
                        if is_comic
                        else self.config_manager.get_group_album_name()
                    )
                    strict_mode = self.config_manager.get_group_album_strict_mode()
                    if not (strict_mode and not album_name):
                        album_id = None
                        if album_name:
                            album_id = await adapter.find_album_id(group_id, album_name)
                        await adapter.upload_group_album(
                            group_id=group_id,
                            image_path=image_file,
                            album_id=album_id,
                            album_name=album_name or "",
                            strict_mode=strict_mode,
                        )
                except Exception as e:
                    logger.warning(f"群相册上传失败 (群 {group_id}): {e}")
        except Exception as e:
            logger.warning(f"图片上传处理异常: {e}")
        finally:
            if created_temp and image_file and os.path.exists(image_file):
                try:
                    os.remove(image_file)
                except OSError:
                    pass
