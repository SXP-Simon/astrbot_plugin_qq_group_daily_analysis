"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，支持跨平台
"""

import asyncio
import os
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star
from astrbot.core.message.components import File

from .src.application.analysis_orchestrator import AnalysisConfig, AnalysisOrchestrator
from .src.core.bot_manager import BotManager
from .src.core.config import ConfigManager
from .src.core.history_manager import HistoryManager
from .src.reports.generators import ReportGenerator
from .src.scheduler.auto_scheduler import AutoScheduler
from .src.scheduler.retry import RetryManager
from .src.utils.helpers import MessageAnalyzer
from .src.utils.pdf_utils import PDFInstaller


class QQGroupDailyAnalysis(Star):
    """QQ群日常分析插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化模块化组件（使用实例属性而非全局变量）
        self.config_manager = ConfigManager(config)
        self.bot_manager = BotManager(self.config_manager)
        self.bot_manager.set_context(context)
        self.message_analyzer = MessageAnalyzer(
            context, self.config_manager, self.bot_manager
        )
        self.report_generator = ReportGenerator(self.config_manager)
        self.history_manager = HistoryManager(self)
        self.retry_manager = RetryManager(
            self.bot_manager, self.html_render, self.report_generator
        )
        self.auto_scheduler = AutoScheduler(
            self.config_manager,
            self.message_analyzer.message_handler,
            self.message_analyzer,
            self.report_generator,
            self.bot_manager,
            self.retry_manager,
            self.history_manager,
            self.html_render,  # 传入html_render函数
        )

        # 注册分析编排器缓存
        self.orchestrators = {}  # {platform_id: AnalysisOrchestrator}

        # 注册日志过滤器
        from .src.utils.trace_context import TraceLogFilter

        logger.addFilter(TraceLogFilter())

        logger.info("QQ群日常分析插件已初始化（模块化版本）")

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从事件中提取群组ID（跨平台兼容）"""
        # 使用正确的 AstrMessageEvent API
        if hasattr(event, "get_group_id"):
            group_id = event.get_group_id()
            return str(group_id) if group_id else None
        if hasattr(event, "message_obj") and hasattr(event.message_obj, "group_id"):
            group_id = event.message_obj.group_id
            return str(group_id) if group_id else None
        return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从事件中提取平台ID（跨平台兼容）"""
        # 使用正确的 AstrMessageEvent API
        if hasattr(event, "get_platform_id"):
            return event.get_platform_id()
        if hasattr(event, "platform_meta") and hasattr(event.platform_meta, "id"):
            return event.platform_meta.id
        return None

    def _get_platform_name_from_event(self, event: AstrMessageEvent) -> str | None:
        """从事件中提取平台名称（如 discord, aiocqhttp 等）"""
        # 使用正确的 AstrMessageEvent API
        if hasattr(event, "get_platform_name"):
            return event.get_platform_name()
        if hasattr(event, "platform_meta") and hasattr(event.platform_meta, "name"):
            return event.platform_meta.name
        return None

    def _get_orchestrator(
        self,
        platform_id: str,
        platform_name: str | None = None,
        bot_instance: Any = None,
    ) -> AnalysisOrchestrator | None:
        """获取或创建分析编排器"""
        if platform_id in self.orchestrators:
            return self.orchestrators[platform_id]

        # 如果缓存中没有，尝试创建
        if not bot_instance:
            bot_instance = self.bot_manager.get_bot_instance(platform_id)

        if not bot_instance:
            return None

        # 检测平台名称（优先使用传入的 platform_name）
        if not platform_name:
            platform_name = self.bot_manager._detect_platform_name(bot_instance)
        if not platform_name:
            return None

        # 创建编排器
        analysis_config = AnalysisConfig(
            days=self.config_manager.get_analysis_days(),
            min_messages_threshold=self.config_manager.get_min_messages_threshold(),
            max_messages=self.config_manager.get_max_messages(),
            output_format=self.config_manager.get_output_format(),
        )

        orchestrator = AnalysisOrchestrator.create_for_platform(
            platform_name,
            bot_instance,
            config={"bot_self_ids": self.config_manager.get_bot_self_ids()},
            analysis_config=analysis_config,
        )

        if orchestrator:
            self.orchestrators[platform_id] = orchestrator

        return orchestrator

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        try:
            # 检查插件是否被启用 (Fix for empty plugin_set issue)
            if self.context:
                config = self.context.get_config()
                plugin_set = config.get("plugin_set")

                if isinstance(plugin_set, list) and not plugin_set:
                    logger.warning("检测到 plugin_set 为空，自动修正以启用插件")
                    config["plugin_set"].append(
                        "astrbot_plugin_qq_group_daily_analysis"
                    )
                elif (
                    isinstance(plugin_set, list)
                    and "*" not in plugin_set
                    and "astrbot_plugin_qq_group_daily_analysis" not in plugin_set
                ):
                    logger.warning("检测到当前插件未在 plugin_set 中，自动添加")
                    config["plugin_set"].append(
                        "astrbot_plugin_qq_group_daily_analysis"
                    )

            # 初始化所有bot实例
            discovered = await self.bot_manager.initialize_from_config()
            if discovered:
                platform_count = len(discovered)
                logger.info(f"Bot管理器初始化成功，发现 {platform_count} 个适配器")
                for platform_id, bot_instance in discovered.items():
                    logger.info(
                        f"  - 平台 {platform_id}: {type(bot_instance).__name__}"
                    )
                    # 预先创建编排器
                    self._get_orchestrator(platform_id, bot_instance=bot_instance)

                # 启动调度器
                self.auto_scheduler.schedule_jobs(self.context)
            else:
                logger.warning("Bot管理器初始化失败，未发现任何适配器")
                status = self.bot_manager.get_status_info()
                logger.info(f"Bot管理器状态: {status}")

            # 始终启动重试管理器
            await self.retry_manager.start()

        except Exception as e:
            logger.error(f"平台加载事件处理失败: {e}", exc_info=True)

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        try:
            logger.info("开始清理QQ群日常分析插件资源...")

            # 停止自动调度器
            if self.auto_scheduler:
                logger.info("正在停止自动调度器...")
                self.auto_scheduler.unschedule_jobs(self.context)
                logger.info("自动调度器已停止")

            if self.retry_manager:
                await self.retry_manager.stop()

            # 重置实例属性
            self.auto_scheduler = None
            self.bot_manager = None
            self.message_analyzer = None
            self.report_generator = None
            self.config_manager = None
            self.orchestrators = {}

            logger.info("QQ群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    @filter.command("群分析", alias={"group_analysis"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AstrMessageEvent, days: int | None = None
    ):
        """
        分析群聊日常活动（跨平台支持）
        用法: /群分析 [天数]
        """
        # 1. 获取 group_id, platform_id 和 platform_name
        group_id = self._get_group_id_from_event(event)
        platform_id = self._get_platform_id_from_event(event)
        platform_name = self._get_platform_name_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        # 更新bot实例（用于手动命令）
        if hasattr(event, "bot"):
            self.bot_manager.update_from_event(event)

        # 2. 检查群组权限
        if not self.config_manager.is_group_allowed(group_id):
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return

        # 3. 设置分析天数
        analysis_days = (
            days if days and 1 <= days <= 7 else self.config_manager.get_analysis_days()
        )

        yield event.plain_result(f"🔍 开始分析群聊近{analysis_days}天的活动，请稍候...")
        logger.info(
            f"收到分析请求: group_id={group_id}, platform_id={platform_id}, platform_name={platform_name}, days={analysis_days}"
        )

        try:
            # 4. 获取编排器
            # 首先尝试从 event 直接提取 bot 客户端
            bot_from_event = None
            if hasattr(event, "client"):  # Discord 平台有 client 属性
                bot_from_event = event.client
            elif hasattr(event, "bot"):  # 其他平台可能有 bot 属性
                bot_from_event = event.bot

            orchestrator = self._get_orchestrator(
                platform_id, platform_name, bot_from_event
            )
            if not orchestrator:
                # 尝试使用 bot_manager 获取 bot 实例再创建
                bot_instance = self.bot_manager.get_bot_instance(platform_id)
                if bot_instance:
                    orchestrator = self._get_orchestrator(
                        platform_id, platform_name, bot_instance
                    )

            if not orchestrator:
                yield event.plain_result(
                    f"❌ 未找到平台 {platform_name or platform_id} 的分析编排器，请检查配置或联系开发者"
                )
                return

            # 5. 获取群聊消息 (使用编排器)
            messages = await orchestrator.fetch_messages_as_raw(
                group_id=group_id, days=analysis_days
            )

            if not messages:
                yield event.plain_result(
                    "❌ 未找到足够的群聊记录，请确保群内有足够的消息历史"
                )
                return

            # 检查消息数量是否足够分析
            min_threshold = self.config_manager.get_min_messages_threshold()
            if len(messages) < min_threshold:
                yield event.plain_result(
                    f"❌ 消息数量不足（{len(messages)}条），至少需要{min_threshold}条消息才能进行有效分析"
                )
                return

            yield event.plain_result(
                f"📊 已获取{len(messages)}条消息，正在进行智能分析..."
            )

            # 6. 进行分析
            analysis_result = await self.message_analyzer.analyze_messages(
                messages, group_id, event.unified_msg_origin
            )

            if not analysis_result or not analysis_result.get("statistics"):
                yield event.plain_result("❌ 分析过程中出现错误，请稍后重试")
                return

            # 7. 保存到历史记录
            await self.history_manager.save_analysis(group_id, analysis_result)

            # 8. 生成并发送报告
            output_format = self.config_manager.get_output_format()

            # 定义头像获取回调
            async def avatar_getter(user_id: str) -> str | None:
                if not orchestrator:
                    return None
                try:
                    # orchestrator.get_member_avatars 接受列表返回字典
                    avatars = await orchestrator.get_member_avatars([user_id])
                    return avatars.get(user_id)
                except Exception as e:
                    logger.warning(f"获取头像失败 {user_id}: {e}")
                    return None

            if output_format == "image":
                (
                    image_url,
                    html_content,
                ) = await self.report_generator.generate_image_report(
                    analysis_result,
                    group_id,
                    self.html_render,
                    avatar_getter=avatar_getter,
                )

                if image_url:
                    # 使用编排器发送图片
                    if await orchestrator.send_image(group_id, image_url):
                        logger.info(f"图片报告发送成功: {group_id}")
                    else:
                        yield event.image_result(image_url)

                elif html_content:
                    # 生成失败但有HTML，加入重试队列
                    logger.warning("图片报告生成失败，加入重试队列")
                    yield event.plain_result(
                        "[AstrBot QQ群日常分析总结插件] ⚠️ 图片报告暂无法生成，已加入重试队列，稍后将自动重试发送。"
                    )
                    await self.retry_manager.add_task(
                        html_content, analysis_result, group_id, platform_id
                    )
                else:
                    # 回退到文本报告
                    logger.warning("图片报告生成失败（无HTML），回退到文本报告")
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    yield event.plain_result(
                        f"[AstrBot QQ群日常分析总结插件] ⚠️ 图片报告生成失败，以下是文本版本：\n\n{text_report}"
                    )

            elif output_format == "pdf":
                if not self.config_manager.playwright_available:
                    yield event.plain_result(
                        "❌ PDF 功能不可用，请使用 /安装PDF 命令安装依赖"
                    )
                    return

                pdf_path = await self.report_generator.generate_pdf_report(
                    analysis_result, group_id, avatar_getter=avatar_getter
                )

                if pdf_path:
                    # 使用编排器发送文件
                    if await orchestrator.send_file(group_id, pdf_path):
                        pass  # 发送成功
                    else:
                        from pathlib import Path

                        pdf_file = File(name=Path(pdf_path).name, file=pdf_path)
                        result = event.make_result()
                        result.chain.append(pdf_file)
                        yield result
                else:
                    logger.warning("PDF 报告生成失败，回退到文本报告")
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    yield event.plain_result(
                        f"\n📝 以下是文本版本的分析报告：\n\n{text_report}"
                    )
            else:
                # 文本报告
                text_report = self.report_generator.generate_text_report(
                    analysis_result
                )
                if not await orchestrator.send_text(group_id, text_report):
                    yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )

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
        # 获取模板目录和可用模板列表
        template_base_dir = os.path.join(
            os.path.dirname(__file__), "src", "reports", "templates"
        )

        def _list_templates_sync():
            if os.path.exists(template_base_dir):
                return sorted(
                    [
                        d
                        for d in os.listdir(template_base_dir)
                        if os.path.isdir(os.path.join(template_base_dir, d))
                        and not d.startswith("__")
                    ]
                )
            return []

        available_templates = await asyncio.to_thread(_list_templates_sync)

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

        # 判断输入是序号还是模板名称
        template_name = template_input
        if template_input.isdigit():
            index = int(template_input)
            if 1 <= index <= len(available_templates):
                template_name = available_templates[index - 1]
            else:
                yield event.plain_result(
                    f"❌ 无效的序号 '{template_input}'，有效范围: 1-{len(available_templates)}"
                )
                return

        # 检查模板是否存在
        template_dir = os.path.join(template_base_dir, template_name)
        template_exists = await asyncio.to_thread(os.path.exists, template_dir)
        if not template_exists:
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
        from astrbot.api.message_components import Image, Node, Nodes, Plain

        # 获取模板目录
        template_dir = os.path.join(
            os.path.dirname(__file__), "src", "reports", "templates"
        )
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        def _list_templates_sync():
            if os.path.exists(template_dir):
                return sorted(
                    [
                        d
                        for d in os.listdir(template_dir)
                        if os.path.isdir(os.path.join(template_dir, d))
                        and not d.startswith("__")
                    ]
                )
            return []

        available_templates = await asyncio.to_thread(_list_templates_sync)

        if not available_templates:
            yield event.plain_result("❌ 未找到任何可用的报告模板")
            return

        current_template = self.config_manager.get_report_template()

        # 获取机器人信息用于合并转发消息
        bot_id = event.get_self_id()
        bot_name = "模板预览"

        # 圆圈数字序号
        circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

        # 构建合并转发消息节点列表
        node_list = []

        # 添加标题节点
        header_content = [
            Plain(
                f"🎨 可用报告模板列表\n📌 当前使用: {current_template}\n💡 使用 /设置模板 [序号] 切换"
            )
        ]
        node_list.append(Node(uin=bot_id, name=bot_name, content=header_content))

        # 为每个模板创建一个节点
        for index, template_name in enumerate(available_templates):
            current_mark = " ✅" if template_name == current_template else ""
            num_label = (
                circle_numbers[index]
                if index < len(circle_numbers)
                else f"({index + 1})"
            )

            node_content = [Plain(f"{num_label} {template_name}{current_mark}")]

            # 添加预览图
            preview_image_path = os.path.join(assets_dir, f"{template_name}-demo.jpg")
            if os.path.exists(preview_image_path):
                node_content.append(Image.fromFileSystem(preview_image_path))

            node_list.append(Node(uin=bot_id, name=template_name, content=node_content))

        # 使用 Nodes 包装成一个合并转发消息
        yield event.chain_result([Nodes(node_list)])

    @filter.command("安装PDF", alias={"install_pdf"})
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: AstrMessageEvent):
        """
        安装 PDF 功能依赖（跨平台支持）
        用法: /安装PDF
        """
        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            result = await PDFInstaller.install_playwright(self.config_manager)
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
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        elif action == "enable":
            mode = self.config_manager.get_group_list_mode()
            target_id = event.unified_msg_origin or group_id  # 优先使用 UMO

            if mode == "whitelist":
                glist = self.config_manager.get_group_list()
                # 检查 UMO 或 Group ID 是否已在列表中
                if not self.config_manager.is_group_allowed(target_id):
                    glist.append(target_id)
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result(
                        f"✅ 已将当前群加入白名单\nID: {target_id}"
                    )
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群已在白名单中")
            elif mode == "blacklist":
                glist = self.config_manager.get_group_list()

                # 尝试移除 UMO 和 Group ID
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

        elif action == "disable":
            mode = self.config_manager.get_group_list_mode()
            target_id = event.unified_msg_origin or group_id  # 优先使用 UMO

            if mode == "whitelist":
                glist = self.config_manager.get_group_list()

                # 尝试移除 UMO 和 Group ID
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
                # 检查 UMO 或 Group ID 是否已在列表中
                if self.config_manager.is_group_allowed(
                    target_id
                ):  # 如果允许，说明不在黑名单
                    glist.append(target_id)
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result(
                        f"✅ 已将当前群加入黑名单\nID: {target_id}"
                    )
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群已在黑名单中")
            else:
                yield event.plain_result(
                    "ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式"
                )

        elif action == "reload":
            self.auto_scheduler.schedule_jobs(self.context)
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")

        elif action == "test":
            if not self.config_manager.is_group_allowed(group_id):
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            # 更新bot实例（用于测试）
            self.bot_manager.update_from_event(event)

            try:
                await self.auto_scheduler._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 自动分析测试完成，请查看群消息")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")

        else:  # status
            is_allowed = self.config_manager.is_group_allowed(group_id)
            status = "已启用" if is_allowed else "未启用"
            mode = self.config_manager.get_group_list_mode()

            auto_status = (
                "已启用" if self.config_manager.get_enable_auto_analysis() else "未启用"
            )
            auto_time = self.config_manager.get_auto_analysis_time()

            pdf_status = PDFInstaller.get_pdf_status(self.config_manager)
            output_format = self.config_manager.get_output_format()
            min_threshold = self.config_manager.get_min_messages_threshold()

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time})
• 输出格式: {output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test
💡 支持的输出格式: image, text, pdf (图片和PDF包含活跃度可视化)
💡 其他命令: /设置格式, /安装PDF""")
