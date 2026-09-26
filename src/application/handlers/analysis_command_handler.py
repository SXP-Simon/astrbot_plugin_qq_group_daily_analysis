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
from datetime import datetime
from inspect import isawaitable
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import quote

# File is only available via astrbot.core (internal API — may change).
from astrbot.core.message.components import File

from ...domain.repositories.platform_adapter_repository import (
    GroupAlbumSupportProtocol,
    GroupFileSupportProtocol,
    PlatformAdapterProtocol,
)
from ...shared.constants import PLUGIN_NAME, AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..services.analysis_application_service import (
    AnalysisApplicationService,
    DuplicateGroupTaskError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from astrbot.api.event import AstrMessageEvent, MessageEventResult

    from ...domain.repositories.plugin_host_repository import PluginHostProtocol
    from ...domain.value_objects import AnalysisResultPayload
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.messaging.message_sender import MessageSender
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ...infrastructure.platform.bot_manager import BotManager
    from ...infrastructure.reporting.generators import ReportGenerator
    from ...infrastructure.webui.active_task_manager import ActiveTaskManager
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

            group_name = ""
            try:
                adapter = self.bot_manager.get_adapter(platform_id)
                if adapter:
                    info = await adapter.get_group_info(group_id)
                    if info and info.group_name:
                        group_name = info.group_name
            except Exception:
                pass

            trace_id = TraceContext.generate(
                prefix="manual", group_name=group_name or group_id
            )
            trace = TraceContext.set(
                trace_id=trace_id,
                group_id=group_id,
                group_name=group_name,
                platform=platform_id or "",
                trigger_type="manual",
            )
            if self.active_task_manager:
                await self.active_task_manager.register_task(
                    task_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform_id or "",
                    trigger_type="manual",
                    current_stage=AnalysisStage.FETCH_MESSAGES,
                    asyncio_task=current_task,
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
                await adapter.set_reaction(
                    event.get_group_id(), orig_msg_id, "analysis_started"
                )

            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id, platform_id=platform_id, manual=True, days=days
            )

            if not result.get("success"):
                reason = result.get("reason")
                if trace and trace.status == "running":
                    err_msg = (
                        str(result.get("error"))
                        if result.get("error")
                        else f"Analysis skipped/failed: {reason}"
                    )
                    trace.finish(
                        status="failed",
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
                await adapter.set_reaction(
                    event.get_group_id(), orig_msg_id, "analysis_done"
                )

            if self.active_task_manager:
                await self.active_task_manager.update_stage(trace_id, "RENDER_REPORT")

            async for res in self.send_analysis_report(event, result):
                yield res

            if trace and trace.status == "running":
                trace.finish(status="succeeded")

        except DuplicateGroupTaskError:
            if trace and trace.status == "running":
                trace.finish(
                    status="aborted", error_message="Task already running in group"
                )
            yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
        except asyncio.CancelledError:
            if trace and trace.status == "running":
                trace.finish(status="aborted", error_message="Task cancelled by system")
            logger.info("群分析任务被取消 (插件重载或卸载)")
        except Exception as e:
            if trace and trace.status == "running":
                trace.finish(status="failed", error_message=str(e))
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {e!s}。请检查网络连接和LLM配置，或联系管理员"
            )
        finally:
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)

    async def send_analysis_report(
        self, event: AstrMessageEvent, result: dict[str, object]
    ) -> AsyncGenerator[MessageEventResult]:
        """处理分析结果的渲染和发送。

        Args:
            event: AstrBot 消息事件对象。
            result: 分析服务产出的结果字典。

        Returns:
            AsyncGenerator[object, None]: 结果消息生成器。
        """
        if self.terminating or not self.config_manager:
            logger.warning("插件正在关闭，停止发送报告")
            return

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

        if self.comic_handler:
            self.comic_handler.try_trigger_comic_generation(
                group_id, platform_id, analysis_result
            )
        elif self.plugin_instance and self.plugin_instance.comic_command_handler:
            self.plugin_instance.comic_command_handler.try_trigger_comic_generation(
                group_id, platform_id, analysis_result
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
            if trace:
                with trace.span(
                    "RENDER_REPORT",
                    {"format": "image", "template": template_theme},
                ):
                    (
                        image_url,
                        _html_content,
                    ) = await self.report_generator.generate_image_report(
                        analysis_result,
                        group_id,
                        self.html_render,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                        template_theme=template_theme,
                    )
            else:
                (
                    image_url,
                    _html_content,
                ) = await self.report_generator.generate_image_report(
                    analysis_result,
                    group_id,
                    self.html_render,
                    avatar_url_getter=avatar_url_getter,
                    nickname_getter=nickname_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=is_qq_official,
                    template_theme=template_theme,
                )

            if image_url:
                save_history = getattr(
                    self.plugin_instance, "_save_report_to_history", None
                )
                cur_tid = trace.trace_id if trace else None
                if callable(save_history):
                    try:
                        save_history(image_url, group_id, trace_id=cur_tid)
                    except TypeError:
                        save_history(image_url, group_id)
                else:
                    self._save_report_to_history(image_url, group_id, trace_id=cur_tid)

                caption = (
                    TraceContext.make_report_caption()
                    if self.config_manager.get_show_report_caption()
                    else ""
                )
                sent = await adapter.send_image(group_id, image_url, caption=caption)
                if sent:
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
            send_text = getattr(self.plugin_instance, "_send_text_reports", None)
            if callable(send_text):
                res = send_text(group_id, analysis_result, is_qq_official, adapter)
                if isawaitable(res):
                    await res
            else:
                await self._send_text_reports(
                    group_id, analysis_result, is_qq_official, adapter
                )
            return

        elif output_format == "html":
            cur_trace_id = trace.trace_id if trace else None
            if trace:
                with trace.span(
                    "RENDER_REPORT",
                    {"format": "html", "template": template_theme},
                ):
                    (
                        html_path,
                        _json_path,
                    ) = await self.report_generator.generate_html_report(
                        analysis_result,
                        group_id,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                        template_theme=template_theme,
                        trace_id=cur_trace_id,
                    )
            else:
                (
                    html_path,
                    _json_path,
                ) = await self.report_generator.generate_html_report(
                    analysis_result,
                    group_id,
                    avatar_url_getter=avatar_url_getter,
                    nickname_getter=nickname_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=is_qq_official,
                    template_theme=template_theme,
                    trace_id=cur_trace_id,
                )
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
                    elif isinstance(adapter, GroupFileSupportProtocol):
                        sent = await adapter.upload_group_file_to_folder(
                            group_id, html_path, filename=Path(html_path).name
                        )
                        if sent and caption:
                            await adapter.send_text(group_id, caption)

                    if not sent:
                        yield event.chain_result(
                            [File(name=Path(html_path).name, file=html_path)]
                        )
                        if caption:
                            yield event.plain_result(caption)
            else:
                yield event.plain_result("⚠️ HTML 生成失败。")

        else:
            send_text = getattr(self.plugin_instance, "_send_text_reports", None)
            if callable(send_text):
                res = send_text(group_id, analysis_result, is_qq_official, adapter)
                if isawaitable(res):
                    await res
            else:
                await self._send_text_reports(
                    group_id, analysis_result, is_qq_official, adapter
                )

    async def _send_text_reports(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        is_qq_official: bool,
        adapter: PlatformAdapterProtocol,
    ) -> None:
        """发送纯文本分析报告。

        Args:
            group_id: 目标群号。
            analysis_result: 分析结果字典。
            is_qq_official: 是否为 QQ 官方平台。
            adapter: 平台适配器。
        """
        try:
            if is_qq_official and hasattr(
                self.report_generator, "generate_qq_official_markdown_report"
            ):
                (
                    text_report,
                    fallback_report,
                ) = await self.report_generator.generate_qq_official_markdown_report(
                    analysis_result, self.html_render
                )
                await adapter.send_text_report(
                    group_id, text_report, fallback_content=fallback_report
                )
                return

            text = self.report_generator.generate_text_report(analysis_result)
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
                from ...shared.trace_context import _global_trace_store

                if _global_trace_store is not None:
                    try:
                        _global_trace_store.save_trace(cur_trace.to_dict())
                    except Exception:
                        pass
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
