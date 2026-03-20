"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，支持跨平台
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from astrbot.api import AstrBotConfig
from astrbot.api import logger as astrbot_logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star
from astrbot.core.message.components import File

from .src.application.commands.template_command_service import (
    TemplateCommandService,
)
from .src.application.services.analysis_application_service import (
    AnalysisApplicationService,
    DuplicateGroupTaskError,
)
from .src.application.services.message_processing_service import (
    MessageProcessingService,
)
from .src.domain.services.analysis_domain_service import AnalysisDomainService
from .src.domain.services.incremental_merge_service import IncrementalMergeService
from .src.domain.services.statistics_service import StatisticsService
from .src.infrastructure.analysis.llm_analyzer import LLMAnalyzer
from .src.infrastructure.config.config_manager import ConfigManager
from .src.infrastructure.persistence.history_manager import HistoryManager
from .src.infrastructure.persistence.incremental_store import IncrementalStore
from .src.infrastructure.persistence.telegram_group_registry import (
    TelegramGroupRegistry,
)
from .src.infrastructure.platform.bot_manager import BotManager
from .src.infrastructure.platform.template_preview import (
    TelegramTemplatePreviewHandler,
    TemplatePreviewRouter,
)
from .src.infrastructure.reporting.generators import ReportGenerator
from .src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from .src.infrastructure.scheduler.retry import RetryManager
from .src.shared.trace_context import TraceContext, TraceLogFilter
from .src.utils.logger import logger
from .src.utils.pdf_utils import PDFInstaller


