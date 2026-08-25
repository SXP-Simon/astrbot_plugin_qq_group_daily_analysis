"""
AstrBot 插件 Pages 后端 Web API 桥接服务
为 React + Ant Design 5 控制台提供 REST 与 SSE 接口。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Any

try:
    from astrbot.api.star import Context
    from astrbot.api.web import (
        error_response,
        json_response,
        request,
        stream_response,
    )
except (ImportError, AttributeError):

    class Context:  # type: ignore
        pass

    def json_response(data: Any, status_code: int = 200) -> Any:  # type: ignore
        return {"status_code": status_code, "data": data}

    def error_response(msg: str, status_code: int = 400) -> Any:  # type: ignore
        return {"status_code": status_code, "message": msg}

    request: Any = None  # type: ignore

    def stream_response(gen: Any) -> Any:  # type: ignore
        return gen


from ...shared.constants import PLUGIN_NAME
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..persistence.trace_sqlite_store import TraceSQLiteStore
from ..platform.factory import PlatformAdapterFactory
from .active_task_manager import ActiveTaskManager


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
            # 3. 统计指标 (dsh-context & KPI)
            (
                f"/{PLUGIN_NAME}/metrics/summary",
                self.api_get_metrics_summary,
                ["GET"],
                "Get KPI and token metrics summary",
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
        ]

        for path, handler, methods, desc in routes:
            try:
                self.context.register_web_api(path, handler, methods, desc)
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
            payload = await request.json(default={})
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
            payload = await request.json(default={})
            group_id = str(payload.get("group_id", "")).strip()
            if not group_id:
                return error_response("group_id is required", status_code=400)

            group_name = str(payload.get("group_name", f"群 {group_id}"))
            platform = str(payload.get("platform", "qq"))

            # 生成语义化 TraceID
            trace_id = TraceContext.generate("web_manual", group_name)

            # 启动后台异步任务
            asyncio_task = asyncio.create_task(
                self._run_triggered_task(
                    trace_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform,
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
        self, trace_id: str, group_id: str, group_name: str, platform: str
    ) -> None:
        """后台异步执行触发任务"""
        trace_ctx = TraceContext.set(
            trace_id=trace_id,
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            trigger_type="web_ui",
        )
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
                            with trace_ctx.span("DISPATCH_REPORT"):
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

    async def api_get_trace_detail(self, trace_id: str) -> Any:
        """获取单个 Trace 的完整 Span 树与上下文指标

        优先查 SQLite 持久化记录；若未入库（任务尚在运行中），则回退到
        ActiveTaskManager 的内存活跃快照，让前端可以展示运行中的实时状态。
        """
        try:
            trace = self.trace_store.get_trace(trace_id)
            if trace:
                return json_response({"status": "ok", "data": trace})

            # 回退：从内存活跃任务列表中查找运行中的任务快照
            for task_info in self.active_task_manager.get_active_tasks():
                if task_info.get("task_id") == trace_id:
                    return json_response(
                        {
                            "status": "ok",
                            "data": {
                                "trace_id": trace_id,
                                "group_id": task_info.get("group_id", ""),
                                "group_name": task_info.get("group_name", ""),
                                "platform": task_info.get("platform", ""),
                                "trigger_type": task_info.get("trigger_type", "manual"),
                                "status": "running",
                                "started_at": task_info.get("started_at"),
                                "completed_at": None,
                                "duration_ms": round(
                                    task_info.get("duration_s", 0) * 1000
                                ),
                                "error_stage": None,
                                "error_message": None,
                                "stack_trace": None,
                                "extra": {},
                                "spans": [],
                                "context_metrics": None,
                                "token_usage": None,
                                "current_stage": task_info.get("current_stage", ""),
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
                    is_html = file_path.suffix.lower() in {".html", ".htm"}
                    trace_id = ""
                    # 1. 尝试从嵌入式文件名中提取群号与 trace_id
                    m = re.match(
                        r"^(?:report|群聊分析报告)_(.+?)_\d{8}_\d{6}_([a-zA-Z0-9_\-]+)\.(?:jpg|jpeg|png|webp|html|htm)$",
                        file_path.name,
                        re.IGNORECASE,
                    )
                    if m:
                        group_id = m.group(1)
                        trace_id = m.group(2)
                    else:
                        m = re.match(
                            r"^(?:report|群聊分析报告)_(.+?)_\d{8}_\d{6}\.(?:jpg|jpeg|png|webp|html|htm)$",
                            file_path.name,
                            re.IGNORECASE,
                        )
                        if not m:
                            m = re.match(
                                r"^(?:report|群聊分析报告)_(.+?)_\d{4}-\d{2}-\d{2}_([a-zA-Z0-9_\-]+)\.(?:jpg|jpeg|png|webp|html|htm)$",
                                file_path.name,
                                re.IGNORECASE,
                            )
                        if not m:
                            m = re.match(
                                r"^(?:report|群聊分析报告)_(.+?)_\d+\.(?:jpg|jpeg|png|webp|html|htm)$",
                                file_path.name,
                                re.IGNORECASE,
                            )
                        if not m:
                            m = re.match(
                                r"^(?:report|群聊分析报告)_(.+?)\.(?:jpg|jpeg|png|webp|html|htm)$",
                                file_path.name,
                                re.IGNORECASE,
                            )
                        group_id = m.group(1) if m else ""

                    # 2. 若文件名未显式包含 trace_id，则从 TraceContext / 历史存储的 report_files 映射中精准匹配
                    if not trace_id:
                        trace_id = report_trace_map.get(file_path.name, "")

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
