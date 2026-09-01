"""
AstrBot 插件 Pages 后端 Web API 桥接服务
为 React + Ant Design 5 控制台提供 REST 与 SSE 接口。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.api.star import Context
    from astrbot.api.web import (
        error_response,
        json_response,
        request,
        stream_response,
    )
else:
    try:
        from astrbot.api.star import Context
        from astrbot.api.web import (
            error_response,
            json_response,
            request,
            stream_response,
        )
    except (ImportError, AttributeError):

        class Context:
            pass

        def json_response(
            data: Any = None,
            *,
            status_code: int = 200,
            headers: dict[str, str] | None = None,
        ) -> Any:
            return {"status_code": status_code, "data": data}

        def error_response(
            message: str = "",
            *,
            status_code: int = 400,
            data: Any = None,
            headers: dict[str, str] | None = None,
        ) -> Any:
            return {"status_code": status_code, "message": message, "data": data}

        request: Any = None

        def stream_response(
            content: Any = None,
            *,
            content_type: str = "text/event-stream",
            status_code: int = 200,
            headers: dict[str, str] | None = None,
        ) -> Any:
            return content


from ...shared.constants import PLUGIN_NAME
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..persistence.trace_sqlite_store import TraceSQLiteStore
from ..platform.factory import PlatformAdapterFactory
from .active_task_manager import ActiveTaskManager


def _sanitize_path_segment(segment: str) -> str:
    cleaned = []
    for ch in segment:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch.isdigit() or ch in {"-", "_"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    return result or "_"


def _config_key_to_folder(key_path: str) -> str:
    """与 AstrBot 官方核心完全一致的 config_key 到存储目录转换规则（以 / 分隔）"""
    parts = [_sanitize_path_segment(part) for part in key_path.split(".") if part]
    return "/".join(parts) if parts else "_"


class PluginPageWebUIBridge:
    """WebUI 面板 API 桥接适配器"""

    def __init__(
        self,
        context: Context,
        trace_store: TraceSQLiteStore,
        active_task_manager: ActiveTaskManager,
        analysis_service: Any,
        report_dispatcher: Any = None,
        report_output_dir: Path | None = None,
    ):
        self.context = context
        self.trace_store = trace_store
        self.active_task_manager = active_task_manager
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.report_output_dir = report_output_dir
        TraceContext.set_active_task_manager(self.active_task_manager)

    def register_routes(self) -> None:
        """向 AstrBot 注册所有 Web API 端点"""
        routes = [
            # 1. 活跃任务与控制
            (
                f"/{PLUGIN_NAME}/tasks/active",
                self.api_get_active_tasks,
                ["GET"],
                "Get active running analysis tasks",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/cancel",
                self.api_cancel_task,
                ["POST"],
                "Cancel an active analysis task",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/trigger",
                self.api_trigger_task,
                ["POST"],
                "Trigger an analysis task manually",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/<trace_id>/resume",
                self.api_resume_task,
                ["POST"],
                "Resume an analysis task from checkpoint",
            ),
            # 2. 链路追溯与详情
            (
                f"/{PLUGIN_NAME}/traces",
                self.api_list_traces,
                ["GET"],
                "List execution traces with filters",
            ),
            (
                f"/{PLUGIN_NAME}/traces/<trace_id>",
                self.api_get_trace_detail,
                ["GET"],
                "Get full trace details with spans and metrics",
            ),
            (
                f"/{PLUGIN_NAME}/metrics/summary",
                self.api_get_metrics_summary,
                ["GET"],
                "Get KPI and token metrics summary",
            ),
            (
                f"/{PLUGIN_NAME}/metrics/trends",
                self.api_get_analytics_trends,
                ["GET"],
                "Get time-series trends with hour/day granularity and provider breakdowns",
            ),
            (
                f"/{PLUGIN_NAME}/groups",
                self.api_get_distinct_groups,
                ["GET"],
                "Get distinct groups list for filtering",
            ),
            (
                f"/{PLUGIN_NAME}/platforms",
                self.api_get_platforms,
                ["GET"],
                "Get active connected bot platforms list",
            ),
            (
                f"/{PLUGIN_NAME}/providers",
                self.api_get_providers,
                ["GET"],
                "Get available LLM providers list",
            ),
            (
                f"/{PLUGIN_NAME}/personas",
                self.api_get_personas,
                ["GET"],
                "Get available AstrBot personas list",
            ),
            # 4. 历史产物
            (
                f"/{PLUGIN_NAME}/reports/history",
                self.api_get_report_history,
                ["GET"],
                "Get generated report image list",
            ),
            (
                f"/{PLUGIN_NAME}/reports/content",
                self.api_get_report_content,
                ["GET"],
                "Get generated report image base64 content",
            ),
            (
                f"/{PLUGIN_NAME}/reports/rerender",
                self.api_rerender_report,
                ["POST"],
                "Re-render report with a new theme template using cached checkpoint without LLM tokens",
            ),
            (
                f"/{PLUGIN_NAME}/reports/templates",
                self.api_get_report_templates,
                ["GET"],
                "Get available built-in and custom report visual templates",
            ),
            # 5. SSE 实时事件流
            (
                f"/{PLUGIN_NAME}/events/stream",
                self.api_stream_events,
                ["GET"],
                "SSE stream for real-time task progress events",
            ),
            # 6. 插件专属日志
            (
                f"/{PLUGIN_NAME}/logs",
                self.api_get_plugin_logs,
                ["GET"],
                "Get plugin live logs with filters",
            ),
            (
                f"/{PLUGIN_NAME}/traces/<trace_id>/logs",
                self.api_get_trace_logs,
                ["GET"],
                "Get execution logs for a specific trace",
            ),
            (
                f"/{PLUGIN_NAME}/logs/clear",
                self.api_clear_plugin_logs,
                ["POST"],
                "Clear in-memory plugin log buffer",
            ),
            # 7. 插件配置中心
            (
                f"/{PLUGIN_NAME}/config",
                self.api_get_config,
                ["GET"],
                "Get current plugin configuration and schema definition",
            ),
            (
                f"/{PLUGIN_NAME}/config",
                self.api_save_config,
                ["POST"],
                "Save and persist updated plugin configuration",
            ),
            (
                f"/{PLUGIN_NAME}/config/upload_file",
                self.api_upload_config_file,
                ["POST"],
                "Upload a config reference image/file and store to files/ folder",
            ),
            (
                f"/{PLUGIN_NAME}/config/file/content",
                self.api_get_config_file_content,
                ["GET"],
                "Get thumbnail or content of a config file path",
            ),
        ]

        for path, handler, methods, desc in routes:
            try:
                self.context.register_web_api(path, handler, methods, desc)  # type: ignore
            except Exception as e:
                logger.error(f"注册 Web API 路由 {path} 失败: {e}")

        # 挂载日志流至 SSE 广播通道，实现毫秒级实时日志推送
        try:
            from ..logging.plugin_log_buffer import global_log_buffer

            def _forward_log_to_sse(entry: Any) -> None:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self.active_task_manager._broadcast_event(
                            {"event": "log_entry", "data": entry.to_dict()}
                        )
                    )
                except RuntimeError:
                    pass

            global_log_buffer.register_listener(_forward_log_to_sse)
        except Exception as e:
            logger.warning(f"挂载日志 SSE 监听器失败: {e}")

    async def api_get_active_tasks(self) -> Any:
        """获取当前正在执行的任务列表"""
        tasks = self.active_task_manager.get_active_tasks()
        return json_response({"status": "ok", "data": tasks})

    async def api_cancel_task(self) -> Any:
        """手动取消正在执行的任务"""
        try:
            payload_raw = await request.json(default={})
            payload: dict[str, Any] = (
                payload_raw if isinstance(payload_raw, dict) else {}
            )
            task_id = payload.get("task_id", "").strip()
            if not task_id:
                return error_response("Missing task_id in request", status_code=400)

            success = await self.active_task_manager.cancel_task(task_id)
            if success:
                return json_response(
                    {"status": "ok", "message": f"Task {task_id} canceled successfully"}
                )
            return error_response(
                f"Task {task_id} not found or already finished", status_code=404
            )
        except Exception as e:
            logger.error(f"取消任务异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_trigger_task(self) -> Any:
        """从 Web 界面手动触发群分析任务"""
        try:
            payload_raw = await request.json(default={})
            payload: dict[str, Any] = (
                payload_raw if isinstance(payload_raw, dict) else {}
            )
            group_id = str(payload.get("group_id", "")).strip()
            if not group_id:
                return error_response("group_id is required", status_code=400)

            group_name = str(payload.get("group_name", f"群 {group_id}"))
            platform = str(payload.get("platform", "qq"))

            # 生成语义化 TraceID
            trace_id = TraceContext.generate("web_manual", group_name)

            provider_id = (
                payload.get("provider_id") if isinstance(payload, dict) else None
            )
            if not provider_id and hasattr(request, "query"):
                provider_id = request.query.get("provider_id")

            # 启动后台异步任务
            asyncio_task = asyncio.create_task(
                self._run_triggered_task(
                    trace_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform,
                    provider_id=provider_id,
                )
            )

            # 注册到活跃任务管理器
            await self.active_task_manager.register_task(
                task_id=trace_id,
                group_id=group_id,
                group_name=group_name,
                platform=platform,
                trigger_type="web_ui",
                current_stage="FETCH_MESSAGES",
                asyncio_task=asyncio_task,
            )

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "trace_id": trace_id,
                        "group_id": group_id,
                        "message": "Analysis task queued successfully",
                    },
                }
            )
        except Exception as e:
            logger.error(f"触发分析任务异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def _run_triggered_task(
        self,
        trace_id: str,
        group_id: str,
        group_name: str,
        platform: str,
        provider_id: str | None = None,
    ) -> None:
        """后台异步执行触发任务"""
        trace_ctx = TraceContext.set(
            trace_id=trace_id,
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            trigger_type="web_ui",
        )
        if provider_id:
            trace_ctx.metadata["override_provider_id"] = str(provider_id)
        try:
            if hasattr(self.analysis_service, "execute_daily_analysis"):
                result = await self.analysis_service.execute_daily_analysis(
                    group_id=group_id,
                    platform_id=platform
                    if platform and platform not in ("all", "auto", "default")
                    else None,
                    manual=True,
                )
                if result and result.get("success"):
                    analysis_result = result.get("analysis_result")
                    adapter = result.get("adapter")
                    bot_mgr = getattr(self.analysis_service, "bot_manager", None)
                    dispatch_platform_id = (
                        (
                            bot_mgr.get_adapter_platform_id(adapter)
                            if bot_mgr and adapter
                            else ""
                        )
                        or getattr(adapter, "platform_id", "")
                        or (
                            platform
                            if platform and platform not in ("all", "auto", "default")
                            else ""
                        )
                    )
                    trace_ctx.platform = str(dispatch_platform_id)
                    # 调度生成报告长图并推送到目标群聊
                    if self.report_dispatcher and analysis_result:
                        try:
                            await self.report_dispatcher.dispatch(
                                group_id,
                                analysis_result,
                                dispatch_platform_id,
                            )
                        except Exception as dispatch_err:
                            logger.error(
                                f"WebUI 触发报告发送异常 (群 {group_id}): {dispatch_err}",
                                exc_info=True,
                            )

                    if trace_ctx.status == "running":
                        trace_ctx.finish(status="succeeded")
                else:
                    if trace_ctx.status == "running":
                        trace_ctx.finish(
                            status="failed",
                            error_message=str(result.get("reason", "unknown")),
                        )
            elif hasattr(self.analysis_service, "analyze_group_daily"):
                await self.analysis_service.analyze_group_daily(
                    group_id=group_id,
                    platform_name=platform,
                    is_manual=True,
                    trace_ctx=trace_ctx,
                )
                if trace_ctx.status == "running":
                    trace_ctx.finish(status="succeeded")
            else:
                with trace_ctx.span("FETCH_MESSAGES"):
                    await asyncio.sleep(0.5)
                with trace_ctx.span("LLM_ANALYSIS"):
                    await asyncio.sleep(1.0)
                trace_ctx.set_context_metrics(1200, 800)
                trace_ctx.add_token_usage(1500, 300, "topics")
                if trace_ctx.status == "running":
                    trace_ctx.finish(status="succeeded")
        except Exception as e:
            if trace_ctx.status == "running":
                trace_ctx.finish(status="failed", error_message=str(e))
            logger.error(f"任务 {trace_id} 执行出错: {e}", exc_info=True)
        finally:
            await self.active_task_manager.finish_task(trace_id)

    async def api_resume_task(self, trace_id: str) -> Any:
        """从 Checkpoint 幂等恢复并重试任务"""
        try:
            trace_record = self.trace_store.get_trace(trace_id)
            if not trace_record:
                return error_response(f"Trace {trace_id} not found", status_code=404)

            group_id = str(trace_record.get("group_id", ""))
            group_name = str(trace_record.get("group_name", ""))
            platform = str(trace_record.get("platform", ""))

            payload = {}
            if hasattr(request, "json"):
                try:
                    payload = await request.json()
                except Exception:
                    payload = {}
            provider_id = (
                payload.get("provider_id") if isinstance(payload, dict) else None
            )
            template_name = (
                payload.get("template_name") if isinstance(payload, dict) else None
            )
            if not provider_id and hasattr(request, "query"):
                provider_id = request.query.get("provider_id")
            if not template_name and hasattr(request, "query"):
                template_name = request.query.get("template_name")

            # 启动后台异步任务
            asyncio_task = asyncio.create_task(
                self._run_resumed_task(
                    trace_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform,
                    provider_id=provider_id,
                    template_name=template_name,
                )
            )

            await self.active_task_manager.register_task(
                task_id=trace_id,
                group_id=group_id,
                group_name=group_name,
                platform=platform,
                trigger_type="resume",
                current_stage="LLM_ANALYSIS",
                asyncio_task=asyncio_task,
            )

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "trace_id": trace_id,
                        "group_id": group_id,
                        "provider_id": provider_id,
                        "template_name": template_name,
                        "message": "Task resume queued successfully",
                    },
                }
            )
        except Exception as e:
            logger.error(f"恢复任务异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def _run_resumed_task(
        self,
        trace_id: str,
        group_id: str,
        group_name: str,
        platform: str,
        provider_id: str | None = None,
        template_name: str | None = None,
    ) -> None:
        """后台异步执行断点续跑"""
        trace_ctx = TraceContext.set(
            trace_id=trace_id,
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            trigger_type="resume",
        )
        if provider_id:
            trace_ctx.metadata["override_provider_id"] = str(provider_id)
        if template_name and template_name != "auto":
            trace_ctx.metadata["override_template_name"] = str(template_name)
        try:
            if hasattr(self.analysis_service, "resume_analysis"):
                result = await self.analysis_service.resume_analysis(
                    trace_id=trace_id,
                    group_id=group_id,
                    platform_id=platform
                    if platform and platform not in ("all", "auto", "default")
                    else None,
                    template_name=template_name,
                )
                if result and result.get("success"):
                    analysis_result = result.get("analysis_result")
                    adapter = result.get("adapter")
                    bot_mgr = getattr(self.analysis_service, "bot_manager", None)
                    dispatch_platform_id = (
                        (
                            bot_mgr.get_adapter_platform_id(adapter)
                            if bot_mgr and adapter
                            else ""
                        )
                        or getattr(adapter, "platform_id", "")
                        or (
                            platform
                            if platform and platform not in ("all", "auto", "default")
                            else ""
                        )
                    )
                    trace_ctx.platform = str(dispatch_platform_id)
                    if self.report_dispatcher and analysis_result:
                        try:
                            with trace_ctx.span(
                                "DISPATCH_REPORT",
                                {
                                    "platform": dispatch_platform_id or "auto",
                                    "group_id": group_id,
                                },
                            ):
                                await self.report_dispatcher.dispatch(
                                    group_id,
                                    analysis_result,
                                    dispatch_platform_id,
                                )
                        except Exception as dispatch_err:
                            logger.error(
                                f"WebUI 续跑报告发送异常 (群 {group_id}): {dispatch_err}",
                                exc_info=True,
                            )

                    if trace_ctx.status == "running":
                        trace_ctx.finish(status="succeeded")
                else:
                    if trace_ctx.status == "running":
                        trace_ctx.finish(
                            status="failed",
                            error_message=str(result.get("reason", "unknown")),
                        )
            else:
                await self._run_triggered_task(trace_id, group_id, group_name, platform)
        except Exception as e:
            if trace_ctx.status == "running":
                trace_ctx.finish(status="failed", error_message=str(e))
            logger.error(f"续跑任务 {trace_id} 执行出错: {e}", exc_info=True)
        finally:
            await self.active_task_manager.finish_task(trace_id)

    async def api_list_traces(self) -> Any:
        """分页与条件筛选 Trace 列表"""
        try:
            limit = int(request.query.get("limit", 20))
            offset = int(request.query.get("offset", 0))
            group_id = request.query.get("group_id")
            status = request.query.get("status")
            search = request.query.get("search")
            start_time_raw = request.query.get("start_time")
            end_time_raw = request.query.get("end_time")
            sort_by = request.query.get("sort_by", "started_at")
            sort_order = request.query.get("sort_order", "desc")

            start_time = float(start_time_raw) if start_time_raw else None
            end_time = float(end_time_raw) if end_time_raw else None

            items, total = self.trace_store.list_traces(
                limit=limit,
                offset=offset,
                group_id=group_id,
                status=status,
                search=search,
                start_time=start_time,
                end_time=end_time,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return json_response(
                {"status": "ok", "data": {"items": items, "total": total}}
            )
        except Exception as e:
            logger.error(f"查询 Trace 列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_distinct_groups(self) -> Any:
        """获取所有有历史分析记录的群组列表（用于下拉快速筛选）"""
        try:
            groups = self.trace_store.get_distinct_groups()
            return json_response({"status": "ok", "data": groups})
        except Exception as e:
            logger.error(f"查询群组列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_platforms(self) -> Any:
        """获取当前 AstrBot 中已注册并就绪的所有聊天平台列表（基于 AstrBot 原生 PlatformMetadata）"""
        try:
            platforms: list[dict[str, Any]] = []
            seen_ids = set()
            type_display_map = {
                "aiocqhttp": "OneBot v11",
                "qq_official": "QQ 官方机器人",
                "qq_official_webhook": "QQ 官方 Webhook",
                "telegram": "Telegram",
                "discord": "Discord",
            }

            # 1. 优先从 AstrBot 原生 platform_manager 获取标准元数据
            platform_manager = getattr(self.context, "platform_manager", None)
            if platform_manager and hasattr(platform_manager, "get_insts"):
                insts = platform_manager.get_insts() or []
                for inst in insts:
                    try:
                        meta = (
                            inst.meta()
                            if callable(getattr(inst, "meta", None))
                            else None
                        )
                        p_id = (
                            getattr(meta, "id", None)
                            or (
                                getattr(inst, "config", {}).get("id")
                                if isinstance(getattr(inst, "config", None), dict)
                                else None
                            )
                            or ""
                        )
                        p_type = (
                            getattr(meta, "name", "")
                            or (
                                getattr(inst, "config", {}).get("type", "")
                                if isinstance(getattr(inst, "config", None), dict)
                                else ""
                            )
                            or ""
                        )
                        # 仅保留插件适配器工厂支持的聊天平台
                        if (
                            not p_id
                            or p_id in seen_ids
                            or not PlatformAdapterFactory.is_supported(p_type)
                        ):
                            continue

                        meta_display = getattr(meta, "adapter_display_name", "")
                        display_name = (
                            meta_display
                            if (meta_display and meta_display != p_type)
                            else type_display_map.get(p_type, p_type)
                        )
                        label = (
                            display_name
                            if (p_id == p_type or p_id == display_name)
                            else f"{display_name} ({p_id})"
                        )

                        seen_ids.add(p_id)
                        platforms.append(
                            {
                                "id": str(p_id),
                                "type": str(p_type),
                                "display_name": str(display_name),
                                "label": str(label),
                            }
                        )
                    except Exception:
                        pass

            # 2. 兜底补全已在 bot_manager 注册的适配器
            bot_manager = getattr(self.analysis_service, "bot_manager", None)
            if bot_manager:
                for p_id, adp in bot_manager.get_all_adapters().items():
                    if p_id in seen_ids:
                        continue
                    p_name = getattr(adp, "platform_name", "unknown")
                    display_name = type_display_map.get(
                        p_name, type(adp).__name__.replace("Adapter", "")
                    )
                    label = (
                        display_name if p_id == p_name else f"{display_name} ({p_id})"
                    )
                    seen_ids.add(p_id)
                    platforms.append(
                        {
                            "id": str(p_id),
                            "type": str(p_name),
                            "display_name": str(display_name),
                            "label": str(label),
                        }
                    )

            return json_response({"status": "ok", "data": platforms})
        except Exception as e:
            logger.error(f"获取平台列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_providers(self) -> Any:
        """获取当前 AstrBot 中已就绪的所有 LLM Provider 列表"""
        try:
            providers: list[dict[str, Any]] = []
            seen_ids = set()
            provider_getter = getattr(self.context, "get_all_providers", None)
            if not callable(provider_getter):
                provider_mgr = getattr(self.context, "provider_manager", None)
                provider_getter = getattr(provider_mgr, "get_all_providers", None)

            if callable(provider_getter):
                raw_list = provider_getter()
                provider_list: list[Any] = (
                    list(raw_list) if isinstance(raw_list, Iterable) else []
                )
                for p in provider_list:
                    try:
                        meta = p.meta() if callable(getattr(p, "meta", None)) else None
                        p_id = (
                            getattr(meta, "id", None)
                            or (
                                getattr(p, "config", {}).get("id")
                                if isinstance(getattr(p, "config", None), dict)
                                else None
                            )
                            or getattr(p, "id", None)
                            or str(p)
                        )
                        if not p_id or p_id in seen_ids:
                            continue
                        p_name = (
                            getattr(meta, "name", None)
                            or getattr(meta, "model", None)
                            or p_id
                        )
                        p_type = getattr(meta, "provider_type", "")
                        seen_ids.add(p_id)
                        providers.append(
                            {
                                "id": str(p_id),
                                "name": str(p_name),
                                "type": str(p_type),
                                "label": f"{p_name} ({p_id})"
                                if p_name != p_id
                                else str(p_name),
                            }
                        )
                    except Exception:
                        pass
            return json_response({"status": "ok", "data": providers})
        except Exception as e:
            logger.error(f"获取 Provider 列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_personas(self) -> Any:
        """获取当前 AstrBot 中配置的所有人格 (Persona) 列表"""
        try:
            personas: list[dict[str, Any]] = []
            seen_ids = set()
            pm = getattr(self.context, "persona_manager", None)
            if pm:
                # 1. 优先读取 v3 personas
                for p in getattr(pm, "personas_v3", []) or []:
                    p_name = (
                        p.get("name")
                        if isinstance(p, dict)
                        else getattr(p, "name", None)
                    )
                    if p_name and p_name not in seen_ids:
                        seen_ids.add(p_name)
                        personas.append(
                            {
                                "id": str(p_name),
                                "name": str(p_name),
                                "label": str(p_name),
                            }
                        )
                # 2. 读取持久化 DB personas
                for p in getattr(pm, "personas", []) or []:
                    p_id = getattr(p, "persona_id", None) or getattr(p, "name", None)
                    p_name = getattr(p, "name", None) or p_id
                    if p_id and p_id not in seen_ids:
                        seen_ids.add(p_id)
                        personas.append(
                            {
                                "id": str(p_id),
                                "name": str(p_name),
                                "label": f"{p_name} ({p_id})"
                                if p_name != p_id
                                else str(p_name),
                            }
                        )
            return json_response({"status": "ok", "data": personas})
        except Exception as e:
            logger.error(f"获取 Persona 列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_trace_detail(self, trace_id: str) -> Any:
        """获取单个 Trace 的完整 Span 树与上下文指标

        优先查 SQLite 持久化记录；若未入库（任务尚在运行中），则回退到
        TraceContext 内存活跃实例与 ActiveTaskManager 快照，实时展示运行中的 Spans 状态。
        """
        try:
            trace = self.trace_store.get_trace(trace_id)
            if trace:
                return json_response({"status": "ok", "data": trace})

            # 回退：从活跃 TraceContext 实例获取实时未完成的 Spans 和当前阶段
            active_trace = TraceContext.get_active_trace(trace_id)
            task_info = None
            for t in self.active_task_manager.get_active_tasks():
                if t.get("task_id") == trace_id:
                    task_info = t
                    break

            if active_trace or task_info:
                started_at = (
                    active_trace.started_at
                    if active_trace
                    else (
                        task_info.get("started_at", time.time())
                        if task_info
                        else time.time()
                    )
                )
                current_stage = (
                    active_trace.current_stage
                    if (active_trace and active_trace.current_stage)
                    else (
                        task_info.get("current_stage", "")
                        if task_info
                        else "FETCH_MESSAGES"
                    )
                )
                spans = list(active_trace._spans) if active_trace else []
                context_metrics = (
                    active_trace._context_metrics if active_trace else None
                )
                token_usage = active_trace._token_usage if active_trace else None

                group_id_val = (active_trace.group_id if active_trace else "") or (
                    task_info.get("group_id", "") if task_info else ""
                )
                group_name_val = (active_trace.group_name if active_trace else "") or (
                    task_info.get("group_name", "") if task_info else ""
                )
                platform_val = (active_trace.platform if active_trace else "") or (
                    task_info.get("platform", "") if task_info else ""
                )
                trigger_type_val = (
                    active_trace.trigger_type if active_trace else ""
                ) or (
                    task_info.get("trigger_type", "manual") if task_info else "manual"
                )

                return json_response(
                    {
                        "status": "ok",
                        "data": {
                            "trace_id": trace_id,
                            "group_id": group_id_val,
                            "group_name": group_name_val,
                            "platform": platform_val,
                            "trigger_type": trigger_type_val,
                            "status": "running",
                            "started_at": started_at,
                            "completed_at": None,
                            "duration_ms": round((time.time() - started_at) * 1000),
                            "error_stage": None,
                            "error_message": None,
                            "stack_trace": None,
                            "extra": dict(active_trace.metadata)
                            if active_trace
                            else {},
                            "spans": spans,
                            "context_metrics": context_metrics,
                            "token_usage": token_usage,
                            "current_stage": current_stage,
                        },
                    }
                )

            return error_response(f"Trace {trace_id} not found", status_code=404)
        except Exception as e:
            logger.error(f"查询 Trace 详情异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_metrics_summary(self) -> Any:
        """获取顶部 KPI 与 Token 统计概览"""
        try:
            summary = self.trace_store.get_metrics_summary()
            return json_response({"status": "ok", "data": summary})
        except Exception as e:
            logger.error(f"获取指标概览异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_analytics_trends(self) -> Any:
        """获取时序趋势统计（支持按小时或按天细粒度切换，并包含服务商与模型统计）"""
        try:
            granularity = (
                request.query.get("granularity", "day")
                if request and hasattr(request, "query")
                else "day"
            )
            range_count = (
                int(
                    request.query.get(
                        "range_count", 48 if granularity == "hour" else 14
                    )
                )
                if request and hasattr(request, "query")
                else (48 if granularity == "hour" else 14)
            )

            trends_data = self.trace_store.get_analytics_trends(
                granularity=granularity, range_count=range_count
            )
            return json_response({"status": "ok", "data": trends_data})
        except Exception as e:
            logger.error(f"获取趋势图表数据异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_report_history(self) -> Any:
        """获取历史生成的报告文件列表（支持图片与 HTML 报告，包含群号、群名与平台归属精准解析）"""
        try:
            reports: list[dict[str, Any]] = []
            group_info_map = {
                str(g["group_id"]): {
                    "group_name": str(g.get("group_name", "")),
                    "platform": str(g.get("platform", "")),
                }
                for g in self.trace_store.get_distinct_groups()
            }
            candidate_dirs: list[Path] = []
            if self.report_output_dir and self.report_output_dir.exists():
                candidate_dirs.append(self.report_output_dir)

            # 兼容自托管 HTML 输出目录
            cfg_mgr = getattr(self.analysis_service, "config_manager", None) or getattr(
                self.report_dispatcher, "config_manager", None
            )
            if cfg_mgr:
                custom_html_dir = getattr(cfg_mgr, "get_html_output_dir", lambda: "")()
                if custom_html_dir:
                    p = Path(custom_html_dir)
                    if p.exists() and p not in candidate_dirs:
                        candidate_dirs.append(p)

            seen_paths = set()
            all_files: list[Path] = []
            for d in candidate_dirs:
                for p in d.iterdir():
                    if (
                        p.is_file()
                        and p.suffix.lower()
                        in {".jpg", ".jpeg", ".png", ".webp", ".html", ".htm"}
                        and p.resolve() not in seen_paths
                    ):
                        seen_paths.add(p.resolve())
                        all_files.append(p)

            report_trace_map: dict[str, str] = {}
            if hasattr(self.trace_store, "get_report_trace_map"):
                try:
                    report_trace_map = self.trace_store.get_report_trace_map()
                except Exception:
                    pass

            for file_path in sorted(
                all_files,
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:150]:
                try:
                    stat = file_path.stat()
                    stem = file_path.stem
                    is_html = file_path.suffix.lower() in {".html", ".htm"}
                    is_comic = stem.lower().startswith("comic_") or stem.startswith(
                        "漫画_"
                    )
                    trace_id = report_trace_map.get(file_path.name, "")
                    group_id = ""

                    # 1. 优先通过数据库已登记群号精确匹配（最长匹配优先，避免前缀歧义）
                    for known_gid in sorted(
                        group_info_map.keys(), key=len, reverse=True
                    ):
                        if not known_gid:
                            continue
                        if re.search(rf"(?:^|_){re.escape(known_gid)}(?:_|$)", stem):
                            group_id = known_gid
                            break

                    # 2. 若未匹配到已知群，按结构化模式解析群号
                    if not group_id:
                        m = re.match(
                            r"^(?:report|群聊分析报告|comic|漫画)_(.+?)_(?:\d{4}-?\d{2}-?\d{2}|\d{8})(?:_\d{6})?(?:_([a-zA-Z0-9_\-]+))?$",
                            stem,
                            re.IGNORECASE,
                        )
                        if m:
                            group_id = m.group(1)
                            if m.group(2) and not trace_id:
                                cand = m.group(2)
                                if "_" in cand or len(cand) < 26:
                                    trace_id = cand
                        else:
                            m = re.match(
                                r"^(?:report|群聊分析报告|comic|漫画)_(.+?)_\d+$",
                                stem,
                                re.IGNORECASE,
                            )
                            if m:
                                group_id = m.group(1)
                            else:
                                m = re.match(
                                    r"^(?:report|群聊分析报告|comic|漫画)_(.+?)$",
                                    stem,
                                    re.IGNORECASE,
                                )
                                group_id = m.group(1) if m else stem

                    # 3. 兜底获取 trace_id
                    if not trace_id:
                        trace_id = report_trace_map.get(file_path.name, "")
                    if not trace_id:
                        # 检查文件名中是否直接包含了已知 trace_id
                        for tid in set(report_trace_map.values()):
                            if tid and tid in stem:
                                trace_id = tid
                                break
                    if not trace_id and group_id:
                        # 检查同群同精确时间戳（年月日_时分秒）前缀的文件映射，避免同天不同任务误匹配
                        stem_parts = stem.split("_")
                        if len(stem_parts) >= 4 and re.match(r"^\d{6}$", stem_parts[3]):
                            stem_prefix = "_".join(stem_parts[:4])
                            for fn, tid in report_trace_map.items():
                                if tid and fn.startswith(stem_prefix):
                                    trace_id = tid
                                    break

                    g_info = group_info_map.get(group_id, {})
                    group_name = g_info.get("group_name", "")
                    platform = g_info.get("platform", "")

                    reports.append(
                        {
                            "filename": file_path.name,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                            "absolute_path": str(file_path.resolve()),
                            "is_html": is_html,
                            "is_comic": is_comic,
                            "report_type": "comic"
                            if is_comic
                            else ("html" if is_html else "image"),
                            "group_id": group_id,
                            "group_name": group_name,
                            "platform": platform,
                            "trace_id": trace_id,
                        }
                    )
                except Exception:
                    pass
            return json_response({"status": "ok", "data": reports})
        except Exception as e:
            logger.error(f"查询历史报告异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_report_content(self) -> Any:
        """获取单个历史报告文件（图片或 HTML）的内容用于在线预览与下载"""
        try:
            filename = (
                request.query.get("filename", "").strip()
                if request and hasattr(request, "query")
                else ""
            )
            if not filename:
                return error_response("Missing filename parameter", status_code=400)

            safe_filename = Path(filename).name
            target_file: Path | None = None

            # 搜索输出目录与自托管 HTML 目录
            search_dirs = []
            if self.report_output_dir and self.report_output_dir.exists():
                search_dirs.append(self.report_output_dir)
            cfg_mgr = getattr(self.analysis_service, "config_manager", None) or getattr(
                self.report_dispatcher, "config_manager", None
            )
            if cfg_mgr:
                custom_html_dir = getattr(cfg_mgr, "get_html_output_dir", lambda: "")()
                if custom_html_dir:
                    p = Path(custom_html_dir)
                    if p.exists() and p not in search_dirs:
                        search_dirs.append(p)

            for d in search_dirs:
                cand = d / safe_filename
                if cand.is_file() and cand.exists():
                    target_file = cand
                    break

            if not target_file:
                return error_response(
                    f"Report file {safe_filename} not found", status_code=404
                )

            ext = target_file.suffix.lower().lstrip(".")
            is_html = ext in ("html", "htm")
            stat = target_file.stat()

            if is_html:
                raw_text = target_file.read_text(encoding="utf-8", errors="replace")
                b64_content = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
                data_url = f"data:text/html;charset=utf-8;base64,{b64_content}"
                return json_response(
                    {
                        "status": "ok",
                        "data": {
                            "filename": safe_filename,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                            "absolute_path": str(target_file.resolve()),
                            "is_html": True,
                            "html_content": raw_text,
                            "data_url": data_url,
                        },
                    }
                )
            else:
                mime_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
                with open(target_file, "rb") as f:
                    b64_content = base64.b64encode(f.read()).decode("utf-8")
                return json_response(
                    {
                        "status": "ok",
                        "data": {
                            "filename": safe_filename,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                            "absolute_path": str(target_file.resolve()),
                            "is_html": False,
                            "data_url": f"data:{mime_type};base64,{b64_content}",
                        },
                    }
                )
        except Exception as e:
            logger.error(f"读取历史报告内容异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_rerender_report(self) -> Any:
        """免 Token 切换模板重新渲染历史分析报告"""
        try:
            body_raw = await request.json() if hasattr(request, "json") else {}
            body: dict[str, Any] = body_raw if isinstance(body_raw, dict) else {}
        except Exception:
            body = {}

        group_id = str(body.get("group_id", "")).strip()
        date_str = str(body.get("date_str", "")).strip()
        template_name = str(body.get("template_name", "default")).strip()
        render_format = str(body.get("render_format", "image")).strip()
        platform_id = body.get("platform_id")
        trace_id = str(body.get("trace_id", "")).strip()

        if not group_id:
            return error_response("缺少群号参数 group_id", status_code=400)
        if not date_str:
            import datetime as _dt

            date_str = _dt.datetime.now().strftime("%Y-%m-%d")

        if not trace_id and hasattr(self, "trace_store"):
            try:
                recent_res = self.trace_store.list_traces(group_id=group_id, limit=5)
                items = recent_res.get("items") if isinstance(recent_res, dict) else []
                if items:
                    trace_id = str(items[0].get("trace_id", ""))
            except Exception:
                pass

        try:
            result = await self.analysis_service.rerender_report(
                group_id=group_id,
                date_str=date_str,
                template_name=template_name,
                platform_id=platform_id,
                render_format=render_format,
                trace_id=trace_id if trace_id else None,
            )
            if not result.get("success"):
                return error_response(
                    result.get("reason", "重新渲染失败"), status_code=400
                )
            return json_response({"status": "ok", "data": result})
        except Exception as e:
            logger.error(f"重新渲染报告异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_report_templates(self) -> Any:
        """获取系统内置及用户自定义的所有可用报告视觉模板"""
        try:
            generator = getattr(
                self.analysis_service, "report_generator", None
            ) or getattr(self.report_dispatcher, "report_generator", None)
            html_tpls = getattr(generator, "html_templates", None)
            if html_tpls and hasattr(html_tpls, "get_available_templates"):
                templates = html_tpls.get_available_templates()
            else:
                from ..reporting.templates import HTMLTemplates

                cfg_mgr = getattr(
                    self.analysis_service, "config_manager", None
                ) or getattr(self.report_dispatcher, "config_manager", None)
                tpl_mgr = HTMLTemplates(cfg_mgr)
                templates = tpl_mgr.get_available_templates()
            return json_response({"status": "ok", "data": templates})
        except Exception as e:
            logger.error(f"获取模板列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_stream_events(self) -> Any:
        """SSE 实时推送任务生命周期事件"""
        q = self.active_task_manager.subscribe()

        async def sse_generator():
            try:
                # 首次连接发送当前活跃任务快照
                active = self.active_task_manager.get_active_tasks()
                initial_event = json.dumps(
                    {"event": "initial_state", "data": active}, ensure_ascii=False
                )
                yield f"data: {initial_event}\n\n"

                while True:
                    event_str = await q.get()
                    yield f"data: {event_str}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                self.active_task_manager.unsubscribe(q)

        return stream_response(sse_generator())

    async def api_get_plugin_logs(self) -> Any:
        """获取群分析专属日志列表"""
        try:
            limit = (
                int(request.query.get("limit", 100))
                if request and hasattr(request, "query")
                else 100
            )
            offset = (
                int(request.query.get("offset", 0))
                if request and hasattr(request, "query")
                else 0
            )
            level = (
                request.query.get("level")
                if request and hasattr(request, "query")
                else None
            )
            trace_id = (
                request.query.get("trace_id")
                if request and hasattr(request, "query")
                else None
            )
            tag = (
                request.query.get("tag")
                if request and hasattr(request, "query")
                else None
            )
            search = (
                request.query.get("search")
                if request and hasattr(request, "query")
                else None
            )

            from ..logging.plugin_log_buffer import global_log_buffer

            items, total = global_log_buffer.query(
                limit=limit,
                offset=offset,
                level=level,
                trace_id=trace_id,
                tag=tag,
                search=search,
            )
            tags = [
                {"key": t[0], "label": t[1]} for t in global_log_buffer.TAG_PATTERNS
            ]
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "items": items,
                        "total": total,
                        "available_tags": tags,
                    },
                }
            )
        except Exception as e:
            logger.error(f"查询插件日志异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_trace_logs(self, trace_id: str) -> Any:
        """获取指定 TraceID 的专属执行日志"""
        try:
            from ..logging.plugin_log_buffer import global_log_buffer

            logs = global_log_buffer.get_trace_logs(trace_id)
            return json_response({"status": "ok", "data": logs})
        except Exception as e:
            logger.error(f"查询 Trace 日志异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_plugin_logs(self) -> Any:
        """清空内存中的插件日志"""
        try:
            from ..logging.plugin_log_buffer import global_log_buffer

            global_log_buffer.clear()
            return json_response({"status": "ok", "message": "Logs cleared"})
        except Exception as e:
            logger.error(f"清空插件日志异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_config(self) -> Any:
        """获取插件当前配置数据与完整 Schema 结构定义"""
        try:
            cfg_mgr = getattr(self.analysis_service, "config_manager", None) or getattr(
                self.report_dispatcher, "config_manager", None
            )
            config_dict = {}
            if cfg_mgr and hasattr(cfg_mgr, "config"):
                raw_cfg = cfg_mgr.config
                if hasattr(raw_cfg, "items"):
                    config_dict = {str(k): v for k, v in raw_cfg.items()}
                elif isinstance(raw_cfg, dict):
                    config_dict = dict(raw_cfg)

            # 读取插件根目录下的 _conf_schema.json
            plugin_root = Path(__file__).resolve().parents[3]
            schema_file = plugin_root / "_conf_schema.json"
            if not schema_file.exists():
                for candidate in [
                    Path.cwd() / "_conf_schema.json",
                    Path(__file__).resolve().parents[2] / "_conf_schema.json",
                    Path(__file__).resolve().parents[1] / "_conf_schema.json",
                ]:
                    if candidate.exists():
                        schema_file = candidate
                        break

            schema_dict = {}
            if schema_file.exists():
                try:
                    schema_dict = json.loads(schema_file.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"读取 _conf_schema.json 失败: {e}")

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "config": config_dict,
                        "schema": schema_dict,
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取配置信息异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_save_config(self) -> Any:
        """保存并更新插件配置"""
        try:
            body = await request.json() if hasattr(request, "json") else {}
            new_config = body.get("config") if isinstance(body, dict) else None
            if not isinstance(new_config, dict):
                return error_response("缺少有效的 config 配置数据", status_code=400)

            cfg_mgr = getattr(self.analysis_service, "config_manager", None) or getattr(
                self.report_dispatcher, "config_manager", None
            )
            config_obj = getattr(cfg_mgr, "config", None) if cfg_mgr else None
            if config_obj is None:
                return error_response("配置管理器未初始化", status_code=500)

            plugin_root = Path(__file__).resolve().parents[3]

            # 自动清洗并迁移历史中残存的 Base64 图片或不合规路径为合规的 files/... 物理文件
            def _cleanse_reference_images(val: Any) -> Any:
                if isinstance(val, list):
                    cleaned = []
                    for item in val:
                        if isinstance(item, dict):
                            cleaned_item = _cleanse_reference_images(item)
                            if isinstance(cleaned_item, dict):
                                if (
                                    "__template_key" not in cleaned_item
                                    or not cleaned_item["__template_key"]
                                ):
                                    cleaned_item["__template_key"] = "character"
                            cleaned.append(cleaned_item)
                        elif isinstance(item, str):
                            folder = _config_key_to_folder(
                                "daily_comic.comic_characters.templates.character.reference_images"
                            )
                            if item.startswith("data:image/"):
                                try:
                                    _, b64 = item.split(",", 1)
                                    file_bytes = base64.b64decode(b64)
                                    ts = int(time.time() * 1000)
                                    filename = f"{ts}_migrated_image.png"
                                    for d in [
                                        Path.cwd()
                                        / "data"
                                        / "plugin_data"
                                        / PLUGIN_NAME
                                        / "files"
                                        / Path(folder),
                                        plugin_root / "files" / Path(folder),
                                    ]:
                                        d.mkdir(parents=True, exist_ok=True)
                                        (d / filename).write_bytes(file_bytes)
                                    cleaned.append(f"files/{folder}/{filename}")
                                except Exception:
                                    pass
                            elif item.startswith("files/"):
                                expected_prefix = f"files/{folder}/"
                                if item.startswith(expected_prefix):
                                    cleaned.append(item.strip())
                                else:
                                    clean_name = Path(item).name
                                    cleaned.append(f"files/{folder}/{clean_name}")
                            elif item.strip():
                                cleaned.append(item.strip())
                        else:
                            cleaned.append(item)
                    return cleaned
                elif isinstance(val, dict):
                    return {k: _cleanse_reference_images(v) for k, v in val.items()}
                return val

            new_config = _cleanse_reference_images(new_config)

            # 更新 AstrBotConfig 字典
            for k, v in new_config.items():
                config_obj[k] = v

            # 持久化保存
            if hasattr(config_obj, "save_config"):
                try:
                    config_obj.save_config()
                except TypeError:
                    config_obj.save_config()

            logger.info("WebUI 配置中心已更新并保存插件配置。")
            return json_response(
                {
                    "status": "ok",
                    "message": "配置已成功保存并持久化生效",
                    "data": dict(config_obj),
                }
            )
        except Exception as e:
            logger.error(f"保存配置异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_upload_config_file(self) -> Any:
        """上传插件配置所需的文件/参考图，并存入合规的 files/{folder}/ 物理路径"""
        try:
            body: dict[str, Any] = {}
            if hasattr(request, "json"):
                try:
                    parsed_body = await request.json(default={})
                    if isinstance(parsed_body, dict):
                        body = parsed_body
                except Exception:
                    body = {}

            config_key = ""
            if (
                hasattr(request, "query")
                and request.query
                and request.query.get("config_key")
            ):
                config_key = request.query.get("config_key")
            elif body.get("config_key"):
                config_key = str(body.get("config_key"))

            if not config_key or config_key == "reference_images":
                config_key = (
                    "daily_comic.comic_characters.templates.character.reference_images"
                )

            folder = _config_key_to_folder(config_key)

            # 优先使用 AstrBot 官方的标准 plugin_data 目录，与 AstrBot 原生保持 100% 一致
            target_dirs: list[Path] = []
            try:
                from astrbot.api.star import StarTools

                data_dir = StarTools.get_data_dir(PLUGIN_NAME)
                if data_dir:
                    target_dirs.append(data_dir / "files" / Path(folder))
            except Exception:
                pass

            target_dirs.append(
                Path.cwd()
                / "data"
                / "plugin_data"
                / PLUGIN_NAME
                / "files"
                / Path(folder)
            )
            plugin_root = Path(__file__).resolve().parents[3]
            target_dirs.append(plugin_root / "files" / Path(folder))

            for d in target_dirs:
                d.mkdir(parents=True, exist_ok=True)

            saved_paths: list[str] = []

            # 1. 尝试从 multipart 上传中读取
            if hasattr(request, "files"):
                try:
                    uploaded_files = await request.files()
                    for key in uploaded_files.keys():
                        for f in uploaded_files.getlist(key):
                            orig_name = (
                                getattr(f, "filename", "") or "uploaded_image.png"
                            )
                            clean_name = re.sub(r"[^\w\.\-]", "_", orig_name)
                            ts = int(time.time() * 1000)
                            final_name = f"{ts}_{clean_name}"
                            file_bytes = await f.read()
                            if file_bytes:
                                for d in target_dirs:
                                    (d / final_name).write_bytes(file_bytes)
                                saved_paths.append(f"files/{folder}/{final_name}")
                except Exception:
                    pass

            # 2. 尝试从 JSON (包含 Base64 或 Data URL) 中解析
            if not saved_paths and body:
                raw_data = (
                    body.get("file_data") or body.get("data") or body.get("base64")
                )
                file_name = body.get("filename") or "upload.png"
                clean_name = re.sub(r"[^\w\.\-]", "_", file_name)
                if raw_data and isinstance(raw_data, str):
                    if raw_data.startswith("data:"):
                        _, b64 = raw_data.split(",", 1)
                    else:
                        b64 = raw_data
                    file_bytes = base64.b64decode(b64)
                    ts = int(time.time() * 1000)
                    final_name = f"{ts}_{clean_name}"
                    for d in target_dirs:
                        (d / final_name).write_bytes(file_bytes)
                    saved_paths.append(f"files/{folder}/{final_name}")

            if not saved_paths:
                return error_response("未检测到有效的文件数据", status_code=400)

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "path": saved_paths[0],
                        "paths": saved_paths,
                        "folder": folder,
                    },
                }
            )
        except Exception as e:
            logger.error(f"上传配置文件异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_config_file_content(self) -> Any:
        """获取配置中的文件（如角色参考图）内容用于 WebUI 在线缩略图展示"""
        try:
            rel_path = ""
            if hasattr(request, "query") and request.query:
                rel_path = request.query.get("path", "").strip()

            if not rel_path and hasattr(request, "json"):
                try:
                    body = await request.json(default={})
                    if isinstance(body, dict):
                        rel_path = str(body.get("path") or "").strip()
                except Exception:
                    pass

            if not rel_path:
                return error_response("Missing path parameter", status_code=400)

            # 搜索候选目录
            search_roots: list[Path] = []
            try:
                from astrbot.api.star import StarTools

                data_dir = StarTools.get_data_dir(PLUGIN_NAME)
                if data_dir:
                    search_roots.append(data_dir)
            except Exception:
                pass

            search_roots.append(Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME)
            plugin_root = Path(__file__).resolve().parents[3]
            search_roots.append(plugin_root)
            search_roots.append(Path.cwd() / "data" / "plugins" / PLUGIN_NAME)

            target_file: Path | None = None
            clean_rel = rel_path.lstrip("/\\")
            for root in search_roots:
                cand = (root / clean_rel).resolve()
                if cand.is_file() and cand.exists():
                    target_file = cand
                    break

            if not target_file:
                # 尝试纯文件名在 files/ 下模糊搜索
                filename = Path(clean_rel).name
                for root in search_roots:
                    files_dir = root / "files"
                    if files_dir.exists():
                        for match in files_dir.rglob(filename):
                            if match.is_file():
                                target_file = match
                                break
                    if target_file:
                        break

            if not target_file or not target_file.is_file():
                return error_response(f"File {rel_path} not found", status_code=404)

            ext = target_file.suffix.lower().lstrip(".")
            mime_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            with open(target_file, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "path": rel_path,
                        "filename": target_file.name,
                        "data_url": f"data:{mime_type};base64,{b64_content}",
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取配置文件内容异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