class GroupDailyAnalysis(Star):
    """群分析插件主类"""

    # ── 显式类型声明 (由 __init__ 初始化) ──
    config: AstrBotConfig
    config_manager: ConfigManager
    bot_manager: BotManager
    history_manager: HistoryManager
    report_generator: ReportGenerator
    telegram_group_registry: TelegramGroupRegistry
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
    retry_manager: RetryManager
    auto_scheduler: AutoScheduler

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 1. 基础设施层
        self.config_manager = ConfigManager(config)
        self.bot_manager = BotManager(self.config_manager)
        self.bot_manager.set_context(context)
        self.bot_manager.set_plugin_instance(self)
        self.history_manager = HistoryManager(self)
        self.report_generator = ReportGenerator(self.config_manager)

        # Telegram 注册表 (持久层)
        self.telegram_group_registry = TelegramGroupRegistry(self)

        # 2. 领域层
        self.statistics_service = StatisticsService()
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
        )

        # 消息处理服务
        self.message_processing_service = MessageProcessingService(
            context, self.telegram_group_registry
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

        # 调度与重试
        self.retry_manager = RetryManager(
            self.bot_manager, self.html_render, self.report_generator
        )
        self.auto_scheduler = AutoScheduler(
            self.config_manager,
            self.analysis_service,
            self.bot_manager,
            self.retry_manager,
            self.report_generator,
            self.html_render,
            plugin_instance=self,
        )

        self._initialized = False
        self._discovery_run = False  # 是否已尝试过运行发现逻辑
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
            # 如果当前没有 running loop (例如在非异步初始化的环境中)，
            # 则依赖 on_platform_loaded 钩子执行初始化
            self._init_task = None

    # orchestrators 缓存已移至 应用层逻辑 (分析服务) 或 暂时移除以简化。
    # 如果需要高性能缓存，后续可由 AnalysisApplicationService 内部维护。

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        await self._run_initialization("Platform Loaded")

    async def _run_initialization(self, source: str):
        """统一初始化逻辑"""
        async with self._init_lock:
            # 如果已经成功发现过平台，且不是来自 Platform Loaded 的强制触发，则跳过
            if (
                self._initialized
                and self.bot_manager
                and self.bot_manager.get_platform_count() > 0
                and source != "Platform Loaded"
            ):
                return

            # 稍微延迟，确保 context 和环境稳定
            # 针对极少数环境，2秒可能不足以让平台管理器就绪，增加到 5秒
            await asyncio.sleep(5)

            # [加固] 如果在等待期间插件已被卸载（terminate），则直接退出
            if not self.bot_manager:
                return

            try:
                # 注册 TraceID 过滤器
                trace_filter = TraceLogFilter()
                if not any(
                    isinstance(f, TraceLogFilter) for f in astrbot_logger.filters
                ):
                    astrbot_logger.addFilter(trace_filter)
                    astrbot_logger.info("[Trace] TraceID 日志追踪已启用")

                logger.info(f"正在执行插件初始化 (来源: {source})...")

                # 1. 尝试发现 bot 实例
                await self.bot_manager.initialize_from_config()

                # 2. 注册预览路由器
                if self.template_preview_router:
                    await self.template_preview_router.ensure_handlers_registered(
                        self.context
                    )

                # 3. 强制注册定时分析任务
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)

                # 4. 始终启动重试管理器
                if self.retry_manager:
                    await self.retry_manager.start()

                self._initialized = True
                self._discovery_run = True
                logger.info(f"插件任务注册完成 (来源: {source})")

            except Exception as e:
                logger.error(f"插件初始化失败: {e}", exc_info=True)

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        try:
            logger.info("开始清理QQ群日常分析插件资源...")

            # 1. 停止所有后台任务
            if self._background_tasks:
                logger.info(f"正在取消 {len(self._background_tasks)} 个后台任务...")
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()

                # 等待任务结束
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
                self._background_tasks.clear()

            # 2. 停止各个组件
            if self.auto_scheduler:
                logger.info("正在停止自动调度器...")
                self.auto_scheduler.unschedule_jobs(self.context)

            if self.retry_manager:
                await self.retry_manager.stop()

            if self.template_preview_router:
                await self.template_preview_router.unregister_handlers()

            # 3. 释放实例属性引用 (使用 type: ignore 允许 None 赋值)
            self.auto_scheduler = None  # type: ignore
            self.bot_manager = None  # type: ignore
            self.report_generator = None  # type: ignore
            self.config_manager = None  # type: ignore
            self.message_processing_service = None  # type: ignore
            self.telegram_group_registry = None  # type: ignore
            self.template_preview_router = None  # type: ignore
            self.telegram_template_preview_handler = None  # type: ignore

            logger.info("QQ群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    # ==================== Telegram 消息拦截器 ====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(filter.PlatformAdapterType.TELEGRAM)
    async def intercept_telegram_messages(self, event: AstrMessageEvent):
        """
        拦截 Telegram 群消息并存储到数据库

        委托给 MessageProcessingService 处理
        """
        try:
            await self.message_processing_service.process_message(event)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"[Telegram] 消息存储失败: {e}")
        except Exception as e:
            logger.error(f"[Telegram] 消息存储异常: {e}", exc_info=True)

    async def get_telegram_seen_group_ids(
        self, platform_id: str | None = None
    ) -> list[str]:
        """读取 Telegram 已见群/话题列表（给调度器回退使用）。"""
        return await self.telegram_group_registry.get_all_group_ids(platform_id)

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

    async def _try_upload_image(self, group_id: str, image_url: str, platform_id: str):
        """
        尝试将图片报告上传到群文件和/或群相册（静默处理，失败仅日志提示）。
        """
        import base64
        import re
        import tempfile
        from datetime import datetime

        enable_file = self.config_manager.get_enable_group_file_upload()
        enable_album = self.config_manager.get_enable_group_album_upload()
        if not enable_file and not enable_album:
            return

        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter or not hasattr(adapter, "upload_group_file_to_folder"):
            return

        # 1. 构造一个更友好的文件名
        now = datetime.now()
        timestamp = now.strftime("%H%M")
        date_str = now.strftime("%Y-%m-%d")

        # 默认基础名和后缀
        ext = (
            ".jpg"
            if (".jpg" in image_url.lower() or ".jpeg" in image_url.lower())
            else ".png"
        )
        nice_filename = f"群分析报告_{group_id}_{date_str}_{timestamp}{ext}"

        try:
            # 尝试通过适配器获取群名称，使文件名更具辨识度
            group_info = await adapter.get_group_info(group_id)
            if group_info and group_info.group_name:
                # 过滤非法文件名字符：\ / : * ? " < > |
                safe_name = re.sub(r'[\\/:*?"<>|]', "", group_info.group_name).strip()
                if safe_name:
                    nice_filename = (
                        f"群分析报告_{safe_name}_{date_str}_{timestamp}{ext}"
                    )
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

            if enable_album and hasattr(adapter, "upload_group_album"):
                try:
                    album_name = self.config_manager.get_group_album_name()
                    strict_mode = self.config_manager.get_group_album_strict_mode()
                    album_id = None
                    if hasattr(adapter, "find_album_id"):
                        if album_name:
                            album_id = await adapter.find_album_id(group_id, album_name)  # type: ignore[attr-defined]
                            if not album_id and strict_mode:
                                logger.info(
                                    f"群相册严格模式开启：在群 {group_id} 中未找到名为 '{album_name}' 的相册，停止上传。"
                                )
                                return
                        elif strict_mode:
                            logger.info(
                                f"群相册严格模式开启：未设置目标相册名称，停止上传以防止操作群 {group_id} 的默认相册。"
                            )
                            return
                    await adapter.upload_group_album(  # type: ignore[attr-defined]
                        group_id,
                        image_file,
                        album_id=album_id,
                        album_name=album_name,
                        strict_mode=strict_mode,
                    )
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
        TraceContext.set(trace_id)

        # 使用表情回应代替文本回复
        adapter = self.bot_manager.get_adapter(platform_id)
        orig_msg_id = getattr(event.message_obj, "message_id", None)
        if adapter and orig_msg_id:
            await adapter.set_reaction(event.get_group_id(), orig_msg_id, "🔍")  # 🔍

        try:
            # 调用 DDD 应用级服务
            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id, platform_id=platform_id, manual=True, days=days
            )

            if not result.get("success"):
                reason = result.get("reason")
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到足够的群聊记录")
                else:
                    yield event.plain_result("❌ 分析失败，原因未知")
                return

            if adapter and orig_msg_id:
                await adapter.set_reaction(
                    event.get_group_id(), orig_msg_id, "📊"
                )  # 📊

            async for res in self._send_analysis_report(event, result):
                yield res

        except DuplicateGroupTaskError:
            yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )

    async def _send_analysis_report(
        self, event: AstrMessageEvent, result: dict
    ) -> AsyncGenerator:
        """处理分析结果的渲染和发送"""
        group_id = result["group_id"]
        platform_id = result["platform_id"]
        analysis_result = result["analysis_result"]
        adapter = result["adapter"]
        output_format = self.config_manager.get_output_format()

        # 定义获取回调
        async def avatar_getter(user_id: str) -> str | None:
            return await adapter.get_user_avatar_url(user_id)

        async def nickname_getter(user_id: str) -> str | None:
            try:
                member = await adapter.get_member_info(group_id, user_id)
                if member:
                    return member.card or member.nickname
            except Exception:
                pass
            return None

        if output_format == "image":
            image_url, html_content = await self.report_generator.generate_image_report(
                analysis_result,
                group_id,
                self.html_render,
                avatar_getter=avatar_getter,
                nickname_getter=nickname_getter,
            )

            if image_url:
                caption = TraceContext.make_report_caption()
                await adapter.send_image(group_id, image_url, caption=caption)
                await self._try_upload_image(group_id, image_url, platform_id)
            elif html_content:
                yield event.plain_result("⚠️ 群分析报告图片发送失败，自动重试中。")
                caption = TraceContext.make_report_caption()
                await self.retry_manager.add_task(
                    html_content,
                    analysis_result,
                    group_id,
                    platform_id,
                    caption=caption,
                )
            else:
                text_report = self.report_generator.generate_text_report(
                    analysis_result
                )
                yield event.plain_result(f"⚠️ 图片生成失败，回退文本：\n\n{text_report}")

        elif output_format == "pdf":
            pdf_path = await self.report_generator.generate_pdf_report(
                analysis_result,
                group_id,
                avatar_getter=avatar_getter,
                nickname_getter=nickname_getter,
            )
            if pdf_path:
                if not await adapter.send_file(group_id, pdf_path):
                    yield event.chain_result(
                        [File(name=Path(pdf_path).name, file=pdf_path)]
                    )
            else:
                yield event.plain_result("⚠️ PDF 生成失败。")

        else:
            text_report = self.report_generator.generate_text_report(analysis_result)
            if not await adapter.send_text(group_id, text_report):
                yield event.plain_result(text_report)

    @filter.command("设置格式", alias={"set_format"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: AstrMessageEvent, format_type: str = ""):
        """
        设置分析报告输出格式（跨平台支持）
        用法: /设置格式 [image|text|pdf]
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not format_type:
            current_format = self.config_manager.get_output_format()
            pdf_status = (
                "✅"
                if self.config_manager.playwright_available
                else "❌ (需安装 Playwright)"
            )
            yield event.plain_result(f"""📊 当前输出格式: {current_format}

可用格式:
• image - 图片格式 (默认)
• text - 文本格式
• pdf - PDF 格式 {pdf_status}

用法: /设置格式 [格式名称]""")
            return

        format_type = format_type.lower()
        if format_type not in ["image", "text", "pdf"]:
            yield event.plain_result("❌ 无效的格式类型，支持: image, text, pdf")
            return

        if format_type == "pdf" and not self.config_manager.playwright_available:
            yield event.plain_result("❌ PDF 格式不可用，请使用 /安装PDF 命令安装依赖")
            return

        self.config_manager.set_output_format(format_type)
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

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

        available_templates = (
            await self.template_command_service.list_available_templates()
        )

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

        available_templates = (
            await self.template_command_service.list_available_templates()
        )

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

    @filter.command("安装PDF", alias={"install_pdf"})
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: AstrMessageEvent):
        """
        安装 PDF 功能依赖（跨平台支持）
        用法: /安装PDF
        """
        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            result = await PDFInstaller.install_playwright(
                self.config_manager, task_registry=self._background_tasks
            )
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"安装 PDF 依赖失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 安装过程中出现错误: {str(e)}")

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
        - incremental_debug: 切换增量分析立即报告模式（调试用）
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if action == "enable":
            async for result in self._handle_settings_enable(event, group_id):
                yield result
        elif action == "disable":
            async for result in self._handle_settings_disable(event, group_id):
                yield result

        elif action == "reload":
            self.auto_scheduler.schedule_jobs(self.context)
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")

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
                await self.auto_scheduler._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 自动分析测试完成，请查看群消息")
            except DuplicateGroupTaskError:
                yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")

        elif action == "incremental_debug":
            current_state = self.config_manager.get_incremental_report_immediately()
            new_state = not current_state
            self.config_manager.set_incremental_report_immediately(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 增量分析立即报告模式: {status_text}")

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
                "已启用" if self.config_manager.get_enable_auto_analysis() else "未启用"
            )
            auto_time = self.config_manager.get_auto_analysis_time()

            pdf_status = PDFInstaller.get_pdf_status(self.config_manager)
            output_format = self.config_manager.get_output_format()
            min_threshold = self.config_manager.get_min_messages_threshold()

            # 增量分析状态
            incremental_enabled = self.config_manager.get_incremental_enabled()
            incremental_status_text = "未启用"
            if incremental_enabled:
                interval = self.config_manager.get_incremental_interval_minutes()
                max_daily = self.config_manager.get_incremental_max_daily_analyses()
                active_start = self.config_manager.get_incremental_active_start_hour()
                active_end = self.config_manager.get_incremental_active_end_hour()
                incremental_status_text = (
                    f"已启用 (间隔{interval}分钟, 最多{max_daily}次/天, "
                    f"活跃时段{active_start}:00-{active_end}:00)"
                )

            debug_report = self.config_manager.get_incremental_report_immediately()
            debug_status = "✅ 开启" if debug_report else "❌ 关闭"

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time})
• 增量分析: {incremental_status_text}
• 调试模式: {debug_status} (增量立即报告)
• 输出格式: {output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test, incremental_debug
💡 支持的输出格式: image, text, pdf (图片和PDF包含活跃度可视化)
💡 其他命令: /设置格式, /安装PDF, /增量状态""")

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
                yield event.plain_result(f"✅ 已将当前群加入白名单\nID: {target_id}")
                self.auto_scheduler.schedule_jobs(self.context)
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
                yield event.plain_result("✅ 已将当前群从黑名单移除")
                self.auto_scheduler.schedule_jobs(self.context)
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
                yield event.plain_result("✅ 已将当前群从白名单移除")
                self.auto_scheduler.schedule_jobs(self.context)
            else:
                yield event.plain_result("ℹ️ 当前群不在白名单中")
        elif mode == "blacklist":
            glist = self.config_manager.get_group_list()
            if self.config_manager.is_group_allowed(target_id):
                glist.append(target_id)
                self.config_manager.set_group_list(glist)
                yield event.plain_result(f"✅ 已将当前群加入黑名单\nID: {target_id}")
                self.auto_scheduler.schedule_jobs(self.context)
            else:
                yield event.plain_result("ℹ️ 当前群已在黑名单中")
        else:
            yield event.plain_result("ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式")
