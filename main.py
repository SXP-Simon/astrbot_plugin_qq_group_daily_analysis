"""
群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，支持跨平台
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star, StarTools

# File is only available via astrbot.core (internal API — may change).
from astrbot.core.message.components import File

from .src.application.commands.template_command_service import (
    TemplateCommandService,
)
from .src.application.services.analysis_application_service import (
    AnalysisApplicationService,
    DuplicateGroupTaskError,
)
from .src.application.services.comic_application_service import ComicApplicationService
from .src.application.services.message_processing_service import (
    MessageProcessingService,
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

        # 漫画生成并发与同群任务去重。
        self._comic_semaphore = asyncio.Semaphore(
            max(1, self.config_manager.get_t2i_max_concurrent())
        )
        self._comic_group_tasks: dict[str, asyncio.Task] = {}
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
        self.active_task_manager.start_reaper(interval_seconds=30, timeout_seconds=600)
        self.webui_bridge = PluginPageWebUIBridge(
            context=context,
            trace_store=self.trace_store,
            active_task_manager=self.active_task_manager,
            analysis_service=self.analysis_service,
            report_dispatcher=self.auto_scheduler.report_dispatcher,
            report_output_dir=plugin_data_dir / "reports",
        )
        self.webui_bridge.register_routes()

        # 同步全局限流并进行初始化配置
        GlobalRateLimiter.get_instance(self.config_manager.get_llm_max_concurrent())

        self._initialized = False
        self._terminating = False  # 生命周期标志
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

    # orchestrators 缓存已移至 应用层逻辑 (分析服务) 或 暂时移除以简化。
    # 如果需要高性能缓存，后续可由 AnalysisApplicationService 内部维护。

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        await self._run_initialization("Platform Loaded")

    async def initialize(self):
        """在 AstrBot 插件生命周期中确认初始化已经完成。

        Returns:
            None: 初始化任务完成或恢复初始化完成后返回。
        """
        init_task = getattr(self, "_init_task", None)
        if init_task is None:
            await self._run_initialization("Plugin Lifecycle")
            return

        try:
            # 构造函数中的任务负责避免阻塞 AstrBot 启动；生命周期入口负责等待
            # 它完成，确保插件重载不会在平台刷新之前被判定为加载成功。
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
        """执行插件初始化，避免阻塞平台启动流程。

        Args:
            source: 触发本次初始化的来源标识。

        Returns:
            None: 就地完成插件状态初始化或刷新。
        """
        async with self._init_lock:
            if self._terminating or not self.bot_manager:
                return

            try:
                # 核心配置迁移和定时任务只执行一次。
                if not self._initialized:
                    logger.info(f"开始初始化插件（来源：{source}）...")

                    # 升级旧版 prompt 模板并回写迁移后的配置。
                    try:
                        self.config_manager.upgrade_prompt_templates()
                    except Exception as e:
                        logger.warning(f"升级 prompt 模板失败：{e}")

                    try:
                        self.config_manager.migrate_legacy_configs()
                    except Exception as e:
                        logger.warning(f"迁移旧版配置失败：{e}")

                # AstrBot 会为每个平台调用一次此回调。平台发现只检查已创建的
                # 平台对象，可以安全重复执行；这样后加载的平台也不会被遗漏。
                await self.bot_manager.initialize_from_config()

                # 模板预览处理器依赖平台实例，因此每个平台加载时都要刷新。
                if self.template_preview_router:
                    await self.template_preview_router.ensure_handlers_registered(
                        self.context
                    )

                if self._initialized:
                    logger.debug(
                        f"插件已完成初始化，已刷新平台状态（来源：{source}）。"
                    )
                    return

                # 插件基础设施准备完成后注册定时任务。
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                    await self.auto_scheduler.start_incremental_trigger()

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

        try:
            logger.info("开始清理群日常分析插件资源...")

            # 1. 停止所有后台任务
            if self._background_tasks:
                logger.info(f"正在取消 {len(self._background_tasks)} 个运行中的任务...")
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()

                # 等待任务结束，给予 3 秒宽限期
                try:
                    await asyncio.wait(list(self._background_tasks), timeout=3.0)
                except Exception:
                    pass
                self._background_tasks.clear()

            # 2. 停止各个组件 (顺序：先调度器，后底层服务)
            if self.auto_scheduler:
                logger.debug("正在停止自动调度器...")
                await self.auto_scheduler.shutdown(self.context)

            if self.template_preview_router:
                await self.template_preview_router.unregister_handlers()

            if self.report_generator:
                await self.report_generator.close()

            # 3. [关键修复] 只有在任务全部清理后，才清理引用。
            # 实际上，在 terminate 结束后，self 本身就会被 GC 释放，
            # 这里的显式 None 更多是为了协助循环引用清理，但由于异步任务存在竞态，
            # 我们可以通过 check _terminating 标志位来保护。
            # 为了彻底解决 #125，我们保留引用，让 GC 自然回收。
            logger.info("群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    # ==================== 群消息增量计数与事件缓存 ====================

    @filter.event_message_type(
        filter.EventMessageType.GROUP_MESSAGE,
        priority=100,
    )
    async def count_incremental_group_message(self, event: AstrMessageEvent):
        """记录目标群消息，达到配置阈值后触发增量分析。

        Args:
            event: AstrBot 群消息事件。

        Returns:
            None: 计数完成后继续消息流水线。
        """
        # QQ 官方和 Telegram 会在各自的持久化钩子成功后计数，避免任务先于入库启动。
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
        """
        拦截 Telegram 群消息并存储到数据库

        委托给 MessageProcessingService 处理
        """
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
        """缓存 QQ 官方机器人群消息；频道消息不在本插件适配范围内。"""
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
        """读取 Telegram 已见群/话题列表（给调度器回退使用）。"""
        return await self.platform_group_registry.get_all_group_ids(platform_id)

    async def get_seen_group_ids(self, platform_id: str | None = None) -> list[str]:
        """读取任意事件驱动平台已经见过的群组。"""
        return await self.platform_group_registry.get_all_group_ids(platform_id)

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从消息事件中安全获取群组 ID"""
        # 保留此辅助方法，因为在其他 command 中仍被频繁使用
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str:
        """从消息事件中获取平台唯一 ID"""
        # 保留此辅助方法，因为在其他 command 中仍被频繁使用
        try:
            return event.get_platform_id()
        except Exception:
            # 后备方案：从元数据获取
            if (
                hasattr(event, "platform_meta")
                and event.platform_meta
                and hasattr(event.platform_meta, "id")
            ):
                return event.platform_meta.id
            return "default"

    # ================================================================
    # 图片报告上传到群文件 / 群相册（仅 QQ 平台 image 格式）
    # ================================================================

    async def _try_upload_image(
        self,
        group_id: str,
        image_url: str,
        platform_id: str | None,
        is_comic: bool = False,
    ):
        """
        尝试将图片报告上传到群文件和/或群相册（静默处理，失败仅日志提示）。
        """
        import base64
        import re
        import tempfile
        from datetime import datetime

        if is_comic:
            enable_file = False  # 我们通常不把漫画作为文件上传，或者可以复用 enable_group_file_upload
            enable_album = self.config_manager.get_enable_comic_album_upload()
        else:
            enable_file = self.config_manager.get_enable_group_file_upload()
            enable_album = self.config_manager.get_enable_group_album_upload()

        if not enable_file and not enable_album:
            return

        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            return
        if enable_file and not hasattr(adapter, "upload_group_file_to_folder"):
            logger.warning(f"群 {group_id} 的适配器不支持群文件上传。")
            enable_file = False
        if enable_album and not hasattr(adapter, "upload_group_album"):
            logger.warning(f"群 {group_id} 的适配器不支持群相册上传。")
            enable_album = False
        if not enable_file and not enable_album:
            return

        # 1. 记录文件名的公共部分。漫画真实格式必须在读取图片字节后决定，
        # 不能依据已经删除的全局输出格式，也不能盲信外部后端返回的文件后缀。
        now = datetime.now()
        timestamp = now.strftime("%H%M")
        date_str = now.strftime("%Y-%m-%d")
        filename_stem = f"群分析报告_{group_id}_{date_str}_{timestamp}"
        try:
            # 尝试通过适配器获取群名称，使文件名更具辨识度
            group_info = await adapter.get_group_info(group_id)
            if group_info and group_info.group_name:
                # 过滤非法文件名字符：\ / : * ? " < > |
                safe_name = re.sub(r'[\\/:*?"<>|]', "", group_info.group_name).strip()
                if safe_name:
                    filename_stem = f"群分析报告_{safe_name}_{date_str}_{timestamp}"
        except Exception:
            pass

        # 2. 将内容准备为文件或数据
        image_file = None
        created_temp = False
        MAX_PAYLOAD_SIZE = 20 * 1024 * 1024  # 20MB 限制

        try:
            data = None
            if image_url.startswith("base64://"):
                base64_str = image_url[len("base64://") :]
                if len(base64_str) * 3 / 4 > MAX_PAYLOAD_SIZE:
                    logger.warning("图片上传失败：Base64 负载过大")
                    return
                data = base64.b64decode(base64_str)
            elif image_url.startswith("data:"):
                parts = image_url.split(",", 1)
                if len(parts) == 2:
                    if len(parts[1]) * 3 / 4 > MAX_PAYLOAD_SIZE:
                        logger.warning("图片上传失败：Data URI 负载过大")
                        return
                    data = base64.b64decode(parts[1])
            elif os.path.isfile(image_url):
                image_file = os.path.abspath(image_url)

            if is_comic:
                # 缓存文件通常已有正确后缀，但上传入口也允许接收 Base64/Data URI。
                # 对本地文件读取少量头部字节即可，不需要把大图完整载入内存。
                image_header = data
                if image_header is None and image_file:
                    with open(image_file, "rb") as image_stream:
                        image_header = image_stream.read(32)
                ext = self._detect_image_ext(image_header or b"")
            else:
                ext = (
                    ".jpg"
                    if (".jpg" in image_url.lower() or ".jpeg" in image_url.lower())
                    else ".png"
                )
            nice_filename = f"{filename_stem}{ext}"

            if data and not image_file:
                # 使用 tempfile 生成唯一后缀，防止并发冲突
                fd, image_file = tempfile.mkstemp(suffix=ext, prefix="group_report_")
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                    created_temp = True
                except Exception:
                    os.close(fd)
                    raise

            if not image_file:
                return

            # 3. 执行上传：群文件
            if enable_file:
                try:
                    folder_name = self.config_manager.get_group_file_folder()
                    folder_id = None
                    if folder_name:
                        folder_id = await adapter.find_or_create_folder(  # type: ignore[attr-defined]
                            group_id, folder_name
                        )
                    await adapter.upload_group_file_to_folder(  # type: ignore[attr-defined]
                        group_id=group_id,
                        file_path=image_file,
                        folder_id=folder_id,
                        filename=nice_filename,  # 显式传递漂亮的文件名
                    )
                except Exception as e:
                    logger.warning(f"群文件上传失败 (群 {group_id}): {e}")

            if enable_album:
                try:
                    if is_comic:
                        album_name = self.config_manager.get_comic_album_name()
                        # 漫画相册与报告相册共用同一个 strict_mode 配置，
                        # 若日后需要独立控制，可为漫画单独添加配置项。
                        strict_mode = self.config_manager.get_group_album_strict_mode()
                    else:
                        album_name = self.config_manager.get_group_album_name()
                        strict_mode = self.config_manager.get_group_album_strict_mode()

                    upload_label = "漫画相册" if is_comic else "群相册"
                    # 严格模式下，名称为空时提前拦截，不再依赖适配器判断
                    if strict_mode and not album_name:
                        logger.info(
                            f"{upload_label}严格模式开启：未设置目标相册名称，停止上传以防止操作群 {group_id} 的默认相册。"
                        )
                    elif hasattr(adapter, "upload_group_album"):
                        # 查找和兜底逻辑统一由适配器处理：
                        #   - strict_mode=True + 找不到相册 → 适配器会拒绝上传
                        #   - strict_mode=False + 找不到相册 → 适配器会回退到默认相册
                        await adapter.upload_group_album(  # type: ignore[attr-defined]
                            group_id,
                            image_file,
                            album_id=None,
                            album_name=album_name,
                            strict_mode=strict_mode,
                        )
                    else:
                        logger.warning(f"群 {group_id} 的适配器不支持群相册上传。")
                except Exception as e:
                    logger.warning(f"群相册上传失败 (群 {group_id}): {e}")
        except Exception as e:
            logger.warning(f"图片上传处理异常: {e}")
        finally:
            if created_temp and image_file and os.path.exists(image_file):
                try:
                    os.remove(image_file)
                except OSError:
                    pass

    @filter.command("群分析", alias={"group_analysis"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AstrMessageEvent, days: int | None = None
    ):
        """
        分析群聊日常活动（跨平台支持）
        用法: /群分析 [天数]
        """
        if self._terminating:
            return

        current_task = asyncio.current_task()
        if current_task:
            self._background_tasks.add(current_task)

        trace = None
        trace_id = ""

        try:
            event.should_call_llm(True)  # 阻止默认 LLM 解析
            group_id = self._get_group_id_from_event(event)
            platform_id = self._get_platform_id_from_event(event)

            if not group_id:
                yield event.plain_result("❌ 请在群聊中使用此命令")
                return

            # 更新bot实例
            self.bot_manager.update_from_event(event)

            # 优先使用 UMO 进行权限检查 (兼容白名单 UMO 格式)
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = f"{platform_id}:GroupMessage:{group_id}"

            if not self.config_manager.is_group_allowed(check_target):
                # Fallback checks (simple ID) are handled inside is_group_allowed logic if list item has no colon
                # But if list item HAS colon, we need precise match.
                # If prompt fails, try simple ID as fallback for permissive cases?
                # No, config_manager.is_group_allowed already handles simple ID matching if whitelist item is simple ID.
                yield event.plain_result("❌ 此群未启用日常分析功能")
                return

            # 获取群名以生成语义化的 TraceID
            group_name = ""
            try:
                adapter = self.bot_manager.get_adapter(platform_id)
                if adapter:
                    info = await adapter.get_group_info(group_id)
                    if info and info.group_name:
                        group_name = info.group_name
            except Exception:
                pass

            # 设置 TraceID (语义化格式: manual_群名_HHmm)
            trace_id = TraceContext.generate(
                prefix="manual", group_name=group_name or group_id
            )
            trace = TraceContext.set(
                trace_id=trace_id,
                group_id=group_id,
                group_name=group_name,
                platform=platform_id or "",
                trigger_type="manual",
            )
            if self.active_task_manager:
                await self.active_task_manager.register_task(
                    task_id=trace_id,
                    group_id=group_id,
                    group_name=group_name,
                    platform=platform_id or "",
                    trigger_type="manual",
                    current_stage="FETCH_MESSAGES",
                    asyncio_task=current_task,
                )

            # 表情回应 或 文本提示（二选一，由配置开关控制）
            adapter = self.bot_manager.get_adapter(platform_id)
            orig_msg_id = getattr(event.message_obj, "message_id", None)
            adapter_platform_name = (
                (adapter.get_platform_name() if adapter else "").strip().lower()
            )
            # QQ 官方机器人 API v2 不支持本插件使用的表情回应接口，
            # 因此始终沿用原有的文字进度提示，避免触发无效的 reaction 请求。
            use_text_reply = (
                adapter_platform_name in {"qq_official", "qq_official_webhook"}
                or self.config_manager.get_enable_analysis_reply()
            )

            if use_text_reply:
                yield event.plain_result("🔍 正在启动分析引擎，正在拉取最近消息...")
            elif adapter and orig_msg_id:
                await adapter.set_reaction(
                    event.get_group_id(), orig_msg_id, "analysis_started"
                )

            # 调用 DDD 应用级服务
            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id, platform_id=platform_id, manual=True, days=days
            )

            if not result.get("success"):
                reason = result.get("reason")
                if trace and trace.status == "running":
                    trace.finish(
                        status="failed",
                        error_message=result.get("error")
                        or f"Analysis skipped/failed: {reason}",
                    )
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到足够的群聊记录")
                elif reason == "llm_analysis_failed":
                    yield event.plain_result(
                        "❌ 大模型文本分析失败：所有已开启的分析模块均调用失败或重试耗尽（请检查大模型 API Key 及服务商连通性）"
                    )
                elif reason == "muted":
                    logger.warning(
                        f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过回复以防抛出发送异常"
                    )
                else:
                    yield event.plain_result(
                        f"❌ 分析失败: {result.get('error', '原因未知')}"
                    )
                return

            if not use_text_reply and adapter and orig_msg_id:
                await adapter.set_reaction(
                    event.get_group_id(), orig_msg_id, "analysis_done"
                )

            if self.active_task_manager:
                await self.active_task_manager.update_stage(trace_id, "RENDER_REPORT")

            async for res in self._send_analysis_report(event, result):
                yield res

            if trace and trace.status == "running":
                trace.finish(status="succeeded")

        except DuplicateGroupTaskError:
            if trace and trace.status == "running":
                trace.finish(
                    status="aborted", error_message="Task already running in group"
                )
            yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
        except asyncio.CancelledError:
            if trace and trace.status == "running":
                trace.finish(status="aborted", error_message="Task cancelled by system")
            logger.info("群分析任务被取消 (插件重载或卸载)")
        except Exception as e:
            if trace and trace.status == "running":
                trace.finish(status="failed", error_message=str(e))
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )
        finally:
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            if current_task:
                self._background_tasks.discard(current_task)

    @filter.command("群漫画", alias={"group_comic", "daily_comic"})
    @filter.permission_type(PermissionType.ADMIN)
    async def generate_group_comic(
        self, event: AstrMessageEvent, days: int | None = None
    ):
        """
        生成群聊趣味漫画（跨平台支持）
        用法: /群漫画 [天数]
        """
        if self._terminating:
            return

        trace = None
        trace_id = None
        current_task = asyncio.current_task()
        if current_task:
            self._background_tasks.add(current_task)

        try:
            event.should_call_llm(True)
            group_id = self._get_group_id_from_event(event)
            platform_id = self._get_platform_id_from_event(event)

            if not group_id:
                yield event.plain_result("❌ 请在群聊中使用此命令")
                return

            self.bot_manager.update_from_event(event)

            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = f"{platform_id}:GroupMessage:{group_id}"

            if not self.config_manager.get_enable_daily_comic():
                yield event.plain_result("❌ 漫画生成功能未启用")
                return

            if not self.config_manager.is_comic_group_allowed(check_target):
                yield event.plain_result("❌ 此群未启用漫画生成功能")
                return

            task_key = f"{platform_id or 'default'}:{group_id}"
            existing_task = self._comic_group_tasks.get(task_key)
            if existing_task and not existing_task.done():
                yield event.plain_result("🎨 该群已有漫画任务正在执行，请稍后再试哦~")
                return

            group_name = None
            adapter = self.bot_manager.get_adapter(platform_id)
            if adapter and hasattr(adapter, "get_group_info"):
                try:
                    info = await adapter.get_group_info(group_id)
                    if info and hasattr(info, "group_name") and info.group_name:
                        group_name = info.group_name
                except Exception:
                    pass

            trace_id = TraceContext.generate(
                prefix="comic", group_name=group_name or group_id
            )
            trace = TraceContext.set(
                trace_id=trace_id,
                group_id=group_id,
                group_name=group_name or group_id,
                platform=platform_id or "",
                trigger_type="comic_manual",
            )
            if self.active_task_manager:
                await self.active_task_manager.register_task(
                    task_id=trace_id,
                    group_id=group_id,
                    group_name=group_name or group_id,
                    platform=platform_id or "",
                    trigger_type="comic_manual",
                    current_stage="FETCH_MESSAGES",
                    asyncio_task=current_task,
                )

            yield event.plain_result("🎨 正在提取群聊话题并生成漫画...")

            result = await self.analysis_service.execute_comic_topic_analysis(
                group_id=group_id, platform_id=platform_id, days=days
            )
            if not result.get("success"):
                reason = result.get("reason")
                if trace and trace.status == "running":
                    trace.finish(
                        status="failed", error_message=f"提取漫画话题失败: {reason}"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到可用于生成漫画的群聊记录")
                elif reason == "no_topics":
                    yield event.plain_result("❌ 未提取到可用于生成漫画的话题")
                elif reason == "muted":
                    logger.warning(
                        "群 %s 开启了禁言，跳过手动漫画回复",
                        group_id,
                    )
                else:
                    yield event.plain_result("❌ 漫画话题提取失败，原因未知")
                return

            status = self._try_trigger_comic_generation(
                group_id,
                platform_id,
                {"topics": result.get("topics", [])},
                require_auto_enabled=False,
                trace=trace,
            )
            if status == "started":
                yield event.plain_result("✅ 漫画生成任务已启动，完成后会发送到群里")
            elif status == "duplicate":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="该群已有漫画任务正在执行"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("🎨 该群已有漫画任务正在执行，请稍后再试哦~")
            elif status == "blocked":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="此群未启用漫画生成功能"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("❌ 此群未启用漫画生成功能")
            elif status == "no_topics":
                if trace and trace.status == "running":
                    trace.finish(
                        status="warning", error_message="未提取到可用于生成漫画的话题"
                    )
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("❌ 未提取到可用于生成漫画的话题")
            else:
                if trace and trace.status == "running":
                    trace.finish(status="failed", error_message="漫画生成任务未启动")
                if trace_id and self.active_task_manager:
                    await self.active_task_manager.finish_task(trace_id)
                yield event.plain_result("⚠️ 漫画生成任务未启动，请查看插件日志")

        except DuplicateGroupTaskError:
            if trace and trace.status == "running":
                trace.finish(
                    status="failed", error_message="该群的漫画话题提取任务正在执行"
                )
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            yield event.plain_result("🎨 该群的漫画话题提取任务正在执行，请稍后再试哦~")
        except asyncio.CancelledError:
            if trace and trace.status == "running":
                trace.finish(status="aborted", error_message="Task cancelled by system")
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            logger.info("手动漫画任务被取消（插件正在关闭或重载）")
        except Exception as e:
            if trace and trace.status == "running":
                trace.finish(status="failed", error_message=str(e))
            if trace_id and self.active_task_manager:
                await self.active_task_manager.finish_task(trace_id)
            logger.error("手动漫画生成失败: %s", e, exc_info=True)
            yield event.plain_result(
                f"❌ 漫画生成失败: {str(e)}。请检查消息获取、LLM 和绘图配置"
            )
        finally:
            if current_task:
                self._background_tasks.discard(current_task)

    def _save_report_to_history(self, image_url: str, group_id: str) -> None:
        """将生成的图片报告副本保存到持久化 reports 目录以供 WebUI 历史报告查阅"""
        try:
            reports_dir = self.plugin_data_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = reports_dir / f"report_{group_id}_{ts_str}.jpg"
            if Path(image_url).exists():
                import shutil

                shutil.copy2(image_url, dest)
            elif image_url.startswith("base64://"):
                import base64

                data = base64.b64decode(image_url[9:])
                dest.write_bytes(data)
        except Exception as e:
            logger.warning(f"保存历史报告副本失败: {e}")

    async def _send_analysis_report(
        self, event: AstrMessageEvent, result: dict
    ) -> AsyncGenerator:
        """处理分析结果的渲染和发送"""
        if self._terminating or not self.config_manager:
            logger.warning("插件正在关闭，停止发送报告")
            return

        group_id = result["group_id"]
        platform_id = result["platform_id"]
        analysis_result = result["analysis_result"]
        adapter = result["adapter"]
        self._try_trigger_comic_generation(group_id, platform_id, analysis_result)
        output_format = self.config_manager.get_output_format()[0]
        is_qq_official = adapter.get_platform_name() in {
            "qq_official",
            "qq_official_webhook",
        }

        # 定义获取回调
        async def avatar_url_getter(user_id: str) -> str | None:
            return await adapter.get_user_avatar_url(user_id)

        async def nickname_getter(user_id: str) -> str | None:
            try:
                member = await adapter.get_member_info(group_id, user_id)
                if member:
                    return member.card or member.nickname
            except Exception:
                pass
            return None

        trace = TraceContext.current()

        if output_format == "image":
            if trace:
                with trace.span("RENDER_REPORT", {"format": "image"}):
                    (
                        image_url,
                        html_content,
                    ) = await self.report_generator.generate_image_report(
                        analysis_result,
                        group_id,
                        self.html_render,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                    )
            else:
                (
                    image_url,
                    html_content,
                ) = await self.report_generator.generate_image_report(
                    analysis_result,
                    group_id,
                    self.html_render,
                    avatar_url_getter=avatar_url_getter,
                    nickname_getter=nickname_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=is_qq_official,
                )

            if image_url:
                self._save_report_to_history(image_url, group_id)
                caption = (
                    TraceContext.make_report_caption()
                    if self.config_manager.get_show_report_caption()
                    else ""
                )
                sent = await adapter.send_image(group_id, image_url, caption=caption)
                if sent:
                    await self._try_upload_image(group_id, image_url, platform_id)
                    return  # 成功发送

            # 如果图片生成或发送失败，直接回退到文本
            logger.warning(f"图片报告发送失败，正在发送文本回退报告。群: {group_id}")
            await self._send_text_reports(
                group_id, analysis_result, is_qq_official, adapter
            )
            return

        elif output_format == "html":
            cur_trace_id = trace.trace_id if trace else None
            if trace:
                with trace.span("RENDER_REPORT", {"format": "html"}):
                    (
                        html_path,
                        json_path,
                    ) = await self.report_generator.generate_html_report(
                        analysis_result,
                        group_id,
                        avatar_url_getter=avatar_url_getter,
                        nickname_getter=nickname_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=is_qq_official,
                        trace_id=cur_trace_id,
                    )
            else:
                html_path, json_path = await self.report_generator.generate_html_report(
                    analysis_result,
                    group_id,
                    avatar_url_getter=avatar_url_getter,
                    nickname_getter=nickname_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=is_qq_official,
                    trace_id=cur_trace_id,
                )
            if html_path:
                is_only_url = self.config_manager.get_html_only_url()
                base_url = self.config_manager.get_html_base_url()

                should_send_file = True

                if is_only_url:
                    if base_url and base_url.strip():
                        # 获取配置中的输出目录
                        html_output_dir = self.config_manager.get_html_output_dir()

                        # 若用户配置为空，使用默认目录
                        if not html_output_dir:
                            html_output_dir = os.path.join(
                                StarTools.get_data_dir(PLUGIN_NAME),
                                "self_hosted_html_reports",
                            )

                        # 计算相对路径并转换为URL
                        rel_path = os.path.relpath(html_path, html_output_dir)
                        url_path = rel_path.replace(os.sep, "/")
                        encoded_url_path = quote(url_path.lstrip("/"), safe="/")
                        report_url = f"{base_url.rstrip('/')}/{encoded_url_path}"

                        yield event.plain_result(
                            f"📊 今日群聊分析报告已生成：\n{report_url}"
                        )
                        should_send_file = False  # 拦截成功，不再发文件
                    else:
                        logger.warning(
                            f"手动触发群 {group_id} 开启了仅发送外链，但未配置 html_base_url，回退至发送文件。"
                        )

                if should_send_file:
                    caption = self.report_generator.build_html_caption(html_path)

                    # 发送 HTML 文件
                    sender = getattr(self, "message_sender", None)
                    if sender:
                        sent = await sender.send_file(
                            group_id,
                            html_path,
                            caption=caption,
                            platform_id=platform_id,
                        )
                    else:
                        sent = await adapter.send_file(group_id, html_path)
                        if sent and caption:
                            await adapter.send_text(group_id, caption)

                    if not sent:
                        yield event.chain_result(
                            [File(name=Path(html_path).name, file=html_path)]
                        )
                        if caption:
                            yield event.plain_result(caption)
            else:
                yield event.plain_result("⚠️ HTML 生成失败。")

        else:
            await self._send_text_reports(
                group_id, analysis_result, is_qq_official, adapter
            )

    def _try_trigger_comic_generation(
        self,
        group_id: str,
        platform_id: str | None,
        analysis_result: dict,
        *,
        require_auto_enabled: bool = True,
        trace: TraceContext | None = None,
    ) -> str:
        if self._terminating:
            return "terminating"
        if not self.config_manager.get_enable_daily_comic():
            return "disabled"
        auto_comic_enabled = getattr(
            self.config_manager, "get_enable_auto_daily_comic", None
        )
        if (
            require_auto_enabled
            and callable(auto_comic_enabled)
            and not auto_comic_enabled()
        ):
            return "auto_disabled"

        umo = f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
        comic_allowed = getattr(self.config_manager, "is_comic_group_allowed", None)
        inherit_allowed = True if require_auto_enabled else None
        if callable(comic_allowed) and not comic_allowed(umo, inherit_allowed):
            logger.info(
                "群 %s 未通过漫画名单判定，跳过漫画生成。platform=%s",
                group_id,
                platform_id or "default",
            )
            return "blocked"

        topics = analysis_result.get("topics", [])
        statistics = analysis_result.get("statistics")
        if not topics and statistics:
            topics = getattr(statistics, "topics", [])

        comic_topics = []
        for topic in topics if isinstance(topics, list) else []:
            title = (
                topic.get("topic", "")
                if isinstance(topic, dict)
                else getattr(topic, "topic", "")
            )
            detail = (
                topic.get("detail", "")
                if isinstance(topic, dict)
                else getattr(topic, "detail", "")
            )
            if str(title).strip():
                comic_topics.append(
                    {"topic": str(title).strip(), "detail": str(detail).strip()}
                )
        if not comic_topics:
            logger.warning(f"群 {group_id} 没有有效话题，跳过漫画生成。")
            return "no_topics"

        task_key = f"{platform_id or 'default'}:{group_id}"
        existing_task = self._comic_group_tasks.get(task_key)
        if existing_task and not existing_task.done():
            logger.info(f"群 {group_id} 已有漫画任务等待或执行，跳过重复任务。")
            return "duplicate"

        task = asyncio.create_task(
            self._trigger_comic_generation(
                comic_topics, group_id, platform_id, umo, trace=trace
            )
        )
        self._comic_group_tasks[task_key] = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(
            lambda completed_task: (
                self._comic_group_tasks.pop(task_key, None)
                if self._comic_group_tasks.get(task_key) is completed_task
                else None
            )
        )
        return "started"

    @staticmethod
    def _detect_image_ext(data: bytes) -> str:
        """从图片字节嗅探扩展名，无法识别时回退 .png。"""
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12] in {b"avif", b"avis"}
        ):
            return ".avif"
        return ".png"

    async def _trigger_comic_generation(
        self,
        topics: list[dict],
        group_id: str,
        platform_id: str | None,
        umo: str,
        trace: TraceContext | None = None,
    ):
        """后台生成并上传漫画，通过信号量控制并发"""
        cur_trace = trace or TraceContext.current()
        if cur_trace:
            from .src.shared.trace_context import _current_trace

            _current_trace.set(cur_trace)

        async with self._comic_semaphore:
            if self._terminating:
                return
            try:
                if cur_trace and self.active_task_manager:
                    await self.active_task_manager.update_stage(
                        cur_trace.trace_id, "COMIC_STORYBOARD"
                    )

                comic_bytes, fallback_url = await self.comic_service.generate_comic(
                    topics, group_id, umo
                )
                if comic_bytes:
                    logger.info(f"群 {group_id} 漫画生成成功，准备发送和保存副本...")
                    ext = self._detect_image_ext(comic_bytes)
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    trace_suffix = f"_{cur_trace.trace_id}" if cur_trace else ""
                    filename = f"comic_{group_id}_{ts_str}{trace_suffix}{ext}"

                    reports_dir = (
                        getattr(self, "plugin_data_dir", None)
                        or StarTools.get_data_dir(PLUGIN_NAME)
                    ) / "reports"
                    reports_dir.mkdir(parents=True, exist_ok=True)
                    comic_file_path = reports_dir / filename
                    comic_file_path.write_bytes(comic_bytes)

                    if cur_trace:
                        rfiles = cur_trace.metadata.setdefault("report_files", [])
                        rfiles.append(
                            {
                                "filename": filename,
                                "format": "image",
                                "report_type": "comic",
                                "path": str(comic_file_path.resolve()),
                            }
                        )

                    try:
                        if self._terminating:
                            return

                        if cur_trace:
                            with cur_trace.span(
                                "DISPATCH_REPORT", {"format": "image", "type": "comic"}
                            ):
                                # 发送图片到群聊
                                adapter = self.bot_manager.get_adapter(platform_id)
                                if adapter and hasattr(adapter, "send_image"):
                                    await adapter.send_image(
                                        group_id,
                                        str(comic_file_path),
                                        caption="✨ 今日群聊趣味漫画已生成！",
                                    )

                                # 上传到相册/群文件
                                await self._try_upload_image(
                                    group_id,
                                    str(comic_file_path),
                                    platform_id,
                                    is_comic=True,
                                )
                        else:
                            adapter = self.bot_manager.get_adapter(platform_id)
                            if adapter and hasattr(adapter, "send_image"):
                                await adapter.send_image(
                                    group_id,
                                    str(comic_file_path),
                                    caption="✨ 今日群聊趣味漫画已生成！",
                                )
                            await self._try_upload_image(
                                group_id,
                                str(comic_file_path),
                                platform_id,
                                is_comic=True,
                            )
                    except Exception as e:
                        logger.warning(f"投递群 {group_id} 漫画失败: {e}")

                    if cur_trace and cur_trace.trigger_type == "comic_manual":
                        cur_trace.finish(status="success")
                        if self.active_task_manager:
                            await self.active_task_manager.finish_task(
                                cur_trace.trace_id
                            )

                elif fallback_url:
                    # 图片 API 返回了 URL 但下载失败，把链接发到群里作为兜底
                    logger.warning(
                        f"群 {group_id} 漫画下载失败，发送 fallback URL 到群中: {fallback_url}"
                    )
                    adapter = self.bot_manager.get_adapter(platform_id)
                    if adapter and hasattr(adapter, "send_text"):
                        await adapter.send_text(
                            group_id,
                            f"✨ 今日群聊趣味漫画已生成，但图片下载失败，请点击链接查看：\n{fallback_url}",
                        )
                    if cur_trace and cur_trace.trigger_type == "comic_manual":
                        cur_trace.finish(
                            status="warning",
                            error_message="Comic download failed, fallback url sent",
                        )
                        if self.active_task_manager:
                            await self.active_task_manager.finish_task(
                                cur_trace.trace_id
                            )
                else:
                    if cur_trace and cur_trace.trigger_type == "comic_manual":
                        cur_trace.finish(status="failed", error_message="未能生成漫画")
                        if self.active_task_manager:
                            await self.active_task_manager.finish_task(
                                cur_trace.trace_id
                            )
            except Exception as e:
                logger.error(
                    f"群 {group_id} 生成/上传漫画时发生错误: {e}", exc_info=True
                )
                if cur_trace and cur_trace.trigger_type == "comic_manual":
                    cur_trace.finish(status="failed", error_message=str(e))
                    if self.active_task_manager:
                        await self.active_task_manager.finish_task(cur_trace.trace_id)

    async def _generate_text_reports(
        self, analysis_result: dict, use_qq_official_markdown: bool
    ) -> tuple[str, str | None]:
        """Generate text or QQ-official-markdown reports."""
        if use_qq_official_markdown:
            return await self.report_generator.generate_qq_official_markdown_report(
                analysis_result, self.html_render
            )
        return self.report_generator.generate_text_report(analysis_result), None

    async def _send_text_reports(
        self,
        group_id: str,
        analysis_result: dict,
        use_qq_official_markdown: bool,
        adapter,
    ) -> bool:
        """Send text reports via platform adapter."""
        tr, fr = await self._generate_text_reports(
            analysis_result, use_qq_official_markdown
        )
        if use_qq_official_markdown:
            return await adapter.send_text_report(group_id, tr, fallback_content=fr)
        return await adapter.send_text_report(group_id, tr)

    @filter.command("设置格式", alias={"set_format"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: AstrMessageEvent, format_input: str = ""):
        """
        设置分析报告输出格式（跨平台支持）
        用法: /设置格式 [格式名称或序号] 或 image,html 等逗号分隔的组合
        """
        # 命令由插件处理，禁用默认 LLM 回退。
        event.should_call_llm(True)

        available_formats = ["image", "text", "html"]
        format_display_names = {
            "image": "图片格式 (默认)",
            "text": "文本格式",
            "html": "交互式 HTML 网页",
        }

        if not format_input:
            current = ", ".join(self.config_manager.get_output_format())
            format_list_str = "\n".join(
                [
                    f"【{i}】{f} - {format_display_names[f]}"
                    for i, f in enumerate(available_formats, start=1)
                ]
            )
            yield event.plain_result(f"""📊 当前输出格式: {current}

可用格式:
{format_list_str}

用法: /设置格式 [名称或序号] 如 /设置格式 image,html""")
            return

        target_format = None
        # 尝试由序号选择
        if format_input.isdigit():
            idx = int(format_input) - 1
            if 0 <= idx < len(available_formats):
                target_format = available_formats[idx]

        # 尝试按名称选择
        if not target_format:
            input_lower = format_input.lower()
            if input_lower in available_formats:
                target_format = input_lower

        # 支持逗号分隔的多个格式
        if not target_format:
            parts = [f.strip() for f in format_input.replace("，", ",").split(",")]
            if all(p in available_formats for p in parts) and len(parts) > 1:
                try:
                    self.config_manager.set_output_format(parts)
                    yield event.plain_result(f"✅ 输出格式已设置为: {', '.join(parts)}")
                except Exception as e:
                    yield event.plain_result(f"❌ 设置失败: {e}")
                return

        if not target_format:
            yield event.plain_result(
                f"❌ 无效的格式类型 '{format_input}'。可用: {', '.join(available_formats)} 或序号 1-{len(available_formats)}"
            )
            return

        try:
            self.config_manager.set_output_format(target_format)  # type: ignore[arg-type]
            yield event.plain_result(f"✅ 输出格式已设置为: {target_format}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {e}")

    @filter.command("设置模板", alias={"set_template"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_report_template(
        self, event: AstrMessageEvent, template_input: str = ""
    ):
        """
        设置分析报告模板（跨平台支持）
        用法: /设置模板 [模板名称或序号]
        """
        # 命令由插件处理，禁用默认 LLM 回退。
        event.should_call_llm(True)

        available_templates = self.template_command_service.list_available_templates()

        if not template_input:
            current_template = self.config_manager.get_report_template()
            template_list_str = "\n".join(
                [f"【{i}】{t}" for i, t in enumerate(available_templates, start=1)]
            )
            yield event.plain_result(f"""🎨 当前报告模板: {current_template}

可用模板:
{template_list_str}

用法: /设置模板 [模板名称或序号]
💡 使用 /查看模板 查看预览图""")
            return

        template_name, parse_error = self.template_command_service.parse_template_input(
            template_input, available_templates
        )
        if parse_error:
            yield event.plain_result(parse_error)
            return

        if not template_name:
            yield event.plain_result(f"❌ 无法解析模板输入: {template_input}")
            return

        if not await self.template_command_service.template_exists(template_name):
            yield event.plain_result(f"❌ 模板 '{template_name}' 不存在")
            return

        self.config_manager.set_report_template(template_name)
        yield event.plain_result(f"✅ 报告模板已设置为: {template_name}")

    @filter.command("查看模板", alias={"view_templates"})
    @filter.permission_type(PermissionType.ADMIN)
    async def view_templates(self, event: AstrMessageEvent):
        """
        查看所有可用的报告模板及预览图（跨平台支持）
        用法: /查看模板
        """
        # 命令由插件处理，禁用默认 LLM 回退。
        event.should_call_llm(True)

        available_templates = self.template_command_service.list_available_templates()

        if not available_templates:
            yield event.plain_result("❌ 未找到任何可用的报告模板")
            return

        platform_id = self._get_platform_id_from_event(event)
        await self.template_preview_router.ensure_handlers_registered(self.context)
        (
            handled,
            handler_results,
        ) = await self.template_preview_router.handle_view_templates(
            event=event,
            platform_id=platform_id,
            available_templates=available_templates,
        )
        if handled:
            for result in handler_results:
                yield result
            return

        current_template = self.config_manager.get_report_template()
        bot_id = event.get_self_id()
        preview_nodes = self.template_command_service.build_template_preview_nodes(
            available_templates=available_templates,
            current_template=current_template,
            bot_id=bot_id,
        )
        yield event.chain_result([preview_nodes])

    @filter.command("分析设置", alias={"analysis_settings"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(self, event: AstrMessageEvent, action: str = "status"):
        """
        管理分析设置（跨平台支持）
        用法: /分析设置 [enable|disable|status|reload|test]
        - enable: 启用当前群的分析功能
        - disable: 禁用当前群的分析功能
        - status: 查看当前状态
        - reload: 重新加载配置并重启定时任务
        - test: 测试自动分析功能
        - filter_bot: 切换是否在分析中包含机器人自己的消息
        - incremental_debug: 切换增量分析立即报告模式（调试用）
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if action == "enable":
            async for result in self._handle_settings_enable(event, group_id):
                yield result
            return
        elif action == "disable":
            async for result in self._handle_settings_disable(event, group_id):
                yield result
            return

        elif action == "reload":
            self.auto_scheduler.schedule_jobs(self.context)
            await self._refresh_incremental_target_states()
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")
            return

        elif action == "test":
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = (
                    f"{self._get_platform_id_from_event(event)}:GroupMessage:{group_id}"
                )

            if not self.config_manager.is_group_allowed(check_target):
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            # 更新bot实例（用于测试）
            self.bot_manager.update_from_event(event)

            try:
                result = await self.auto_scheduler._perform_auto_analysis_for_group(
                    group_id
                )
                if isinstance(result, dict) and result.get("success"):
                    yield event.plain_result("✅ 自动分析及报告发送成功，请查看群消息")
                else:
                    reason = (
                        result.get("reason", "unknown")
                        if isinstance(result, dict)
                        else "invalid_result"
                    )
                    yield event.plain_result(f"❌ 自动分析或报告发送失败: {reason}")
            except DuplicateGroupTaskError:
                yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")
            return

        elif action == "incremental_debug":
            current_state = self.config_manager.get_incremental_report_immediately()
            new_state = not current_state
            self.config_manager.set_incremental_report_immediately(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 增量分析立即报告模式: {status_text}")
            return

        elif action == "filter_bot":
            current = self.config_manager.get_filter_bot_messages()
            new_state = not current
            self.config_manager.set_filter_bot_messages(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 过滤机器人消息: {status_text}")
            return

        else:  # status
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = (
                    f"{self._get_platform_id_from_event(event)}:GroupMessage:{group_id}"
                )

            is_allowed = self.config_manager.is_group_allowed(check_target)
            status = "已启用" if is_allowed else "未启用"
            mode = self.config_manager.get_group_list_mode()

            auto_status = (
                "已启用" if self.config_manager.is_auto_analysis_enabled() else "未启用"
            )
            auto_time = self.config_manager.get_auto_analysis_time()

            output_format = self.config_manager.get_output_format()[0]
            min_threshold = self.config_manager.get_min_messages_threshold()

            # 增量分析状态
            incremental_enabled = self.config_manager.get_incremental_enabled()
            incremental_status_text = "未启用"
            if incremental_enabled:
                batch_messages = self.config_manager.get_incremental_min_messages()
                incremental_status_text = f"已启用 (每 {batch_messages} 条消息触发)"

        debug_report = self.config_manager.get_incremental_report_immediately()
        debug_status = "✅ 开启" if debug_report else "❌ 关闭"
        filter_bot = self.config_manager.get_filter_bot_messages()
        filter_bot_status = "✅ 开启" if filter_bot else "❌ 关闭"

        yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time})
        • 增量分析: {incremental_status_text}
        • 调试模式: {debug_status} (增量立即报告)
        • 过滤机器人: {filter_bot_status}
        • 输出格式: {output_format}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test, filter_bot, incremental_debug
💡 支持的输出格式: image, text (图片包含活跃度可视化)
💡 其他命令: /设置格式, /增量状态""")

    @filter.command("增量状态", alias={"incremental_status"})
    @filter.permission_type(PermissionType.ADMIN)
    async def incremental_status(self, event: AstrMessageEvent):
        """查看当前增量分析状态（滑动窗口）"""
        group_id = self._get_group_id_from_event(event)
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not self.config_manager.get_incremental_enabled():
            yield event.plain_result("ℹ️ 增量分析模式未启用，请在插件配置中开启")
            return

        import time as time_mod

        # 计算滑动窗口范围
        analysis_days = self.config_manager.get_analysis_days()
        window_end = time_mod.time()
        window_start = window_end - (analysis_days * 24 * 3600)

        # 查询窗口内的批次
        batches = await self.incremental_store.query_batches(
            group_id, window_start, window_end
        )

        if not batches:
            from datetime import datetime

            start_str = datetime.fromtimestamp(window_start).strftime("%m-%d %H:%M")
            end_str = datetime.fromtimestamp(window_end).strftime("%m-%d %H:%M")
            yield event.plain_result(
                f"📊 滑动窗口 ({start_str} ~ {end_str}) 内尚无增量分析数据"
            )
            return

        # 合并批次获取聚合视图
        state = self.incremental_merge_service.merge_batches(
            batches, window_start, window_end
        )
        summary = state.get_summary()

        yield event.plain_result(
            f"📊 增量分析状态 (窗口: {summary['window']})\n"
            f"• 分析次数: {summary['total_analyses']}\n"
            f"• 累计消息: {summary['total_messages']}\n"
            f"• 话题数: {summary['topics_count']}\n"
            f"• 金句数: {summary['quotes_count']}\n"
            f"• 参与者: {summary['participants']}\n"
            f"• 高峰时段: {summary['peak_hours']}"
        )

    async def _handle_settings_enable(self, event: AstrMessageEvent, group_id: str):
        """协助逻辑：处理启用设置的分支逻辑"""
        mode = self.config_manager.get_group_list_mode()
        target_id = event.unified_msg_origin or group_id

        if mode == "whitelist":
            glist = self.config_manager.get_group_list()
            if not self.config_manager.is_group_allowed(target_id):
                glist.append(target_id)
                self.config_manager.set_group_list(glist)
                self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result(f"✅ 已将当前群加入白名单\nID: {target_id}")
            else:
                yield event.plain_result("ℹ️ 当前群已在白名单中")
        elif mode == "blacklist":
            glist = self.config_manager.get_group_list()
            removed = False
            if target_id in glist:
                glist.remove(target_id)
                removed = True
            if group_id in glist:
                glist.remove(group_id)
                removed = True

            if removed:
                self.config_manager.set_group_list(glist)
                self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result("✅ 已将当前群从黑名单移除")
            else:
                yield event.plain_result("ℹ️ 当前群不在黑名单中")
        else:
            yield event.plain_result("ℹ️ 当前为无限制模式，所有群聊默认启用")

    async def _handle_settings_disable(self, event: AstrMessageEvent, group_id: str):
        """协助逻辑：处理禁用设置的分支逻辑"""
        mode = self.config_manager.get_group_list_mode()
        target_id = event.unified_msg_origin or group_id

        if mode == "whitelist":
            glist = self.config_manager.get_group_list()
            removed = False
            if target_id in glist:
                glist.remove(target_id)
                removed = True
            if group_id in glist:
                glist.remove(group_id)
                removed = True

            if removed:
                self.config_manager.set_group_list(glist)
                self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result("✅ 已将当前群从白名单移除")
            else:
                yield event.plain_result("ℹ️ 当前群不在白名单中")
        elif mode == "blacklist":
            glist = self.config_manager.get_group_list()
            if self.config_manager.is_group_allowed(target_id):
                glist.append(target_id)
                self.config_manager.set_group_list(glist)
                self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result(f"✅ 已将当前群加入黑名单\nID: {target_id}")
            else:
                yield event.plain_result("ℹ️ 当前群已在黑名单中")
        else:
            yield event.plain_result("ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式")

    async def _refresh_incremental_target_states(self) -> None:
        """在插件内修改名单后立即同步增量状态。"""
        incremental_trigger = self.auto_scheduler.incremental_trigger
        if incremental_trigger:
            await incremental_trigger.refresh_target_states()
