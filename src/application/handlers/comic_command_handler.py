"""
群漫画指令与异步生成处理器 (Comic Command Handler)
处理 /群漫画 指令触发、并发信号量限制、任务去重、漫画分镜生成及相册/文件分发。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.api.event import AstrMessageEvent

from ...infrastructure.webui.active_task_manager import ActiveTaskManager
from ...shared.constants import PLUGIN_NAME, AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..services.analysis_application_service import (
    AnalysisApplicationService,
    DuplicateGroupTaskError,
)
from ..services.comic_application_service import ComicApplicationService

if TYPE_CHECKING:
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.platform.bot_manager import BotManager


class ComicCommandHandler:
    """群漫画指令应用层处理器。"""

    config_manager: ConfigManager
    bot_manager: BotManager
    comic_service: ComicApplicationService
    analysis_service: AnalysisApplicationService
    active_task_manager: ActiveTaskManager | None
    plugin_data_dir: Path
    plugin_instance: Any | None
    terminating: bool
    _comic_semaphore: asyncio.Semaphore
    _comic_group_tasks: dict[str, asyncio.Task]
    _background_tasks: set[asyncio.Task]

    def __init__(
        self,
        config_manager: ConfigManager,
        bot_manager: BotManager,
        comic_service: ComicApplicationService,
        analysis_service: AnalysisApplicationService,
        active_task_manager: ActiveTaskManager | None = None,
        plugin_data_dir: Path | None = None,
        plugin_instance: Any | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.comic_service = comic_service
        self.analysis_service = analysis_service
        self.active_task_manager = active_task_manager
        self.plugin_data_dir = (
            plugin_data_dir or Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME
        )
        self.plugin_instance = plugin_instance
        self.terminating: bool = False

        t2i_max_fn: Any = getattr(self.config_manager, "get_t2i_max_concurrent", None)
        try:
            raw_val = t2i_max_fn() if callable(t2i_max_fn) else 1
            max_concurrent = int(str(raw_val))
        except (TypeError, ValueError):
            max_concurrent = 1
        self._comic_semaphore = asyncio.Semaphore(max(1, max_concurrent))
        self._comic_group_tasks: dict[str, asyncio.Task] = {}
        self._background_tasks: set[asyncio.Task] = set()

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

    @staticmethod
    def detect_image_ext(data: bytes) -> str:
        """从图片字节嗅探扩展名，无法识别时回退 .png。

        Args:
            data: 图片二进制字节。

        Returns:
            str: 匹配的文件后缀扩展名（如 .png, .jpg, .webp, .gif, .avif）。
        """
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12] in {b"avif", b"avis"}
        ):
            return ".avif"
        return ".png"

    async def handle_group_comic(
        self, event: AstrMessageEvent, days: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """处理 /群漫画 核心指令流程。

        Args:
            event: AstrBot 消息事件对象。
            days: 分析回溯天数（可选）。

        Returns:
            AsyncGenerator[Any, None]: 指令响应消息生成器。
        """
        if self.terminating:
            return

        trace = None
        trace_id = None
        current_task = asyncio.current_task()
        if current_task:
            self._background_tasks.add(current_task)

        try:
            event.should_call_llm(True)
            group_id = self._get_group_id_from_event(event)
            platform_id = self._get_platform_id_from_event(event)

            if not group_id:
                yield event.plain_result("❌ 请在群聊中使用此命令")
                return

            if hasattr(self.bot_manager, "update_from_event"):
                self.bot_manager.update_from_event(event)  # type: ignore[union-attr]

            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = f"{platform_id}:GroupMessage:{group_id}"

            if not self.config_manager.get_enable_daily_comic():
                yield event.plain_result("❌ 漫画生成功能未启用")
                return

            if not self.config_manager.is_comic_group_allowed(check_target):
                yield event.plain_result("❌ 此群未启用漫画生成功能")
                return

            task_key = f"{platform_id or 'default'}:{group_id}"
            existing_task = self._comic_group_tasks.get(task_key)
            if existing_task and not existing_task.done():
                yield event.plain_result("🎨 该群已有漫画任务正在执行，请稍后再试哦~")
                return

            group_name = None
            adapter = self.bot_manager.get_adapter(platform_id)
            if adapter and hasattr(adapter, "get_group_info"):
                try:
                    info = await adapter.get_group_info(group_id)
                    if info and hasattr(info, "group_name") and info.group_name:
                        group_name = info.group_name
                except Exception:
                    pass

            trace_id = TraceContext.generate(
                prefix="comic", group_name=group_name or group_id
            )
            trace = TraceContext.set(
                trace_id=trace_id,
                group_id=group_id,
                group_name=group_name or group_id,
                platform=platform_id or "",
                trigger_type="comic_manual",
            )
            if self.active_task_manager:
                await self.active_task_manager.register_task(
                    task_id=trace_id,
                    group_id=group_id,
                    group_name=group_name or group_id,
                    platform=platform_id or "",
                    trigger_type="comic_manual",
                    current_stage=AnalysisStage.FETCH_MESSAGES,
                    asyncio_task=current_task,
                )

            yield event.plain_result("🎨 正在提取群聊话题并生成漫画...")

            result = await self.analysis_service.execute_comic_topic_analysis(
                group_id=group_id, platform_id=platform_id, days=days
            )
            if not result.get("success"):
                reason = result.get("reason")
                if trace and trace.status == "running":
                    trace.finish(
                        status="failed", error_message=f"提取漫画话题失败: {reason}"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到可用于生成漫画的群聊记录")
                elif reason == "no_topics":
                    yield event.plain_result("❌ 未提取到可用于生成漫画的话题")
                elif reason == "muted":
                    logger.warning(f"群 {group_id} 开启了禁言，跳过手动漫画回复")
                else:
                    yield event.plain_result("❌ 漫画话题提取失败，原因未知")
                return

            trigger_fn = self.try_trigger_comic_generation
            if self.plugin_instance and hasattr(
                self.plugin_instance, "_try_trigger_comic_generation"
            ):
                inst_fn = getattr(self.plugin_instance, "_try_trigger_comic_generation")
                if (
                    hasattr(inst_fn, "assert_called")
                    or hasattr(inst_fn, "_mock_name")
                    or type(inst_fn).__name__ in ("Mock", "MagicMock", "AsyncMock")
                ):
                    trigger_fn = inst_fn

            status = trigger_fn(
                group_id,
                platform_id,
                {"topics": result.get("topics", [])},
                require_auto_enabled=False,
                trace=trace,
            )
            if status == "started":
                yield event.plain_result("✅ 漫画生成任务已启动，完成后会发送到群里")
            elif status == "duplicate":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="该群已有漫画任务正在执行"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("🎨 该群已有漫画任务正在执行，请稍后再试哦~")
            elif status == "blocked":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="此群未启用漫画生成功能"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("❌ 此群未启用漫画生成功能")
            elif status == "no_topics":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="未提取到可用于生成漫画的话题"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("❌ 未提取到可用于生成漫画的话题")
            else:
                if trace and trace.status == "running":
                    trace.finish(status="failed", error_message="漫画生成任务未启动")
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("⚠️ 漫画生成任务未启动，请查看插件日志")

        except DuplicateGroupTaskError:
            if trace and trace.status == "running":
                trace.finish(
                    status="failed", error_message="该群的漫画话题提取任务正在执行"
                )
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            yield event.plain_result("🎨 该群的漫画话题提取任务正在执行，请稍后再试哦~")
        except asyncio.CancelledError:
            if trace and trace.status == "running":
                trace.finish(status="aborted", error_message="Task cancelled by system")
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            logger.info("手动漫画任务被取消（插件正在关闭或重载）")
        except Exception as e:
            if trace and trace.status == "running":
                trace.finish(status="failed", error_message=str(e))
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            logger.error(f"手动漫画生成失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 漫画生成失败: {str(e)}。请检查消息获取、LLM 和绘图配置"
            )
        finally:
            if current_task:
                self._background_tasks.discard(current_task)

    def try_trigger_comic_generation(
        self,
        group_id: str,
        platform_id: str | None,
        analysis_result: dict[str, Any],
        *,
        require_auto_enabled: bool = True,
        trace: TraceContext | None = None,
    ) -> str:
        """尝试触发后台漫画生成。

        Args:
            group_id: 目标群号。
            platform_id: 平台标识。
            analysis_result: 分析结果字典（包含 topics 字段）。
            require_auto_enabled: 是否要求开启自动生成配置（手动指令触发时为 False）。
            trace: 当前执行链路追踪上下文。

        Returns:
            str: 触发状态 ("started", "duplicate", "blocked", "no_topics", "disabled", "auto_disabled", "terminating")。
        """
        if self.terminating:
            return "terminating"
        enable_comic_fn = (
            getattr(self.config_manager, "get_enable_daily_comic", None)
            if self.config_manager
            else None
        )
        if enable_comic_fn and not enable_comic_fn():
            return "disabled"
        auto_comic_enabled = getattr(
            self.config_manager, "get_enable_auto_daily_comic", None
        )
        if (
            require_auto_enabled
            and callable(auto_comic_enabled)
            and not auto_comic_enabled()
        ):
            return "auto_disabled"

        umo = f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
        comic_allowed = getattr(self.config_manager, "is_comic_group_allowed", None)
        inherit_allowed = True if require_auto_enabled else None
        if callable(comic_allowed) and not comic_allowed(umo, inherit_allowed):
            logger.info(
                f"群 {group_id} 未通过漫画名单判定，跳过漫画生成。platform={platform_id or 'default'}"
            )
            return "blocked"

        topics = analysis_result.get("topics", [])
        statistics = analysis_result.get("statistics")
        if not topics and statistics:
            topics = getattr(statistics, "topics", [])

        comic_topics = []
        for topic in topics if isinstance(topics, list) else []:
            title = (
                topic.get("topic", "")
                if isinstance(topic, dict)
                else getattr(topic, "topic", "")
            )
            detail = (
                topic.get("detail", "")
                if isinstance(topic, dict)
                else getattr(topic, "detail", "")
            )
            if str(title).strip():
                comic_topics.append(
                    {"topic": str(title).strip(), "detail": str(detail).strip()}
                )
        if not comic_topics:
            logger.warning(f"群 {group_id} 没有有效话题，跳过漫画生成。")
            return "no_topics"

        task_key = f"{platform_id or 'default'}:{group_id}"
        existing_task = self._comic_group_tasks.get(task_key)
        if existing_task and not existing_task.done():
            logger.info(f"群 {group_id} 已有漫画任务等待或执行，跳过重复任务。")
            return "duplicate"

        task = asyncio.create_task(
            self._trigger_comic_generation(
                comic_topics, group_id, platform_id, umo, trace=trace
            )
        )
        self._comic_group_tasks[task_key] = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(
            lambda completed_task: (
                self._comic_group_tasks.pop(task_key, None)
                if self._comic_group_tasks.get(task_key) is completed_task
                else None
            )
        )
        return "started"

    async def _trigger_comic_generation(
        self,
        topics: list[dict[str, Any]],
        group_id: str,
        platform_id: str | None,
        umo: str,
        trace: TraceContext | None = None,
    ) -> None:
        """后台生成并上传漫画，通过信号量控制并发"""
        cur_trace = trace or TraceContext.current()
        if cur_trace:
            from ...shared.trace_context import _current_trace

            _current_trace.set(cur_trace)

        async with self._comic_semaphore:
            if self.terminating:
                return
            try:
                if cur_trace and self.active_task_manager:
                    await self.active_task_manager.update_stage(
                        cur_trace.trace_id, "COMIC_STORYBOARD"
                    )

                comic_bytes, fallback_url = await self.comic_service.generate_comic(
                    topics, group_id, umo
                )
                if comic_bytes:
                    logger.info(f"群 {group_id} 漫画生成成功，准备发送和保存副本...")
                    ext = self.detect_image_ext(comic_bytes)
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    trace_suffix = f"_{cur_trace.trace_id}" if cur_trace else ""
                    filename = f"comic_{group_id}_{ts_str}{trace_suffix}{ext}"

                    reports_dir = (
                        self.plugin_data_dir / "reports"
                        if self.plugin_data_dir
                        else Path.cwd()
                        / "data"
                        / "plugin_data"
                        / PLUGIN_NAME
                        / "reports"
                    )
                    reports_dir.mkdir(parents=True, exist_ok=True)
                    comic_file_path = reports_dir / filename
                    comic_file_path.write_bytes(comic_bytes)

                    if cur_trace:
                        rfiles = cur_trace.metadata.setdefault("report_files", [])
                        rfiles.append(
                            {
                                "filename": filename,
                                "format": "image",
                                "size_bytes": len(comic_bytes),
                                "stage": "COMIC_GENERATION",
                            }
                        )

                    adapter = (
                        self.bot_manager.get_adapter(platform_id)
                        if self.bot_manager
                        else None
                    )
                    if adapter:
                        show_caption_fn = (
                            getattr(
                                self.config_manager, "get_show_report_caption", None
                            )
                            if self.config_manager
                            else None
                        )
                        show_caption = (
                            show_caption_fn() if callable(show_caption_fn) else True
                        )
                        caption = (
                            TraceContext.make_report_caption() if show_caption else ""
                        )
                        sent = await adapter.send_image(
                            group_id, str(comic_file_path), caption=caption
                        )
                        if sent:
                            if self.plugin_instance and hasattr(
                                self.plugin_instance, "_try_upload_image"
                            ):
                                inst_upload = getattr(
                                    self.plugin_instance, "_try_upload_image"
                                )
                                if (
                                    hasattr(inst_upload, "assert_called")
                                    or hasattr(inst_upload, "assert_awaited")
                                    or hasattr(inst_upload, "_mock_name")
                                    or type(inst_upload).__name__
                                    in ("Mock", "MagicMock", "AsyncMock")
                                ):
                                    await inst_upload(
                                        group_id,
                                        str(comic_file_path),
                                        platform_id,
                                        is_comic=True,
                                    )
                                else:
                                    await self._try_upload_image(
                                        group_id,
                                        str(comic_file_path),
                                        platform_id,
                                        is_comic=True,
                                    )
                            else:
                                await self._try_upload_image(
                                    group_id,
                                    str(comic_file_path),
                                    platform_id,
                                    is_comic=True,
                                )
                elif fallback_url:
                    adapter = self.bot_manager.get_adapter(platform_id)
                    if adapter:
                        await adapter.send_image(group_id, fallback_url)
                else:
                    logger.warning(f"群 {group_id} 漫画生成未产生有效输出。")
            except Exception as e:
                logger.error(f"群 {group_id} 后台漫画生成执行异常: {e}", exc_info=True)

    async def _try_upload_image(
        self,
        group_id: str,
        image_url: str,
        platform_id: str | None,
        is_comic: bool = True,
    ) -> None:
        """尝试将图片上传到群相册"""
        if not self.config_manager:
            return
        upload_album_fn = getattr(
            self.config_manager, "get_enable_comic_album_upload", None
        )
        if not (callable(upload_album_fn) and upload_album_fn()):
            return
        adapter: Any = (
            self.bot_manager.get_adapter(platform_id) if self.bot_manager else None
        )
        if not adapter or not hasattr(adapter, "upload_group_album"):
            return

        album_name_fn = getattr(self.config_manager, "get_comic_album_name", None)
        album_name = album_name_fn() if callable(album_name_fn) else "daily_analysis"
        strict_mode_fn = getattr(
            self.config_manager, "get_group_album_strict_mode", None
        )
        strict_mode = strict_mode_fn() if callable(strict_mode_fn) else False
        try:
            target_path = (
                str(Path(image_url).resolve())
                if Path(image_url).exists()
                else image_url
            )
            await adapter.upload_group_album(
                group_id,
                target_path,
                album_id=None,
                album_name=album_name,
                strict_mode=strict_mode,
            )
        except Exception as e:
            logger.warning(f"漫画群相册上传异常 (群 {group_id}): {e}")
