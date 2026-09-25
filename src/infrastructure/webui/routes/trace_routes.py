"""
WebUI 链路观测与指标路由 (Trace & Metrics Routes)
处理执行链路检索、详情追溯、Span 树展开、KPI 指标概览、时序趋势图表及基础维度元数据查询。
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import TYPE_CHECKING

from ....shared.constants import AnalysisStage
from ....shared.trace_context import TraceContext
from ....utils.logger import logger
from ...platform.factory import PlatformAdapterFactory
from ..web_compat import (
    Context,
    WebApiResponse,
    error_response,
    json_response,
    request,
)

if TYPE_CHECKING:
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...persistence.trace_sqlite_store import TraceSQLiteStore
    from ..active_task_manager import ActiveTaskManager


class TraceRoutes:
    """链路观测与指标 Web API 路由处理器。"""

    def __init__(
        self,
        context: Context,
        trace_store: TraceSQLiteStore,
        active_task_manager: ActiveTaskManager,
        analysis_service: AnalysisApplicationService | None = None,
    ) -> None:
        self.context = context
        self.trace_store = trace_store
        self.active_task_manager = active_task_manager
        self.analysis_service = analysis_service

    async def api_list_traces(self) -> WebApiResponse:
        """分页与条件筛选 Trace 列表"""
        try:
            limit = int(request.query.get("limit", 20))
            offset = int(request.query.get("offset", 0))
            group_id = request.query.get("group_id")
            status = request.query.get("status")
            trigger_type = request.query.get("trigger_type")
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
                trigger_type=trigger_type,
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

    async def api_get_distinct_groups(self) -> WebApiResponse:
        """获取所有有历史分析记录的群组列表（用于下拉快速筛选）"""
        try:
            groups = self.trace_store.get_distinct_groups()
            return json_response({"status": "ok", "data": groups})
        except Exception as e:
            logger.error(f"查询群组列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_platforms(self) -> WebApiResponse:
        """获取当前 AstrBot 中已注册并就绪的所有聊天平台列表（基于 AstrBot 原生 PlatformMetadata）"""
        try:
            platforms: list[dict[str, object]] = []
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
                            if (p_id in (p_type, display_name))
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

    async def api_get_providers(self) -> WebApiResponse:
        """获取当前 AstrBot 中已就绪的所有 LLM Provider 列表"""
        try:
            providers: list[dict[str, object]] = []
            seen_ids = set()
            provider_getter = getattr(self.context, "get_all_providers", None)
            if not callable(provider_getter):
                provider_mgr = getattr(self.context, "provider_manager", None)
                provider_getter = getattr(provider_mgr, "get_all_providers", None)

            if callable(provider_getter):
                raw_list = provider_getter()
                provider_list: list[object] = (
                    list(raw_list) if isinstance(raw_list, Iterable) else []
                )
                for p in provider_list:
                    try:
                        meta_getter = getattr(p, "meta", None)
                        meta = meta_getter() if callable(meta_getter) else None
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

    async def api_get_personas(self) -> WebApiResponse:
        """获取当前 AstrBot 中配置的所有人格 (Persona) 列表"""
        try:
            personas: list[dict[str, object]] = []
            seen_ids = set()
            pm = getattr(self.context, "persona_manager", None)
            if pm:
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

    async def api_get_trace_detail(self, trace_id: str) -> WebApiResponse:
        """获取单个 Trace 的完整 Span 树与上下文指标"""
        try:
            trace = self.trace_store.get_trace(trace_id)
            if trace:
                return json_response({"status": "ok", "data": trace})

            active_trace = TraceContext.get_active_trace(trace_id)
            task_info = None
            for t in self.active_task_manager.get_active_tasks():
                if t.get("task_id") == trace_id:
                    task_info = t
                    break

            if active_trace or task_info:
                task_started_at = task_info.get("started_at") if task_info else None
                if active_trace:
                    started_at = active_trace.started_at
                elif isinstance(task_started_at, (int, float)):
                    started_at = float(task_started_at)
                else:
                    started_at = time.time()

                current_stage = (
                    active_trace.current_stage
                    if (active_trace and active_trace.current_stage)
                    else (
                        str(task_info.get("current_stage", ""))
                        if task_info
                        else AnalysisStage.FETCH_MESSAGES.value
                    )
                )
                spans = list(active_trace._spans) if active_trace else []
                context_metrics = (
                    active_trace._context_metrics if active_trace else None
                )
                token_usage = active_trace._token_usage if active_trace else None

                group_id_val = (active_trace.group_id if active_trace else "") or (
                    str(task_info.get("group_id", "")) if task_info else ""
                )
                group_name_val = (active_trace.group_name if active_trace else "") or (
                    str(task_info.get("group_name", "")) if task_info else ""
                )
                platform_val = (active_trace.platform if active_trace else "") or (
                    str(task_info.get("platform", "")) if task_info else ""
                )
                trigger_type_val = (
                    active_trace.trigger_type if active_trace else ""
                ) or (
                    str(task_info.get("trigger_type", "manual")) if task_info else "manual"
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

    async def api_get_metrics_summary(self) -> WebApiResponse:
        """获取顶部 KPI 与 Token 统计概览"""
        try:
            summary = self.trace_store.get_metrics_summary()
            return json_response({"status": "ok", "data": summary})
        except Exception as e:
            logger.error(f"获取指标概览异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_analytics_trends(self) -> WebApiResponse:
        """获取时序趋势统计（支持按小时或按天细粒度切换，并包含服务商与模型统计）"""
        try:
            granularity = request.query.get("granularity", "day")
            range_count_str = request.query.get("range_count")
            range_count = (
                int(range_count_str)
                if range_count_str
                else (48 if granularity == "hour" else 14)
            )

            trends_data = self.trace_store.get_analytics_trends(
                granularity=granularity, range_count=range_count
            )
            return json_response({"status": "ok", "data": trends_data})
        except Exception as e:
            logger.error(f"获取趋势图表数据异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
