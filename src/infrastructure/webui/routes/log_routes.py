"""
WebUI 日志与 SSE 实时事件流路由 (Log & Stream Routes)
处理任务实时进度推送 (SSE)、插件专属运行日志筛选、Trace 日志查询与日志清空。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from ....utils.logger import logger
from ...logging.plugin_log_buffer import global_log_buffer
from ..web_compat import (
    WebApiResponse,
    error_response,
    json_response,
    request,
    stream_response,
)

if TYPE_CHECKING:
    from ..active_task_manager import ActiveTaskManager


class LogRoutes:
    """日志与 SSE 事件流 Web API 路由处理器。"""

    def __init__(self, active_task_manager: ActiveTaskManager) -> None:
        self.active_task_manager = active_task_manager

    async def api_stream_events(self) -> WebApiResponse:
        """SSE 实时推送任务生命周期事件"""
        q = self.active_task_manager.subscribe()

        async def sse_generator():
            try:
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

    async def api_get_plugin_logs(self) -> WebApiResponse:
        """获取群分析专属日志列表"""
        try:
            limit = int(request.query.get("limit", 100))
            offset = int(request.query.get("offset", 0))
            level = request.query.get("level")
            trace_id = request.query.get("trace_id")
            tag = request.query.get("tag")
            search = request.query.get("search")

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

    async def api_get_trace_logs(self, trace_id: str) -> WebApiResponse:
        """获取指定 TraceID 的专属执行日志"""
        try:
            logs = global_log_buffer.get_trace_logs(trace_id)
            return json_response({"status": "ok", "data": logs})
        except Exception as e:
            logger.error(f"查询 Trace 日志异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_plugin_logs(self) -> WebApiResponse:
        """清空内存中的插件日志"""
        try:
            global_log_buffer.clear()
            return json_response({"status": "ok", "message": "Logs cleared"})
        except Exception as e:
            logger.error(f"清空插件日志异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
