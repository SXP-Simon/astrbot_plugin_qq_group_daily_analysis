"""
群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 遵循整洁架构与领域驱动设计 (DDD)，支持跨平台与 WebUI 控制台。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star, StarTools

from .src.application.handlers.analysis_command_handler import (
    AnalysisCommandHandler,
)
from .src.application.handlers.comic_command_handler import ComicCommandHandler
from .src.application.handlers.settings_command_handler import (
    SettingsCommandHandler,
)
from .src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from .src.application.services.comic_application_service import ComicApplicationService
from .src.application.services.crash_recovery_service import CrashRecoveryService
from .src.application.services.message_processing_service import (
    MessageProcessingService,
)
from .src.application.services.template_command_service import (
    TemplateCommandService,
)
from .src.domain.services.analysis_domain_service import AnalysisDomainService
from .src.domain.services.incremental_merge_service import IncrementalMergeService
from .src.domain.services.statistics_service import StatisticsService
from .src.infrastructure.analysis.llm_analyzer import LLMAnalyzer
from .src.infrastructure.config.config_manager import ConfigManager
from .src.infrastructure.drawing.drawing_client import DrawingClient
from .src.infrastructure.messaging.message_sender import MessageSender
from .src.infrastructure.persistence.checkpoint_store import CheckpointStore
from .src.infrastructure.persistence.history_manager import HistoryManager
from .src.infrastructure.persistence.incremental_store import IncrementalStore
from .src.infrastructure.persistence.platform_group_registry import (
    PlatformGroupRegistry,
)
from .src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from .src.infrastructure.platform.bot_manager import BotManager
from .src.infrastructure.platform.template_preview import (
    TelegramTemplatePreviewHandler,
    TemplatePreviewRouter,
)
from .src.infrastructure.reporting.generators import ReportGenerator
from .src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from .src.infrastructure.visualization.activity_charts import ActivityVisualizer
from .src.infrastructure.webui.active_task_manager import ActiveTaskManager
from .src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge
from .src.shared.constants import PLUGIN_NAME
from .src.shared.trace_context import TraceContext
from .src.utils.logger import logger
from .src.utils.resilience import GlobalRateLimiter


def _resolve_settings_handler(plugin: Any) -> SettingsCommandHandler:
    handler = getattr(plugin, "settings_command_handler", None)
    if handler is not None:
        return handler
    return SettingsCommandHandler(
        config_manager=getattr(plugin, "config_manager", None),  # type: ignore
        template_command_service=getattr(plugin, "template_command_service", None),  # type: ignore
        template_preview_router=getattr(plugin, "template_preview_router", None),
        auto_scheduler=getattr(plugin, "auto_scheduler", None),
        incremental_store=getattr(plugin, "incremental_store", None),
        incremental_merge_service=getattr(plugin, "incremental_merge_service", None),
        bot_manager=getattr(plugin, "bot_manager", None),
        context=getattr(plugin, "context", None),
    )


def _resolve_comic_handler(plugin: Any) -> ComicCommandHandler:
    handler = getattr(plugin, "comic_command_handler", None)
    if handler is not None:
        return handler
    return ComicCommandHandler(
        config_manager=getattr(plugin, "config_manager", None),  # type: ignore
        bot_manager=getattr(plugin, "bot_manager", None),  # type: ignore
        comic_service=getattr(plugin, "comic_service", None),  # type: ignore
        analysis_service=getattr(plugin, "analysis_service", None),  # type: ignore
        active_task_manager=getattr(plugin, "active_task_manager", None),
        plugin_data_dir=getattr(plugin, "plugin_data_dir", None),
        plugin_instance=plugin,
    )


def _resolve_analysis_handler(plugin: Any) -> AnalysisCommandHandler:
    handler = getattr(plugin, "analysis_command_handler", None)
    if handler is not None:
        return handler
    plugin_data_dir = getattr(plugin, "plugin_data_dir", None)
    if plugin_data_dir is None:
        try:
            plugin_data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        except Exception:
            plugin_data_dir = Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME
    return AnalysisCommandHandler(
        config_manager=getattr(plugin, "config_manager", None),  # type: ignore
        bot_manager=getattr(plugin, "bot_manager", None),  # type: ignore
        analysis_service=getattr(plugin, "analysis_service", None),  # type: ignore
        report_generator=getattr(plugin, "report_generator", None),  # type: ignore
        html_render=getattr(plugin, "html_render", None),  # type: ignore
        active_task_manager=getattr(plugin, "active_task_manager", None),
        trace_store=getattr(plugin, "trace_store", None),
        message_sender=getattr(plugin, "message_sender", None),
        comic_handler=_resolve_comic_handler(plugin),
        plugin_data_dir=plugin_data_dir,
        plugin_instance=plugin,
    )


class GroupDailyAnalysis(Star):
    """群分析插件主类"""

    # ── 显式类型声明 (由 __init__ 初始化) ──
    config: AstrBotConfig
    config_manager: ConfigManager
    bot_manager: BotManager
    history_manager: HistoryManager
    report_generator: ReportGenerator
    html_render: Callable
    platform_group_registry: PlatformGroupRegistry
    statistics_service: StatisticsService
    analysis_domain_service: AnalysisDomainService
    llm_analyzer: LLMAnalyzer
    incremental_store: IncrementalStore
    incremental_merge_service: IncrementalMergeService
    analysis_service: AnalysisApplicationService
    message_processing_service: MessageProcessingService
    template_command_service: TemplateCommandService
    telegram_template_preview_handler: TelegramTemplatePreviewHandler
    template_preview_router: TemplatePreviewRouter
    auto_scheduler: AutoScheduler
    message_sender: MessageSender
    trace_store: TraceSQLiteStore
    checkpoint_store: CheckpointStore
    active_task_manager: ActiveTaskManager
    webui_bridge: PluginPageWebUIBridge
    settings_command_handler: SettingsCommandHandler
    comic_command_handler: ComicCommandHandler
    analysis_command_handler: AnalysisCommandHandler

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 1. 基础设施层
        self.config_manager = ConfigManager(config)
        self.bot_manager = BotManager(self.config_manager)
        self.bot_manager.set_context(context)
        self.bot_manager.set_plugin_instance(self)
        self.history_manager = HistoryManager(self)

        plugin_data_dir = StarTools.get_data_dir(PLUGIN_NAME)
        self.plugin_data_dir = plugin_data_dir

        self.report_generator = ReportGenerator(self.config_manager, plugin_data_dir)

        # Telegram 注册表 (持久层)
        self.platform_group_registry = PlatformGroupRegistry(self)

        # 1.1 Trace & Checkpoint 基础设施 (持久化)
        self.trace_store = TraceSQLiteStore(plugin_data_dir / "traces.db")
        TraceContext.set_global_store(self.trace_store)
        TraceContext.set_metrics_enabled(
            self.config_manager.get_enable_runtime_metrics()
        )
        self.checkpoint_store = CheckpointStore(plugin_data_dir / "traces.db")

        # 2. 领域层
        activity_visualizer = ActivityVisualizer()
        self.statistics_service = StatisticsService(activity_visualizer)
        self.analysis_domain_service = AnalysisDomainService()

        # 3. 分析核心 (LLM Bridge)
        self.llm_analyzer = LLMAnalyzer(context, self.config_manager)

        # 4. 增量分析组件
        self.incremental_store = IncrementalStore(self)
        self.incremental_merge_service = IncrementalMergeService()

        # 5. 应用层
        self.analysis_service = AnalysisApplicationService(
            self.config_manager,
            self.bot_manager,
            self.history_manager,
            self.report_generator,
            self.llm_analyzer,
            self.statistics_service,
            self.analysis_domain_service,
            incremental_store=self.incremental_store,
            incremental_merge_service=self.incremental_merge_service,
            checkpoint_store=self.checkpoint_store,
            html_render=self.html_render,
        )
        self.drawing_client = DrawingClient(self.config_manager)
        self.comic_service = ComicApplicationService(
            self.llm_analyzer,
            self.drawing_client,
            self.config_manager,
            plugin_data_dir,
            context=context,
        )

        # 消息处理服务
        self.message_processing_service = MessageProcessingService(
            context, self.platform_group_registry
        )

        self.template_command_service = TemplateCommandService(
            plugin_root=os.path.dirname(__file__)
        )
        self.telegram_template_preview_handler = TelegramTemplatePreviewHandler(
            config_manager=self.config_manager,
            template_service=self.template_command_service,
        )
        self.template_preview_router = TemplatePreviewRouter(
            handlers=[self.telegram_template_preview_handler]
        )

        # 调度与发送
        self.message_sender = MessageSender(self.bot_manager, self.config_manager)
        self.auto_scheduler = AutoScheduler(
            self.config_manager,
            self.analysis_service,
            self.bot_manager,
            self.report_generator,
            self.html_render,
            plugin_instance=self,
        )

        # 1.2 WebUI 控制台与 Task Reaper 孤儿回收器
        self.active_task_manager = ActiveTaskManager(trace_store=self.trace_store)
        TraceContext.set_active_task_manager(self.active_task_manager)
        self.active_task_manager.start_reaper(interval_seconds=30, timeout_seconds=180)
        self.webui_bridge = PluginPageWebUIBridge(
            context=context,
            trace_store=self.trace_store,
            active_task_manager=self.active_task_manager,
            analysis_service=self.analysis_service,
            report_dispatcher=self.auto_scheduler.report_dispatcher,
            report_output_dir=plugin_data_dir / "reports",
        )
        self.webui_bridge.register_routes()

        # 开机崩溃对账与自愈恢复服务
        self.crash_recovery_service = CrashRecoveryService(
            trace_store=self.trace_store,
            checkpoint_store=self.checkpoint_store,
            analysis_service=self.analysis_service,
            report_dispatcher=self.auto_scheduler.report_dispatcher,
        )

        # 指令处理器
        self.settings_command_handler = SettingsCommandHandler(
            config_manager=self.config_manager,
            template_command_service=self.template_command_service,
            template_preview_router=self.template_preview_router,
            auto_scheduler=self.auto_scheduler,
            incremental_store=self.incremental_store,
            incremental_merge_service=self.incremental_merge_service,
            bot_manager=self.bot_manager,
            context=context,
        )
        self.comic_command_handler = ComicCommandHandler(
            config_manager=self.config_manager,
            bot_manager=self.bot_manager,
            comic_service=self.comic_service,
            analysis_service=self.analysis_service,
            active_task_manager=self.active_task_manager,
            plugin_data_dir=plugin_data_dir,
            plugin_instance=self,
        )
        self.analysis_command_handler = AnalysisCommandHandler(
            config_manager=self.config_manager,
            bot_manager=self.bot_manager,
            analysis_service=self.analysis_service,
            report_generator=self.report_generator,
            html_render=self.html_render,
            active_task_manager=self.active_task_manager,
            trace_store=self.trace_store,
            message_sender=self.message_sender,
            comic_handler=self.comic_command_handler,
            plugin_data_dir=plugin_data_dir,
            plugin_instance=self,
        )

        # 同步全局限流并进行初始化配置
        GlobalRateLimiter.get_instance(self.config_manager.get_llm_max_concurrent())

        self._initialized = False
        self._terminating = False
        self._init_lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

        # 异步注册任务，处理插件重载情况
        try:
            loop = asyncio.get_running_loop()
            self._init_task = loop.create_task(
                self._run_initialization("Plugin Reload/Init")
            )
            self._background_tasks.add(self._init_task)
            self._init_task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            self._init_task = None

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        await self._run_initialization("Platform Loaded")

    async def initialize(self):
        """在 AstrBot 插件生命周期中确认初始化已经完成。"""
        init_task = getattr(self, "_init_task", None)
        if init_task is None:
            await self._run_initialization("Plugin Lifecycle")
            return

        try:
            await asyncio.shield(init_task)
        except asyncio.CancelledError:
            if self._terminating:
                raise
            logger.warning("插件生命周期初始化任务被取消，正在执行恢复初始化。")
            await self._run_initialization("Plugin Lifecycle Recovery")

        if not self._initialized and not self._terminating:
            logger.warning("插件初始化未完成，正在执行一次生命周期恢复初始化。")
            await self._run_initialization("Plugin Lifecycle Recovery")

    async def _run_initialization(self, source: str):
        """执行插件初始化，避免阻塞平台启动流程。"""
        async with self._init_lock:
            if self._terminating or not self.bot_manager:
                return

            try:
                if not self._initialized:
                    logger.info(f"开始初始化插件（来源：{source}）...")

                    try:
                        self.config_manager.upgrade_prompt_templates()
                    except Exception as e:
                        logger.warning(f"升级 prompt 模板失败：{e}")

                    try:
                        self.config_manager.migrate_legacy_configs()
                    except Exception as e:
                        logger.warning(f"迁移旧版配置失败：{e}")

                await self.bot_manager.initialize_from_config()

                if self.template_preview_router:
                    await self.template_preview_router.ensure_handlers_registered(
                        self.context
                    )

                if self._initialized:
                    logger.debug(
                        f"插件已完成初始化，已刷新平台状态（来源：{source}）。"
                    )
                    return

                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                    await self.auto_scheduler.start_incremental_trigger()

                crash_recovery = getattr(self, "crash_recovery_service", None)
                if crash_recovery:
                    try:
                        loop = asyncio.get_running_loop()
                        recovery_task = loop.create_task(
                            crash_recovery.recover_crashed_tasks()
                        )
                        bg_tasks = getattr(self, "_background_tasks", None)
                        if isinstance(bg_tasks, set):
                            bg_tasks.add(recovery_task)
                            recovery_task.add_done_callback(bg_tasks.discard)
                    except RuntimeError:
                        pass

                self._initialized = True
                self._discovery_run = True
                logger.info(f"插件初始化完成（来源：{source}）")

            except Exception as e:
                logger.error(f"插件初始化失败：{e}", exc_info=True)

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        if self._terminating:
            return
        self._terminating = True

        if hasattr(self, "analysis_command_handler"):
            self.analysis_command_handler.set_terminating(True)
        if hasattr(self, "comic_command_handler"):
            self.comic_command_handler.set_terminating(True)

        try:
            logger.info("开始清理群日常分析插件资源...")

            if self._background_tasks:
                logger.info(f"正在取消 {len(self._background_tasks)} 个运行中的任务...")
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()

                try:
                    await asyncio.wait(list(self._background_tasks), timeout=3.0)
                except Exception:
                    pass
                self._background_tasks.clear()

            if self.auto_scheduler:
                logger.debug("正在停止自动调度器...")
                await self.auto_scheduler.shutdown(self.context)

            if self.template_preview_router:
                await self.template_preview_router.unregister_handlers()

            if self.report_generator:
                await self.report_generator.close()

            logger.info("群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    # ==================== 群消息增量计数与事件缓存 ====================

    @filter.event_message_type(
        filter.EventMessageType.GROUP_MESSAGE,
        priority=100,
    )
    async def count_incremental_group_message(self, event: AstrMessageEvent):
        """记录目标群消息，达到配置阈值后触发增量分析。"""
        if str(event.get_platform_name() or "").strip().lower() in {
            "qq_official",
            "qq_official_webhook",
            "telegram",
        }:
            return
        if self.auto_scheduler:
            await self.auto_scheduler.record_incremental_message(event)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(filter.PlatformAdapterType.TELEGRAM)
    async def intercept_telegram_messages(self, event: AstrMessageEvent):
        """拦截 Telegram 群消息并存储到数据库"""
        try:
            stored = await self.message_processing_service.process_message(event)
            if stored and self.auto_scheduler:
                await self.auto_scheduler.record_incremental_message(event)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"[Telegram] 消息存储失败: {e}")
        except Exception as e:
            logger.error(f"[Telegram] 消息存储异常: {e}", exc_info=True)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(
        filter.PlatformAdapterType.QQOFFICIAL
        | filter.PlatformAdapterType.QQOFFICIAL_WEBHOOK
    )
    async def intercept_qq_official_messages(self, event: AstrMessageEvent):
        """缓存 QQ 官方机器人群消息"""
        raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)
        if isinstance(raw_message, dict):
            author = raw_message.get("author") or {}
            group_openid = str(raw_message.get("group_openid", "") or "").strip()
            member_openid = str(
                author.get("member_openid", "") if isinstance(author, dict) else ""
            ).strip()
        else:
            author = getattr(raw_message, "author", None)
            group_openid = str(getattr(raw_message, "group_openid", "") or "").strip()
            member_openid = str(getattr(author, "member_openid", "") or "").strip()
        if not group_openid or not member_openid:
            return

        try:
            adapter = self.bot_manager.get_adapter(event.get_platform_id())
            remember_user_profile = getattr(adapter, "remember_user_profile", None)
            if callable(remember_user_profile):
                raw_avatar = (
                    author.get("avatar")
                    if isinstance(author, dict)
                    else getattr(author, "avatar", None)
                )
                raw_nickname = (
                    author.get("username")
                    if isinstance(author, dict)
                    else getattr(author, "username", None)
                )
                remember_user_profile(
                    member_openid,
                    nickname=str(raw_nickname or event.get_sender_name() or ""),
                    avatar_url=str(raw_avatar or ""),
                )

            stored = await self.message_processing_service.process_message(event)
            if stored and self.auto_scheduler:
                await self.auto_scheduler.record_incremental_message(event)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"[QQOfficial] 消息存储失败: {e}")
        except Exception as e:
            logger.error(f"[QQOfficial] 消息存储异常: {e}", exc_info=True)

    async def get_telegram_seen_group_ids(
        self, platform_id: str | None = None
    ) -> list[str]:
        return await self.platform_group_registry.get_all_group_ids(platform_id)

    async def get_seen_group_ids(self, platform_id: str | None = None) -> list[str]:
        return await self.platform_group_registry.get_all_group_ids(platform_id)

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str:
        try:
            return event.get_platform_id()
        except Exception:
            if (
                hasattr(event, "platform_meta")
                and event.platform_meta
                and hasattr(event.platform_meta, "id")
            ):
                return event.platform_meta.id
            return "default"

    # ==================== 指令注册与分发 ====================

    @filter.command("群分析", alias={"group_analysis"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AstrMessageEvent, days: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """分析群聊日常活动（跨平台支持）"""
        handler = _resolve_analysis_handler(self)
        async for result in handler.handle_daily_analysis(event, days):
            yield result

    @filter.command("群漫画", alias={"group_comic", "daily_comic"})
    @filter.permission_type(PermissionType.ADMIN)
    async def generate_group_comic(
        self, event: AstrMessageEvent, days: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """生成群聊趣味漫画（跨平台支持）"""
        handler = _resolve_comic_handler(self)
        async for result in handler.handle_group_comic(event, days):
            yield result

    @filter.command("设置格式", alias={"set_format"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: AstrMessageEvent, format_input: str = ""):
        """设置分析报告输出格式（跨平台支持）"""
        handler = _resolve_settings_handler(self)
        async for result in handler.handle_set_output_format(event, format_input):
            yield result

    @filter.command("设置模板", alias={"set_template"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_report_template(
        self, event: AstrMessageEvent, template_input: str = ""
    ):
        """设置分析报告模板（跨平台支持）"""
        handler = _resolve_settings_handler(self)
        async for result in handler.handle_set_report_template(event, template_input):
            yield result

    @filter.command("查看模板", alias={"view_templates"})
    @filter.permission_type(PermissionType.ADMIN)
    async def view_templates(self, event: AstrMessageEvent):
        """查看所有可用的报告模板及预览图（跨平台支持）"""
        platform_id_fn = getattr(self, "_get_platform_id_from_event", None)
        platform_id = str(platform_id_fn(event) if callable(platform_id_fn) else "")
        handler = _resolve_settings_handler(self)
        async for result in handler.handle_view_templates(event, platform_id):
            yield result

    @filter.command("分析设置", alias={"analysis_settings"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(self, event: AstrMessageEvent, action: str = "status"):
        """管理分析设置（跨平台支持）"""
        group_id_fn = getattr(self, "_get_group_id_from_event", None)
        group_id = (
            (group_id_fn(event) or "")
            if callable(group_id_fn)
            else getattr(event, "group_id", "")
        )
        platform_id_fn = getattr(self, "_get_platform_id_from_event", None)
        platform_id = str(platform_id_fn(event) if callable(platform_id_fn) else "")
        handler = _resolve_settings_handler(self)
        async for result in handler.handle_analysis_settings(
            event, action, str(group_id), platform_id
        ):
            yield result

    @filter.command("增量状态", alias={"incremental_status"})
    @filter.permission_type(PermissionType.ADMIN)
    async def incremental_status(self, event: AstrMessageEvent):
        """查看当前增量分析状态（滑动窗口）"""
        group_id_fn = getattr(self, "_get_group_id_from_event", None)
        group_id = (
            (group_id_fn(event) or "")
            if callable(group_id_fn)
            else getattr(event, "group_id", "")
        )
        handler = _resolve_settings_handler(self)
        async for result in handler.handle_incremental_status(event, str(group_id)):
            yield result

    async def _refresh_incremental_target_states(self) -> None:
        """在插件内修改名单后立即同步增量状态。"""
        handler = _resolve_settings_handler(self)
        await handler._refresh_incremental_target_states()

    # ==================== 兼容性私有方法代理转发 ====================

    async def _send_analysis_report(
        self, event: AstrMessageEvent, result: dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        handler = _resolve_analysis_handler(self)
        async for res in handler.send_analysis_report(event, result):
            yield res

    async def _try_upload_image(
        self,
        group_id: str,
        image_url: str,
        platform_id: str | None,
        is_comic: bool = False,
    ) -> None:
        handler = _resolve_analysis_handler(self)
        await handler._try_upload_image(
            group_id, image_url, platform_id, is_comic=is_comic
        )

    def _save_report_to_history(self, image_url: str, group_id: str) -> None:
        handler = _resolve_analysis_handler(self)
        handler._save_report_to_history(image_url, group_id)

    async def _send_text_reports(
        self,
        group_id: str,
        analysis_result: dict[str, Any],
        is_qq_official: bool,
        adapter: Any,
    ) -> None:
        handler = _resolve_analysis_handler(self)
        await handler._send_text_reports(
            group_id, analysis_result, is_qq_official, adapter
        )

    def _try_trigger_comic_generation(
        self,
        group_id: str,
        platform_id: str | None,
        analysis_result: dict[str, Any],
        *,
        require_auto_enabled: bool = True,
        trace: TraceContext | None = None,
    ) -> str:
        handler = _resolve_comic_handler(self)
        return handler.try_trigger_comic_generation(
            group_id,
            platform_id,
            analysis_result,
            require_auto_enabled=require_auto_enabled,
            trace=trace,
        )

    async def _trigger_comic_generation(
        self,
        topics: list[dict[str, Any]],
        group_id: str,
        platform_id: str | None,
        umo: str,
        trace: TraceContext | None = None,
    ) -> None:
        handler = _resolve_comic_handler(self)
        await handler._trigger_comic_generation(
            topics, group_id, platform_id, umo, trace=trace
        )

    @property
    def _comic_group_tasks(self) -> dict[str, asyncio.Task]:
        return _resolve_comic_handler(self)._comic_group_tasks

    @_comic_group_tasks.setter
    def _comic_group_tasks(self, val: dict[str, asyncio.Task]) -> None:
        _resolve_comic_handler(self)._comic_group_tasks = val

    @staticmethod
    def _detect_image_ext(data: bytes) -> str:
        return ComicCommandHandler.detect_image_ext(data)
