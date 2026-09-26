"""
WebUI 任务管理路由 (Task Routes)
处理群分析任务的手动触发、取消、断点续跑及活跃任务查询。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from ....shared.constants import AnalysisStage
from ....shared.trace_context import TraceContext
from ....utils.logger import logger
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ....domain.value_objects import AnalysisResultPayload
    from ...persistence.trace_sqlite_store import TraceSQLiteStore
    from ...reporting.dispatcher import ReportDispatcher
    from ..active_task_manager import ActiveTaskManager


class TaskRoutes:
    """任务管理 Web API 路由处理器。"""

    trace_store: TraceSQLiteStore
    active_task_manager: ActiveTaskManager
    analysis_service: AnalysisApplicationService | None
    report_dispatcher: ReportDispatcher | None

    def __init__(
        self,
        trace_store: TraceSQLiteStore,
        active_task_manager: ActiveTaskManager,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None = None,
    ) -> None:
        self.trace_store = trace_store
        self.active_task_manager = active_task_manager
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher

    async def api_get_active_tasks(self) -> WebApiResponse:
        """获取当前正在执行的任务列表"""
        tasks = self.active_task_manager.get_active_tasks()
        return json_response({"status": "ok", "data": tasks})

    async def api_cancel_task(self) -> WebApiResponse:
        """手动取消正在执行的任务"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            task_id = (
                str(payload.get("task_id", "")).strip()
                or request.query.get("task_id", "").strip()
            )
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

    async def api_trigger_task(self) -> WebApiResponse:
        """从 Web 界面手动触发群分析任务"""
        if not self.analysis_service:
            return error_response("分析服务未初始化", status_code=500)

        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            if not group_id:
                return error_response("group_id is required", status_code=400)

            # 防重入即时拦截：若该群已有分析任务正在执行，直接拒绝重复触发并返回友好提示
            if self.analysis_service.is_group_running(group_id, "daily"):
                return error_response(
                    f"群 {group_id} 的日常分析任务正在执行中，请勿重复触发",
                    status_code=409,
                )

            group_name = str(
                payload.get("group_name")
                or request.query.get("group_name")
                or f"群 {group_id}"
            ).strip()
            platform = str(
                payload.get("platform") or request.query.get("platform") or "qq"
            ).strip()

            trace_id = TraceContext.generate("web_manual", group_name)

            provider_id_raw = (
                payload.get("provider_id")
                if payload.get("provider_id") is not None
                else request.query.get("provider_id")
            )
            provider_id = (
                str(provider_id_raw).strip()
                if provider_id_raw is not None
                and str(provider_id_raw).strip()
                and str(provider_id_raw).strip() != "auto"
                else None
            )

            template_name_raw = (
                payload.get("template_name")
                or payload.get("template")
                or request.query.get("template_name")
                or request.query.get("template")
            )
            template_name = (
                str(template_name_raw).strip()
                if template_name_raw is not None
                and str(template_name_raw).strip()
                and str(template_name_raw).strip() != "auto"
                else None
            )

            asyncio_task = asyncio.create_task(
                self._run_triggered_task(
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
                trigger_type="web_ui",
                current_stage=AnalysisStage.FETCH_MESSAGES,
                asyncio_task=asyncio_task,
            )

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "trace_id": trace_id,
                        "group_id": group_id,
                        "template_name": template_name,
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
        template_name: str | None = None,
    ) -> None:
        """后台异步执行触发任务"""
        if not self.analysis_service:
            return
        trace_ctx = TraceContext.set(
            trace_id=trace_id,
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            trigger_type="web_ui",
        )
        if provider_id:
            trace_ctx.metadata["override_provider_id"] = str(provider_id)
        if template_name and template_name != "auto":
            trace_ctx.metadata["override_template_name"] = str(template_name)
        try:
            bot_mgr = self.analysis_service.bot_manager
            target_platform: str | None = None

            if platform and bot_mgr.get_adapter(platform):
                target_platform = str(platform).strip()
            else:
                adapters = bot_mgr.get_all_adapters()
                if len(adapters) == 1:
                    target_platform = next(iter(adapters.keys()))
                elif len(adapters) > 1 and group_id:
                    for p_id, adp in adapters.items():
                        try:
                            if await adp.get_group_info(str(group_id)):
                                target_platform = bot_mgr.get_adapter_platform_id(
                                    adp
                                ) or str(p_id)
                                break
                        except Exception:
                            continue

            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id,
                platform_id=target_platform,
                manual=True,
            )
            if result and result.get("success"):
                analysis_result = result.get("analysis_result")
                adapter = result.get("adapter")
                dispatch_platform_id = (
                    (bot_mgr.get_adapter_platform_id(adapter) if adapter else "")
                    or target_platform
                    or ""
                )
                trace_ctx.platform = str(dispatch_platform_id)
                if self.report_dispatcher and isinstance(analysis_result, dict):
                    try:
                        with trace_ctx.span(
                            AnalysisStage.DISPATCH_REPORT,
                            {
                                "platform": dispatch_platform_id or "auto",
                                "group_id": group_id,
                            },
                        ):
                            await self.report_dispatcher.dispatch(
                                group_id,
                                cast("AnalysisResultPayload", analysis_result),
                                dispatch_platform_id,
                            )
                    except Exception as dispatch_err:
                        logger.error(
                            f"WebUI 报告发送异常 (群 {group_id}): {dispatch_err}",
                            exc_info=True,
                        )

                if trace_ctx.status == "running":
                    trace_ctx.finish(status="succeeded")
            else:
                if trace_ctx.status == "running":
                    trace_ctx.finish(
                        status="failed",
                        error_message=str(result.get("reason", "unknown"))
                        if result
                        else "unknown",
                    )
        except asyncio.CancelledError:
            logger.info(f"触发分析任务已取消: {trace_id}")
            if trace_ctx.status == "running":
                trace_ctx.finish(status="cancelled", error_message="Task cancelled")
        except Exception as e:
            if trace_ctx.status == "running":
                trace_ctx.finish(status="failed", error_message=str(e))
            logger.error(f"任务 {trace_id} 执行出错: {e}", exc_info=True)
        finally:
            await self.active_task_manager.finish_task(trace_id)

    async def api_resume_task(self, trace_id: str) -> WebApiResponse:
        """从 Checkpoint 幂等恢复并重试任务"""
        if not self.analysis_service:
            return error_response("分析服务未初始化", status_code=500)

        try:
            trace_record = self.trace_store.get_trace(trace_id)
            if not trace_record:
                return error_response(f"Trace {trace_id} not found", status_code=404)

            group_id = str(trace_record.get("group_id", ""))
            group_name = str(trace_record.get("group_name", ""))
            platform = str(trace_record.get("platform", ""))

            try:
                payload = await request.json()
            except Exception:
                payload = {}

            provider_id_raw = (
                payload.get("provider_id")
                if payload.get("provider_id") is not None
                else request.query.get("provider_id")
            )
            provider_id = (
                str(provider_id_raw).strip()
                if provider_id_raw is not None
                and str(provider_id_raw).strip()
                and str(provider_id_raw).strip() != "auto"
                else None
            )
            template_name_raw = (
                payload.get("template_name")
                or payload.get("template")
                or request.query.get("template_name")
                or request.query.get("template")
            )
            template_name = (
                str(template_name_raw).strip()
                if template_name_raw is not None
                and str(template_name_raw).strip()
                and str(template_name_raw).strip() != "auto"
                else None
            )

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
                current_stage=AnalysisStage.LLM_ANALYSIS,
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
        if not self.analysis_service:
            return
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
            bot_mgr = self.analysis_service.bot_manager
            target_platform: str | None = None

            if platform and bot_mgr.get_adapter(platform):
                target_platform = str(platform).strip()
            else:
                adapters = bot_mgr.get_all_adapters()
                if len(adapters) == 1:
                    target_platform = next(iter(adapters.keys()))
                elif len(adapters) > 1 and group_id:
                    for p_id, adp in adapters.items():
                        try:
                            if await adp.get_group_info(str(group_id)):
                                target_platform = bot_mgr.get_adapter_platform_id(
                                    adp
                                ) or str(p_id)
                                break
                        except Exception:
                            continue

            result = await self.analysis_service.resume_analysis(
                trace_id=trace_id,
                group_id=group_id,
                platform_id=target_platform,
                template_name=template_name,
            )
            if result and result.get("success"):
                if result.get("fallback_to_fresh_run"):
                    trace_ctx.metadata["fallback_to_fresh_run"] = True
                    trace_ctx.metadata["fallback_reason"] = str(
                        result.get(
                            "fallback_reason",
                            "checkpoint_missing_auto_refetched",
                        )
                    )
                    trace_ctx.metadata["resumed_from"] = str(
                        result.get("resumed_from", "fresh_run_fallback")
                    )
                analysis_result = result.get("analysis_result")
                adapter = result.get("adapter")
                dispatch_platform_id = (
                    (bot_mgr.get_adapter_platform_id(adapter) if adapter else "")
                    or target_platform
                    or ""
                )
                trace_ctx.platform = str(dispatch_platform_id)
                if self.report_dispatcher and isinstance(analysis_result, dict):
                    try:
                        with trace_ctx.span(
                            AnalysisStage.DISPATCH_REPORT,
                            {
                                "platform": dispatch_platform_id or "auto",
                                "group_id": group_id,
                            },
                        ):
                            await self.report_dispatcher.dispatch(
                                group_id,
                                cast("AnalysisResultPayload", analysis_result),
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
                        error_message=str(result.get("reason", "unknown"))
                        if result
                        else "unknown",
                    )
        except Exception as e:
            if trace_ctx.status == "running":
                trace_ctx.finish(status="failed", error_message=str(e))
            logger.error(f"续跑任务 {trace_id} 执行出错: {e}", exc_info=True)
        finally:
            await self.active_task_manager.finish_task(trace_id)
