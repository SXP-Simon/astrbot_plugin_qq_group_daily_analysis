"""分析产物恢复与重绘服务模块

负责群聊分析 Checkpoint 断点续跑（Resume）以及历史分析产物重新渲染（Rerender）。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time as time_mod
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.api.star import StarTools

from ...domain.value_objects import TokenUsage
from ...shared.constants import PLUGIN_NAME, AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .analysis_serializer import AnalysisResultSerializer
from .pipeline_context import PipelineContext

if TYPE_CHECKING:
    from ...domain.repositories.analysis_repository import IAnalysisProvider
    from ...domain.repositories.config_repository import IConfigProvider
    from ...domain.repositories.persistence_repository import ICheckpointStore
    from ...domain.repositories.report_repository import IReportGenerator
    from ...domain.services.statistics_service import StatisticsService
    from .task_guard import TaskGuard


class AnalysisRecoveryService:
    """分析恢复与重绘服务 - 提供幂等断点续跑与按模板重新渲染。"""

    def __init__(
        self,
        config_manager: IConfigProvider,
        bot_manager: Any,
        history_manager: Any,
        report_generator: IReportGenerator,
        llm_analyzer: IAnalysisProvider,
        statistics_service: StatisticsService,
        task_guard: TaskGuard,
        checkpoint_store: ICheckpointStore | None = None,
        html_render: Any | None = None,
    ):
        """初始化恢复与重绘服务。

        Args:
            config_manager: 配置提供者。
            bot_manager: 机器人管理器。
            history_manager: 历史持久化管理器。
            report_generator: 报表生成器。
            llm_analyzer: LLM 分析器。
            statistics_service: 统计领域服务。
            task_guard: 任务排他锁守卫。
            checkpoint_store: 检查点持久化仓储。
            html_render: HTML 渲染回调。
        """
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.history_manager = history_manager
        self.report_generator = report_generator
        self.llm_analyzer = llm_analyzer
        self.statistics_service = statistics_service
        self.task_guard = task_guard
        self.checkpoint_store = checkpoint_store
        self.html_render = html_render

    async def rerender_report(
        self,
        group_id: str,
        date_str: str,
        template_name: str,
        platform_id: str | None = None,
        render_format: str = "image",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """根据历史分析产物重新渲染指定模板风格的报告。

        Args:
            group_id: 群组 ID。
            date_str: 分析日期（YYYY-MM-DD）。
            template_name: 模板主题名称。
            platform_id: 平台实例标识。
            render_format: 输出格式（'image' 或 'html'）。
            trace_id: 追踪 Trace ID。

        Returns:
            包含渲染结果与生成文件路径的字典。
        """
        analysis_result = None
        if self.history_manager:
            try:
                hist_data = await self.history_manager.get_analysis(group_id, date_str)
                if hist_data and isinstance(hist_data, dict):
                    analysis_result = hist_data
            except Exception as e:
                logger.debug(f"从 HistoryManager 获取分析记录异常: {e}")

        if not analysis_result and self.checkpoint_store:
            cached_data = self.checkpoint_store.get_checkpoint(
                group_id, date_str, "LLM_ANALYSIS", trace_id=trace_id or ""
            )
            if cached_data:
                analysis_result = AnalysisResultSerializer.deserialize(cached_data)

        if not analysis_result:
            return {
                "success": False,
                "reason": f"未找到群 {group_id} 在 {date_str} 的分析产物记录",
            }

        reports_dir = (
            getattr(self.report_generator, "data_dir", None)
            or StarTools.get_data_dir(PLUGIN_NAME)
        ) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

        if render_format == "html":
            filename = (
                f"report_{group_id}_{ts_str}_{trace_id}_{template_name}.html"
                if trace_id
                else f"report_{group_id}_{ts_str}_{template_name}.html"
            )
            dest = reports_dir / filename
            html_path, _ = await self.report_generator.generate_html_report(
                analysis_result=analysis_result,
                group_id=group_id,
                template_theme=template_name,
                custom_filename=filename,
                trace_id=trace_id,
            )
            if not html_path or not Path(html_path).exists():
                prep_func = getattr(self.report_generator, "_prepare_render_data", None)
                if callable(prep_func):
                    prep_res = prep_func(analysis_result)
                    render_data = (
                        await prep_res if asyncio.iscoroutine(prep_res) else prep_res
                    )
                else:
                    render_data = analysis_result
                html_tpls = getattr(self.report_generator, "html_templates", None)
                if html_tpls and hasattr(html_tpls, "render_template"):
                    render_kwargs: dict[str, Any] = (
                        dict(render_data) if isinstance(render_data, Mapping) else {}
                    )
                    html_content = html_tpls.render_template(
                        "html_template.html",
                        template_theme=template_name,
                        **render_kwargs,
                    )
                    dest.write_text(html_content, encoding="utf-8")

            if trace_id:
                from ...shared.trace_context import _global_trace_store

                if _global_trace_store is not None:
                    try:
                        trace_data = _global_trace_store.get_trace(trace_id)
                        if trace_data:
                            extra = trace_data.get("extra") or {}
                            rfiles = extra.setdefault("report_files", [])
                            if not any(rf.get("filename") == filename for rf in rfiles):
                                rfiles.append(
                                    {
                                        "filename": filename,
                                        "path": str(dest.resolve()),
                                        "format": "html",
                                        "template": template_name,
                                        "size_bytes": dest.stat().st_size
                                        if dest.exists()
                                        else 0,
                                        "created_at": time_mod.time(),
                                    }
                                )
                            trace_data["extra"] = extra
                            _global_trace_store.save_trace(trace_data)
                    except Exception:
                        pass

            return {
                "success": True,
                "filename": filename,
                "report_path": str(dest),
                "is_html": True,
                "from_checkpoint": True,
                "trace_id": trace_id,
            }
        else:
            image_res = await self.report_generator.generate_image_report(
                analysis_result=analysis_result,
                group_id=group_id,
                html_render_func=self.html_render,
                template_theme=template_name,
            )
            image_url = image_res[0] if isinstance(image_res, tuple) else image_res
            filename = (
                f"report_{group_id}_{ts_str}_{trace_id}_{template_name}.jpg"
                if trace_id
                else f"report_{group_id}_{ts_str}_{template_name}.jpg"
            )
            dest = reports_dir / filename
            if image_url and Path(image_url).exists():
                import shutil

                shutil.copy2(image_url, dest)
            elif image_url and image_url.startswith("base64://"):
                import base64

                data = base64.b64decode(image_url[9:])
                dest.write_bytes(data)

            if trace_id:
                from ...shared.trace_context import _global_trace_store

                if _global_trace_store is not None:
                    try:
                        trace_data = _global_trace_store.get_trace(trace_id)
                        if trace_data:
                            extra = trace_data.get("extra") or {}
                            rfiles = extra.setdefault("report_files", [])
                            if not any(rf.get("filename") == filename for rf in rfiles):
                                rfiles.append(
                                    {
                                        "filename": filename,
                                        "path": str(dest.resolve()),
                                        "format": "image",
                                        "template": template_name,
                                        "size_bytes": dest.stat().st_size
                                        if dest.exists()
                                        else 0,
                                        "created_at": time_mod.time(),
                                    }
                                )
                            trace_data["extra"] = extra
                            _global_trace_store.save_trace(trace_data)
                    except Exception:
                        pass

            return {
                "success": True,
                "filename": filename,
                "report_path": str(dest),
                "image_url": image_url,
                "is_html": False,
                "from_checkpoint": True,
                "trace_id": trace_id,
            }

    async def resume_analysis(
        self,
        trace_id: str,
        group_id: str,
        platform_id: str | None = None,
        date_str: str | None = None,
        template_name: str | None = None,
        fallback_daily_func: Any | None = None,
    ) -> dict[str, Any]:
        """从上一次 Checkpoint 检查点执行幂等断点续跑。

        Args:
            trace_id: 待恢复的 Trace ID。
            group_id: 群组 ID。
            platform_id: 平台标识。
            date_str: 日期字符串（缺省为今日）。
            template_name: 模板主题名称。
            fallback_daily_func: 未命中快照时回退执行全量分析的异步函数。

        Returns:
            包含执行产物与恢复阶段标识的字典。

        Raises:
            ValueError: 缺少平台适配器时抛出。
        """
        if not date_str:
            date_str = dt.datetime.now().strftime("%Y-%m-%d")

        trace = TraceContext.current()
        if not trace:
            trace = TraceContext.get_or_create(
                trace_id=trace_id,
                group_id=str(group_id),
                platform=platform_id or "",
                trigger_type="resume",
                auto_bind=True,
            )
        if template_name and template_name != "auto":
            trace.metadata["override_template_name"] = str(template_name)

        topic_enabled = self.config_manager.get_topic_analysis_enabled()
        user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
        golden_quote_enabled = self.config_manager.get_golden_quote_analysis_enabled()
        chat_quality_enabled = self.config_manager.get_chat_quality_analysis_enabled()

        pipeline = PipelineContext(
            trace=trace,
            checkpoint_store=self.checkpoint_store,
            group_id=group_id,
            date_str=date_str,
        )

        cached_llm = (
            self.checkpoint_store.get_checkpoint(
                group_id,
                date_str,
                AnalysisStage.LLM_ANALYSIS.value,
                trace_id=trace_id or "",
            )
            if self.checkpoint_store
            else None
        )
        if not cached_llm:
            try:
                hist_data = await self.history_manager.get_analysis(group_id, date_str)
                if hist_data and isinstance(hist_data, dict):
                    cached_llm = AnalysisResultSerializer.serialize(hist_data)
            except Exception:
                cached_llm = None

        if cached_llm:
            cached_result = AnalysisResultSerializer.deserialize(cached_llm)
            cached_topics = cached_result.get("topics", [])
            cached_titles = cached_result.get("user_titles", [])
            cached_stats = cached_result.get("statistics")
            cached_quotes = (
                getattr(cached_stats, "golden_quotes", []) if cached_stats else []
            )
            cached_quality = cached_result.get("chat_quality_review")

            has_required_topics = not topic_enabled or bool(cached_topics)
            has_required_titles = not user_title_enabled or bool(cached_titles)
            has_required_quotes = not golden_quote_enabled or bool(cached_quotes)
            has_required_quality = not chat_quality_enabled or bool(cached_quality)

            if (
                has_required_topics
                and has_required_titles
                and has_required_quotes
                and has_required_quality
            ):
                logger.info(
                    f"群 {group_id} 命中完整的 LLM 分析产物快照，跳过消息拉取与 LLM 分析，直接进入报告排版与分发"
                )
                async with self.task_guard.group_lock(group_id, "daily"):
                    adapter = self.bot_manager.get_adapter(platform_id)
                    pipeline.restore_checkpoint_span(
                        AnalysisStage.LLM_ANALYSIS,
                        {"direct_render": True},
                    )
                    return {
                        "success": True,
                        "analysis_result": cached_result,
                        "messages_count": (
                            getattr(cached_stats, "message_count", 0)
                            if cached_stats
                            else 0
                        ),
                        "adapter": adapter,
                        "group_id": group_id,
                        "platform_id": getattr(adapter, "platform_id", platform_id),
                        "resumed_from": AnalysisStage.LLM_ANALYSIS.value,
                        "trace_id": trace_id,
                    }

        clean_checkpoint = (
            self.checkpoint_store.get_checkpoint(
                group_id,
                date_str,
                AnalysisStage.CLEAN_MESSAGES.value,
                trace_id=trace_id or "",
            )
            if self.checkpoint_store
            else None
        )

        if not clean_checkpoint:
            logger.info(f"未找到群 {group_id} 的前置清洗快照，回退到全量重新分析")
            if trace:
                trace.metadata["fallback_to_fresh_run"] = True
                trace.metadata["fallback_reason"] = "checkpoint_missing_auto_refetched"
                trace.metadata["resumed_from"] = "fresh_run_fallback"
            if fallback_daily_func:
                result = await fallback_daily_func(
                    group_id=group_id,
                    platform_id=platform_id,
                    manual=True,
                )
                if isinstance(result, dict):
                    result["fallback_to_fresh_run"] = True
                    result["fallback_reason"] = "checkpoint_missing_auto_refetched"
                    result["resumed_from"] = "fresh_run_fallback"
                return result
            return {"success": False, "reason": "checkpoint_missing"}

        logger.info(
            f"群 {group_id} 命中 Checkpoint 快照，跳过消息拉取与清洗，直接进入 LLM 幂等续跑"
        )
        async with self.task_guard.group_lock(group_id, "daily"):
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            stats_data = clean_checkpoint.get("statistics", {})
            deserialized = AnalysisResultSerializer.deserialize(
                {
                    "statistics": stats_data,
                    "user_analysis": clean_checkpoint.get("user_activity", {}),
                    "user_titles": clean_checkpoint.get("top_users", []),
                }
            )
            statistics = deserialized["statistics"]
            user_activity = deserialized.get("user_analysis", {})
            top_users = deserialized.get("user_titles", [])
            unified_messages = clean_checkpoint.get("unified_messages", [])

            pipeline.restore_checkpoint_span(AnalysisStage.CLEAN_MESSAGES)

            cached_result = (
                AnalysisResultSerializer.deserialize(cached_llm) if cached_llm else {}
            )

            topics = cached_result.get("topics", [])
            user_titles = cached_result.get("user_titles", [])
            cached_stats = cached_result.get("statistics")
            golden_quotes = (
                getattr(cached_stats, "golden_quotes", []) if cached_stats else []
            )
            chat_quality_review = cached_result.get("chat_quality_review")
            total_token_usage = (
                getattr(cached_stats, "token_usage", TokenUsage())
                if cached_stats
                else TokenUsage()
            )

            run_topic = topic_enabled and not bool(topics)
            run_user_title = user_title_enabled and not bool(user_titles)
            run_golden_quote = golden_quote_enabled and not bool(golden_quotes)
            run_chat_quality = chat_quality_enabled and not bool(chat_quality_review)

            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )
            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            if run_topic or run_user_title or run_golden_quote or run_chat_quality:
                async with pipeline.step(AnalysisStage.LLM_ANALYSIS) as step:
                    async with self.task_guard.llm_slot(group_id, "resume"):
                        (
                            new_topics,
                            new_user_titles,
                            new_golden_quotes,
                            new_tokens,
                            new_chat_quality,
                        ) = await self.llm_analyzer.analyze_all_concurrent(
                            legacy_messages,
                            user_activity,
                            umo=unified_msg_origin,
                            top_users=top_users,
                            topic_enabled=run_topic,
                            user_title_enabled=run_user_title,
                            golden_quote_enabled=run_golden_quote,
                            chat_quality_enabled=run_chat_quality,
                        )
                        if run_topic:
                            topics = new_topics
                        if run_user_title:
                            user_titles = new_user_titles
                        if run_golden_quote:
                            golden_quotes = new_golden_quotes
                        if run_chat_quality:
                            chat_quality_review = new_chat_quality

                        total_token_usage = TokenUsage(
                            prompt_tokens=total_token_usage.prompt_tokens
                            + new_tokens.prompt_tokens,
                            completion_tokens=total_token_usage.completion_tokens
                            + new_tokens.completion_tokens,
                            total_tokens=total_token_usage.total_tokens
                            + new_tokens.total_tokens,
                        )

                    enabled_count = sum(
                        [
                            bool(run_topic),
                            bool(run_user_title),
                            bool(run_golden_quote),
                            bool(run_chat_quality),
                        ]
                    )
                    success_count = sum(
                        [
                            bool(new_topics) if run_topic else False,
                            bool(new_user_titles) if run_user_title else False,
                            bool(new_golden_quotes) if run_golden_quote else False,
                            bool(new_chat_quality) if run_chat_quality else False,
                        ]
                    )

                    if enabled_count > 0 and success_count == 0:
                        step.mark_failed(
                            "续跑大模型文本分析所有启用的子任务均调用失败或重试耗尽，已中断后续任务"
                        )
                        if trace:
                            trace.metadata["has_warnings"] = False
                            trace.metadata["failure_stage"] = (
                                AnalysisStage.LLM_ANALYSIS.value
                            )
                        return {
                            "success": False,
                            "reason": "llm_analysis_failed",
                            "error": "大模型文本分析全部子任务失败，已中止续跑",
                        }
                    elif enabled_count > 0 and success_count < enabled_count:
                        step.mark_warning(
                            f"续跑大模型文本分析部分子任务未产出结果 ({success_count}/{enabled_count} 成功)"
                        )
                        if trace:
                            trace.metadata["has_warnings"] = True

            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            analysis_result = {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_activity,
                "chat_quality_review": chat_quality_review,
            }

            async with pipeline.step(
                AnalysisStage.SAVE_SUMMARY,
                save_checkpoint=True,
                serializer=AnalysisResultSerializer.serialize,
            ) as step:
                await self.history_manager.save_analysis(group_id, analysis_result)
                if self.checkpoint_store:
                    try:
                        cur_trace_id = trace.trace_id if trace else ""
                        self.checkpoint_store.save_checkpoint(
                            group_id=group_id,
                            date_str=date_str,
                            stage_name=AnalysisStage.LLM_ANALYSIS.value,
                            data=AnalysisResultSerializer.serialize(analysis_result),
                            trace_id=cur_trace_id,
                        )
                    except Exception as e:
                        logger.warning(f"保存分析 Checkpoint 失败: {e}")
                step.set_payload(
                    date=date_str,
                    topics_persisted=len(topics),
                    titles_persisted=len(user_titles),
                    checkpoint_saved=bool(self.checkpoint_store),
                )

            return {
                "success": True,
                "analysis_result": analysis_result,
                "messages_count": len(unified_messages),
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
                "resumed_from": AnalysisStage.CLEAN_MESSAGES.value,
                "trace_id": trace_id,
            }
