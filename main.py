"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，支持跨平台
"""

import asyncio
import os

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star
from astrbot.core.message.components import File

from .src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from .src.domain.services.analysis_domain_service import AnalysisDomainService
from .src.domain.services.statistics_service import StatisticsService
from .src.infrastructure.analysis.llm_analyzer import LLMAnalyzer
from .src.infrastructure.config.config_manager import ConfigManager
from .src.infrastructure.persistence.history_manager import HistoryManager
from .src.infrastructure.platform.bot_manager import BotManager
from .src.infrastructure.reporting.generators import ReportGenerator
from .src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from .src.infrastructure.scheduler.retry import RetryManager
from .src.utils.pdf_utils import PDFInstaller


class QQGroupDailyAnalysis(Star):
    """QQ群日常分析插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 1. 基础设施层
        self.config_manager = ConfigManager(config)
        self.bot_manager = BotManager(self.config_manager)
        self.bot_manager.set_context(context)
        self.history_manager = HistoryManager(self)
        self.report_generator = ReportGenerator(self.config_manager)

        # 2. 领域层
        self.statistics_service = StatisticsService()
        self.analysis_domain_service = AnalysisDomainService()

        # 3. 分析核心 (LLM Bridge)
        self.llm_analyzer = LLMAnalyzer(context, self.config_manager)

        # 4. 应用层
        self.analysis_service = AnalysisApplicationService(
            self.config_manager,
            self.bot_manager,
            self.history_manager,
            self.report_generator,
            self.llm_analyzer,
            self.statistics_service,
            self.analysis_domain_service,
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
            self.html_render,
        )

    # orchestrators 缓存已移至 应用层逻辑 (分析服务) 或 暂时移除以简化。
    # 如果需要高性能缓存，后续可由 AnalysisApplicationService 内部维护。

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        try:
            # 检查插件是否被启用 (Fix for empty plugin_set issue)
            if self.context:
                config = self.context.get_config()
                plugin_set = config.get("plugin_set")

                # ！！！仅开发阶段使用，正式发布后删除！！！
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
                logger.info("Bot管理器初始化成功")
                for platform_id, bot_instance in discovered.items():
                    logger.info(
                        f"  - 平台 {platform_id}: {type(bot_instance).__name__}"
                    )

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
            self.report_generator = None
            self.config_manager = None

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
        group_id = self._get_group_id_from_event(event)
        platform_id = self._get_platform_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        # 更新bot实例
        self.bot_manager.update_from_event(event)

        if not self.config_manager.is_group_allowed(group_id):
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return

        yield event.plain_result("🔍 正在启动跨平台分析引擎，正在拉取最近消息...")

        try:
            # 调用 DDD 应用级服务
            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id, platform_id=platform_id, manual=True
            )

            if not result.get("success"):
                reason = result.get("reason")
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到足够的群聊记录")
                else:
                    yield event.plain_result("❌ 分析失败，原因未知")
                return

            yield event.plain_result(
                f"📊 已获取{result['messages_count']}条消息，正在生成渲染报告..."
            )

            analysis_result = result["analysis_result"]
            adapter = result["adapter"]
            output_format = self.config_manager.get_output_format()

            # 定义头像获取回调 (Infrastructure delegate)
            async def avatar_getter(user_id: str) -> str | None:
                return await adapter.get_user_avatar_url(user_id)

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
                    if not await adapter.send_image(group_id, image_url):
                        yield event.image_result(image_url)
                elif html_content:
                    yield event.plain_result("⚠️ 图片生成暂不可用，已尝试加入队列。")
                    await self.retry_manager.add_task(
                        html_content, analysis_result, group_id, platform_id
                    )
                else:
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    yield event.plain_result(
                        f"⚠️ 图片生成失败，回退文本：\n\n{text_report}"
                    )

            elif output_format == "pdf":
                pdf_path = await self.report_generator.generate_pdf_report(
                    analysis_result, group_id, avatar_getter=avatar_getter
                )
                if pdf_path:
                    if not await adapter.send_file(group_id, pdf_path):
                        from pathlib import Path

                        yield event.chain_result(
                            [File(name=Path(pdf_path).name, file=pdf_path)]
                        )
                else:
                    yield event.plain_result("⚠️ PDF 生成失败。")

            else:
                text_report = self.report_generator.generate_text_report(
                    analysis_result
                )
                if not await adapter.send_text(group_id, text_report):
                    yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 分析核心执行失败: {str(e)}")

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

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从消息事件中安全获取群组 ID"""
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str:
        """从消息事件中获取平台唯一 ID"""
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
