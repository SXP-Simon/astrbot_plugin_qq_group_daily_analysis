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

from ...infrastructure.persistence.checkpoint_store import CheckpointStore
from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from ...infrastructure.reporting.dispatcher import ReportDispatcher
from ...shared.constants import AnalysisStage, TaskStatus
from ...utils.logger import logger
from .analysis_application_service import AnalysisApplicationService


class CrashRecoveryService:
    """开机崩溃任务对账与自愈恢复服务"""

    def __init__(
        self,
        trace_store: TraceSQLiteStore | None,
        checkpoint_store: CheckpointStore | None,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None,
    ) -> None:
        self.trace_store = trace_store
        self.checkpoint_store = checkpoint_store
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher

    async def recover_crashed_tasks(self) -> dict[str, int]:
        """开机扫描并执行未完成任务自愈对账。

        Returns:
            dict[str, int]: 自愈结果统计字典，包含 recovered, archived, aborted。
        """
        if not self.trace_store or not self.analysis_service:
            return {"recovered": 0, "archived": 0, "aborted": 0}

        try:
            crashed_traces = self.trace_store.get_crashed_traces_on_startup()
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
            trace_id = trace_dict.get("trace_id", "")
            if not trace_id:
                continue

            group_id = str(trace_dict.get("group_id", "") or "")
            platform_id = str(trace_dict.get("platform", "") or "")
            trigger_type = str(trace_dict.get("trigger_type", "") or "manual")
            started_at = trace_dict.get("started_at")
            task_date_str = (
                dt.datetime.fromtimestamp(started_at).strftime("%Y-%m-%d")
                if started_at
                else today_date_str
            )

            has_clean_cp = (
                self.checkpoint_store.get_checkpoint(
                    group_id, task_date_str, AnalysisStage.CLEAN_MESSAGES.value
                )
                if self.checkpoint_store
                else None
            )
            has_llm_cp = (
                self.checkpoint_store.get_checkpoint(
                    group_id, task_date_str, AnalysisStage.LLM_ANALYSIS.value
                )
                if self.checkpoint_store
                else None
            )

            if not has_clean_cp and not has_llm_cp:
                logger.info(
                    f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 无前置快照，标记为已回收"
                )
                self.trace_store.save_trace(
                    {
                        "trace_id": trace_id,
                        "status": TaskStatus.ABORTED.value,
                        "error_stage": "CRASH_RECOVERY",
                        "error_message": "AstrBot/容器在任务执行期间异常终止，无可用快照，开机已自动回收",
                        "completed_at": dt.datetime.now().timestamp(),
                    }
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
                    actual_platform_id = result.get("platform_id") or platform_id

                    if is_same_day:
                        if (
                            trigger_type in ("manual", "auto", "scheduled")
                            and self.report_dispatcher
                            and analysis_result
                        ):
                            await self.report_dispatcher.dispatch(
                                group_id, analysis_result, actual_platform_id
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
                else:
                    err_msg = (
                        result.get("error") or result.get("reason") or "未知原因"
                        if isinstance(result, dict)
                        else "未知原因"
                    )
                    logger.warning(
                        f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 恢复失败: {err_msg}"
                    )
                    self.trace_store.save_trace(
                        {
                            "trace_id": trace_id,
                            "status": TaskStatus.FAILED.value,
                            "error_stage": "CRASH_RECOVERY",
                            "error_message": f"开机自愈失败: {err_msg}",
                            "completed_at": dt.datetime.now().timestamp(),
                        }
                    )
                    aborted_count += 1

            except Exception as exc:
                logger.error(
                    f"[CrashRecovery] 任务 {trace_id} (群 {group_id}) 自愈过程异常: {exc}",
                    exc_info=True,
                )
                self.trace_store.save_trace(
                    {
                        "trace_id": trace_id,
                        "status": TaskStatus.FAILED.value,
                        "error_stage": "CRASH_RECOVERY",
                        "error_message": f"开机自愈异常: {exc}",
                        "completed_at": dt.datetime.now().timestamp(),
                    }
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
