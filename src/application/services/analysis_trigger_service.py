"""分析触发应用服务 - 应用层 (LLM Tool 专用)

实现“按需触发群聊日常分析”核心用例。
负责管理员鉴权、群排他锁防重入、配置交集过滤、异步任务派发、ON_DEMAND Checkpoint 隔离与静默执行控制。
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, cast

from ...domain.repositories.platform_adapter_repository import PlatformAdapterProtocol
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...domain.value_objects import AnalysisResultPayload
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ...infrastructure.reporting.dispatcher import ReportDispatcher
    from ...infrastructure.webui.active_task_manager import ActiveTaskManager
    from .analysis_application_service import AnalysisApplicationService
    from .report_query_service import ReportQueryService


class AnalysisTriggerService:
    """分析触发应用服务。"""

    def __init__(
        self,
        config_manager: ConfigManager,
        analysis_service: AnalysisApplicationService,
        report_query_service: ReportQueryService,
        active_task_manager: ActiveTaskManager | None = None,
        trace_store: TraceSQLiteStore | None = None,
        report_dispatcher: ReportDispatcher | None = None,
    ) -> None:
        """初始化触发服务。

        Args:
            config_manager: 配置管理器。
            analysis_service: 核心分析用例服务。
            report_query_service: 报告查询服务（用于群号解析）。
            active_task_manager: 活跃任务管理器。
            trace_store: 追踪仓储。
            report_dispatcher: 报告分发器（用于自动向群内发送渲染长图报告）。
        """
        self.config_manager = config_manager
        self.analysis_service = analysis_service
        self.report_query_service = report_query_service
        self.active_task_manager = active_task_manager
        self.trace_store = trace_store
        self.report_dispatcher = report_dispatcher
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._pending_groups: set[str] = set()

    async def trigger_analysis(
        self,
        event: AstrMessageEvent,
        analysis_sections: str = "全部",
        days: int = 1,
        group: str = "",
        render_to_chat: bool = True,
    ) -> str:
        """执行按需分析任务派发。

        Args:
            event: 当前消息事件。
            analysis_sections: 请求分析的模块。
            days: 分析回溯天数。
            group: 目标群聊标识（群号/群名/空）。
            render_to_chat: 分析完成后是否直接渲染并向群聊发送长图报告，默认 True。

        Returns:
            str: 格式化的任务受理状态回执或拦截提示。
        """
        # 1. 严格权限鉴权：必须是管理员或群主
        if not self._check_admin_permission(event):
            sender_id = getattr(event, "get_sender_id", lambda: "未知")()
            return (
                f"[权限不足] 即时触发群分析属于高资源消耗操作，仅群管理员或 Bot 管理员具备调用权限 "
                f"(您的 ID: {sender_id})。普通群成员请直接询问历史报告（例如：“今天群里聊了什么”）。"
            )

        # 2. 智能群目标解析
        current_event_group_id = (
            str(event.get_group_id())
            if hasattr(event, "get_group_id") and event.get_group_id()
            else None
        )
        target_group_id, matched_name, candidates = (
            self.report_query_service.resolve_target_group(
                group_input=group,
                current_event_group_id=current_event_group_id,
            )
        )

        if candidates:
            cand_lines = [
                f"{i}. {c.get('group_name', '未知')} ({c.get('group_id')})"
                for i, c in enumerate(candidates, 1)
            ]
            return (
                f"检测到多个名称匹配 '{group}' 的群聊，请指明具体群号或准确名称重试：\n"
                + "\n".join(cand_lines)
            )

        if not target_group_id:
            if not group and not current_event_group_id:
                return (
                    "[提示] 当前处于私聊会话中，请在提问时指明目标群聊名称或群号"
                    "（例如：“更新开发交流群的日报”）。"
                )
            return f"未能定位到群聊 '{group}'。建议直接提供纯数字群号重新触发。"

        # 3. 群白名单/黑名单校验
        if not self.config_manager.is_group_allowed(target_group_id):
            return f"群聊 {matched_name or target_group_id} 未在群分析启用名单中，已拒绝触发分析。"

        # 4. 并发排他锁防重入与原子预占
        if (
            target_group_id in self._pending_groups
            or self.analysis_service.is_group_running(target_group_id, "daily")
        ):
            return (
                f"[任务冲突] 群聊 {matched_name or target_group_id} ({target_group_id}) "
                f"当前已有日常分析任务正在执行中，请勿重复触发！待后台完成后可直接查询结果。"
            )

        # 5. 分析天数边界约束 (1 ~ 7 天)
        try:
            days_int = max(1, min(int(days), 7))
        except (ValueError, TypeError):
            days_int = 1

        # 6. 计算配置交集
        requested_modules, effective_sections, skipped_notes = (
            self._resolve_effective_sections(analysis_sections)
        )
        if not effective_sections:
            return (
                f"[无法执行] 您请求的分析模块 ({', '.join(requested_modules)}) "
                f"在插件配置中均已被关闭，没有可执行的分析子任务。"
            )

        # 7. Checkpoint 隔离：若只执行部分模块，使用 ON_DEMAND_ANALYSIS
        is_partial = len(effective_sections) < 4 or days_int != int(
            self.config_manager.get_analysis_days() or 1
        )
        target_stage_name = (
            AnalysisStage.ON_DEMAND_ANALYSIS.value
            if is_partial
            else AnalysisStage.LLM_ANALYSIS.value
        )

        # 8. 预占群锁、派发异步任务并生成 TraceID
        self._pending_groups.add(target_group_id)
        trace_id = TraceContext.generate(prefix="tool_trigger", group_name=matched_name)
        platform_id = str(event.get_platform_id() or "")

        task = asyncio.create_task(
            self._run_async_analysis(
                group_id=target_group_id,
                group_name=matched_name,
                platform_id=platform_id,
                days=days_int,
                effective_sections=effective_sections,
                target_stage_name=target_stage_name,
                trace_id=trace_id,
                render_to_chat=render_to_chat,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # 9. 500ms 内向宿主 LLM 返回任务受理凭证回执
        sec_names = ", ".join(effective_sections)
        skipped_text = (
            f"\n- 跳过模块: {', '.join(skipped_notes)}" if skipped_notes else ""
        )
        if render_to_chat:
            dispatch_note = (
                "1. 本任务正在后台执行分析，计算完成后将**自动渲染并直接将报告长图发送至本群**。\n"
                "2. 请明确告知用户分析流水线已在后台启动，报告长图稍后（预计一分钟左右）会自动发到群里，请用户耐心稍候，切勿虚构假分析结果。"
            )
        else:
            dispatch_note = (
                "1. 本任务在后台静默执行并将结果持久化入库，**不会**向群聊发送长图。\n"
                "2. 请明确告知用户分析已在后台静默计算中，待稍后（预计一分钟左右）通过询问或调用查询工具即可查验最新结果，切勿虚构假分析结果。"
            )

        return (
            f"[分析任务已成功在后台启动]\n"
            f"- 目标群聊: {matched_name or target_group_id} ({target_group_id})\n"
            f"- 任务编号: {trace_id}\n"
            f"- 执行模块: {sec_names}{skipped_text}\n"
            f"- 分析跨度: 最近 {days_int} 天\n"
            f"- 预计耗时: 约 1 分钟左右\n\n"
            f"【系统重要提示】\n"
            f"{dispatch_note}"
        )

    async def _run_async_analysis(
        self,
        group_id: str,
        group_name: str,
        platform_id: str,
        days: int,
        effective_sections: set[str],
        target_stage_name: str,
        trace_id: str,
        render_to_chat: bool = True,
    ) -> None:
        """后台异步分析执行流程（绑定生命周期管理、静默落库与自动发图）。"""
        trace = TraceContext.set(
            trace_id=trace_id,
            group_id=group_id,
            group_name=group_name,
            platform=platform_id,
            trigger_type="llm_tool",
        )
        if self.trace_store:
            try:
                self.trace_store.save_trace(trace.to_dict())
            except Exception:
                pass

        try:
            if self.active_task_manager:
                await self.active_task_manager.register_task(
                    task_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform_id,
                    trigger_type="llm_tool",
                    current_stage=AnalysisStage.FETCH_MESSAGES,
                    asyncio_task=asyncio.current_task(),
                )

            logger.info(
                f"[LLM Tool Trigger] 异步任务启动: 群 {group_id}, trace={trace_id}, sections={effective_sections}, render_to_chat={render_to_chat}"
            )
            res = await self.analysis_service.execute_daily_analysis(
                group_id=group_id,
                platform_id=platform_id or None,
                manual=True,
                days=days,
                analysis_sections=effective_sections,
                checkpoint_stage_name=target_stage_name,
            )
            success = bool(res.get("success", False))
            if success:
                # 若需要向群聊派发报告长图，调用报告分发器
                if render_to_chat and self.report_dispatcher:
                    raw_analysis = res.get("analysis_result")
                    analysis_result = cast(
                        "AnalysisResultPayload",
                        raw_analysis if isinstance(raw_analysis, dict) else {},
                    )
                    adapter = res.get("adapter")
                    dispatch_platform_id = (
                        adapter.platform_id
                        if isinstance(adapter, PlatformAdapterProtocol)
                        else (platform_id or None)
                    )
                    logger.info(
                        f"[LLM Tool Trigger] 分析完成，开始渲染并派发报告长图: 群 {group_id}, trace={trace_id}"
                    )
                    try:
                        await self.report_dispatcher.dispatch(
                            group_id=group_id,
                            analysis_result=analysis_result,
                            platform_id=dispatch_platform_id,
                        )
                        logger.info(
                            f"[LLM Tool Trigger] 报告长图已成功派发至群 {group_id}"
                        )
                    except Exception as dispatch_err:
                        logger.error(
                            f"[LLM Tool Trigger] 报告派发异常: 群 {group_id}, 错误: {dispatch_err}",
                            exc_info=True,
                        )

                trace.finish(status="succeeded")
                logger.info(
                    f"[LLM Tool Trigger] 异步任务执行成功: 群 {group_id}, trace={trace_id}"
                )
            else:
                reason = str(res.get("reason", "unknown"))
                trace.finish(
                    status="failed",
                    error_stage=target_stage_name,
                    error_message=f"分析失败: {reason}",
                )
                logger.warning(
                    f"[LLM Tool Trigger] 异步任务未完成: 群 {group_id}, 原因: {reason}"
                )
        except Exception as exc:
            trace.finish(
                status="failed",
                error_stage=target_stage_name,
                error_message=str(exc),
            )
            logger.error(
                f"[LLM Tool Trigger] 异步任务异常: 群 {group_id}, 错误: {exc}",
                exc_info=True,
            )
        finally:
            self._pending_groups.discard(group_id)
            if self.trace_store:
                try:
                    self.trace_store.save_trace(trace.to_dict())
                except Exception:
                    pass
            if self.active_task_manager:
                try:
                    await self.active_task_manager.finish_task(trace_id)
                except Exception:
                    pass

    def _check_admin_permission(self, event: AstrMessageEvent) -> bool:
        """检查调用者是否具备管理员权限。"""
        # 1. AstrBot 核心事件权限
        if hasattr(event, "is_admin") and event.is_admin():
            return True
        if getattr(event, "role", "") == "admin":
            return True

        # 2. 插件配置白名单
        sender_id = str(getattr(event, "get_sender_id", lambda: "")() or "").strip()
        admin_users = [
            str(u).strip()
            for u in self.config_manager._get_group("basic").get("admin_users", [])
        ]
        return bool(sender_id and sender_id in admin_users)

    def _resolve_effective_sections(
        self, analysis_sections_input: str
    ) -> tuple[list[str], set[str], list[str]]:
        """计算实际执行的分析模块与被配置关闭的跳过模块。"""
        raw = str(analysis_sections_input or "").strip()
        all_modules = ["话题", "用户称号", "金句", "聊天质量分析"]

        if not raw or raw in {"全部", "all", "ALL"}:
            requested = all_modules
        else:
            tokens = re.split(r"[,，、| +]+", raw)
            requested = []
            for tok in tokens:
                t = tok.strip()
                if not t:
                    continue
                if t in {"话题", "topic", "topics", "主题"} and "话题" not in requested:
                    requested.append("话题")
                elif (
                    t in {"金句", "quote", "quotes", "语录"} and "金句" not in requested
                ):
                    requested.append("金句")
                elif (
                    t in {"用户称号", "称号", "头衔", "user_titles"}
                    and "用户称号" not in requested
                ):
                    requested.append("用户称号")
                elif (
                    t in {"聊天质量分析", "质量", "质量分析", "氛围"}
                    and "聊天质量分析" not in requested
                ):
                    requested.append("聊天质量分析")
            if not requested:
                requested = all_modules

        effective = set()
        skipped = []

        cfg = self.config_manager
        for m in requested:
            if m == "话题":
                if cfg.get_topic_analysis_enabled():
                    effective.add("topics")
                else:
                    skipped.append("话题")
            elif m == "用户称号":
                if cfg.get_user_title_analysis_enabled():
                    effective.add("user_titles")
                else:
                    skipped.append("用户称号")
            elif m == "金句":
                if cfg.get_golden_quote_analysis_enabled():
                    effective.add("golden_quotes")
                else:
                    skipped.append("金句")
            elif m == "聊天质量分析":
                if cfg.get_chat_quality_analysis_enabled():
                    effective.add("chat_quality_review")
                else:
                    skipped.append("聊天质量分析")

        return requested, effective, skipped
