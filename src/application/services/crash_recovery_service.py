"""
开机崩溃对账与任务自愈恢复服务 (Crash Recovery & Auto Resume on Startup)

负责在插件启动且平台适配器就绪后，扫描上次因异常终止而遗留的 running 任务。
根据 Checkpoint 快照与时效性策略进行断点续跑：
- 当天内任务（未跨天）：从快照恢复计算并投递群聊；
- 跨天任务（隔天或更久）：从快照恢复计算并静默归档（跳过群聊投递）；
- 无快照任务：标记为 aborted 回收。
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, cast

from ...domain.value_objects.task_event import TaskEvent
from ...domain.value_objects.task_status import TaskStatus
from ...shared.constants import PROCESS_BOOT_ID, AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .task_lifecycle_service import TaskLifecycleService

if TYPE_CHECKING:
    from ...domain.value_objects import AnalysisResultPayload
    from ...infrastructure.persistence.checkpoint_store import CheckpointStore
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ...infrastructure.reporting.dispatcher import ReportDispatcher
    from .analysis_application_service import AnalysisApplicationService


class CrashRecoveryService:
    """开机崩溃任务对账与自愈恢复服务"""

    trace_store: TraceSQLiteStore | None
    checkpoint_store: CheckpointStore | None
    analysis_service: AnalysisApplicationService | None
    report_dispatcher: ReportDispatcher | None
    lifecycle_service: TaskLifecycleService | None

    def __init__(
        self,
        trace_store: TraceSQLiteStore | None,
        checkpoint_store: CheckpointStore | None,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None,
        lifecycle_service: TaskLifecycleService | None = None,
    ) -> None:
        self.trace_store = trace_store
        self.checkpoint_store = checkpoint_store
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.lifecycle_service = lifecycle_service or (
            TaskLifecycleService(trace_store) if trace_store else None
        )

    async def recover_crashed_tasks(
        self, current_boot_id: str | None = None
    ) -> dict[str, int]:
        """开机扫描并执行未完成任务自愈对账。

        Args:
            current_boot_id: 当前进程实例凭据。默认取全局 PROCESS_BOOT_ID。
                             仅扫描非当前进程（真正因断电/崩溃死亡）的历史遗留任务。

        Returns:
            dict[str, int]: 自愈结果统计字典，包含 recovered, archived, aborted。
        """
        if not self.trace_store or not self.analysis_service:
            return {"recovered": 0, "archived": 0, "aborted": 0}

        effective_boot_id = current_boot_id or PROCESS_BOOT_ID

        try:
            crashed_traces = self.trace_store.get_crashed_traces_on_startup(
                current_boot_id=effective_boot_id
            )
        except Exception as e:
            logger.error(f"[CrashRecovery] 读取开机遗留崩溃任务失败: {e}")
            return {"recovered": 0, "archived": 0, "aborted": 0}

        if not crashed_traces:
            return {"recovered": 0, "archived": 0, "aborted": 0}

        logger.info(
            f"[CrashRecovery] 开机对账发现 {len(crashed_traces)} 条异常中断任务，开始自愈恢复..."
        )

        today_date_str = dt.datetime.now().strftime("%Y-%m-%d")
        recovered_count = 0
        archived_count = 0
        aborted_count = 0

        for trace_dict in crashed_traces:
            trace_id = str(trace_dict.get("trace_id", "") or "")
            if not trace_id:
                continue

            group_id = str(trace_dict.get("group_id", "") or "")
            platform_id = str(trace_dict.get("platform", "") or "")
            trigger_type = str(trace_dict.get("trigger_type", "") or "manual")
            started_at = trace_dict.get("started_at")
            started_at_ts = (
                float(started_at) if isinstance(started_at, (int, float)) else None
            )
            task_date_str = (
                dt.datetime.fromtimestamp(started_at_ts).strftime("%Y-%m-%d")
                if started_at_ts
                else today_date_str
            )

            has_clean_cp = (
                self.checkpoint_store.get_checkpoint(
                    group_id,
                    task_date_str,
                    AnalysisStage.CLEAN_MESSAGES.value,
                    trace_id=trace_id,
                )
                if self.checkpoint_store
                else None
            )
            has_llm_cp = (
                self.checkpoint_store.get_checkpoint(
                    group_id,
                    task_date_str,
                    AnalysisStage.LLM_ANALYSIS.value,
                    trace_id=trace_id,
                )
                if self.checkpoint_store
                else None
            )

            if not has_clean_cp and not has_llm_cp:
                logger.info(
                    f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 无前置快照，标记为已回收"
                )
                self._transition_trace(
                    trace_id,
                    TaskEvent.ABORT,
                    error_stage="CRASH_RECOVERY",
                    error_message="AstrBot/容器在任务执行期间异常终止，无可用快照，开机已自动回收",
                )
                aborted_count += 1
                continue

            is_same_day = task_date_str == today_date_str

            try:
                result = await self.analysis_service.resume_analysis(
                    trace_id=trace_id,
                    group_id=group_id,
                    platform_id=platform_id or None,
                    date_str=task_date_str,
                )

                if result and result.get("success"):
                    analysis_result = result.get("analysis_result")
                    actual_platform_id = (
                        str(result.get("platform_id") or platform_id or "") or None
                    )

                    if is_same_day:
                        if (
                            trigger_type in ("manual", "auto", "scheduled")
                            and self.report_dispatcher
                            and isinstance(analysis_result, dict)
                        ):
                            await self.report_dispatcher.dispatch(
                                group_id,
                                cast("AnalysisResultPayload", analysis_result),
                                actual_platform_id,
                            )
                            logger.info(
                                f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 当天自愈恢复成功并已投递群聊"
                            )
                        else:
                            logger.info(
                                f"[CrashRecovery] 任务 {trace_id} (群 {group_id}, 类型: {trigger_type}) 当天自愈恢复成功"
                            )
                        recovered_count += 1
                    else:
                        logger.info(
                            f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 跨天自愈恢复成功，已静默归档历史记录（跳过群投递）"
                        )
                        archived_count += 1

                    self._transition_trace(trace_id, TaskEvent.SUCCEED)
                else:
                    err_msg = result.get("error") or result.get("reason") or "未知原因"
                    logger.warning(
                        f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 恢复失败: {err_msg}"
                    )
                    self._transition_trace(
                        trace_id,
                        TaskEvent.FAIL,
                        error_stage="CRASH_RECOVERY",
                        error_message=f"开机自愈失败: {err_msg}",
                    )
                    aborted_count += 1

            except Exception as exc:
                logger.error(
                    f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 自愈过程异常: {exc}",
                    exc_info=True,
                )
                self._transition_trace(
                    trace_id,
                    TaskEvent.FAIL,
                    error_stage="CRASH_RECOVERY",
                    error_message=f"开机自愈异常: {exc}",
                )
                aborted_count += 1

        logger.info(
            f"[CrashRecovery] 开机对账完成：恢复并投递 {recovered_count} 条，静默归档 {archived_count} 条，回收/失败 {aborted_count} 条"
        )
        return {
            "recovered": recovered_count,
            "archived": archived_count,
            "aborted": aborted_count,
        }

    def _transition_trace(
        self,
        trace_id: str,
        event: TaskEvent,
        error_stage: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """通过活跃 Trace 或生命周期用例收敛恢复任务。

        Args:
            trace_id: 任务追踪标识。
            event: 恢复过程产生的生命周期事件。
            error_stage: 失败或回收阶段。
            error_message: 失败或回收原因。
        """
        trace = TraceContext.get_active_trace(trace_id)
        try:
            if trace and trace.status == TaskStatus.RUNNING.value:
                trace.finish(
                    event=event,
                    error_stage=error_stage,
                    error_message=error_message,
                )
            elif self.lifecycle_service:
                self.lifecycle_service.transition(
                    trace_id,
                    event,
                    error_stage=error_stage,
                    error_message=error_message,
                )
        except (KeyError, ValueError, RuntimeError) as exc:
            logger.info(f"[CrashRecovery] 任务 {trace_id} 状态未改变: {exc}")
