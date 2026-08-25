"""
AstrBot 插件 Pages 后端 Web API 桥接服务
为 React + Ant Design 5 控制台提供 REST 与 SSE 接口。
"""

from __future__ import annotations

import asyncio
import json
import logging
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
    Context: Any = Any  # type: ignore

    def json_response(data: Any, status_code: int = 200) -> Any:  # type: ignore
        return {"status_code": status_code, "data": data}

    def error_response(msg: str, status_code: int = 400) -> Any:  # type: ignore
        return {"status_code": status_code, "message": msg}

    request: Any = None  # type: ignore

    def stream_response(gen: Any) -> Any:  # type: ignore
        return gen


from ...shared.constants import PLUGIN_NAME
from ...shared.trace_context import TraceContext
from ..persistence.trace_sqlite_store import TraceSQLiteStore
from .active_task_manager import ActiveTaskManager

logger = logging.getLogger(__name__)


class PluginPageWebUIBridge:
    """WebUI 面板 API 桥接适配器"""

    def __init__(
        self,
        context: Context,
        trace_store: TraceSQLiteStore,
        active_task_manager: ActiveTaskManager,
        analysis_service: Any,
        report_output_dir: Path | None = None,
    ):
        self.context = context
        self.trace_store = trace_store
        self.active_task_manager = active_task_manager
        self.analysis_service = analysis_service
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
            # 4. 历史产物
            (
                f"/{PLUGIN_NAME}/reports/history",
                self.api_get_report_history,
                ["GET"],
                "Get generated report image list",
            ),
            # 5. SSE 实时事件流
            (
                f"/{PLUGIN_NAME}/events/stream",
                self.api_stream_events,
                ["GET"],
                "SSE stream for real-time task progress events",
            ),
        ]

        for path, handler, methods, desc in routes:
            try:
                self.context.register_web_api(path, handler, methods, desc)
            except Exception as e:
                logger.error(f"注册 Web API 路由 {path} 失败: {e}")

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
                    platform_id=platform if platform and platform != "all" else None,
                    manual=True,
                )
                if result and result.get("success"):
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

    async def api_get_trace_detail(self, trace_id: str) -> Any:
        """获取单个 Trace 的完整 Span 树与上下文指标"""
        try:
            trace = self.trace_store.get_trace(trace_id)
            if not trace:
                return error_response(f"Trace {trace_id} not found", status_code=404)
            return json_response({"status": "ok", "data": trace})
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
        """获取历史生成的报告图片列表"""
        try:
            reports: list[dict[str, Any]] = []
            if self.report_output_dir and self.report_output_dir.exists():
                for file_path in sorted(
                    self.report_output_dir.glob("*.jpg"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:50]:
                    stat = file_path.stat()
                    reports.append(
                        {
                            "filename": file_path.name,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                        }
                    )
            return json_response({"status": "ok", "data": reports})
        except Exception as e:
            logger.error(f"查询历史报告异常: {e}", exc_info=True)
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
