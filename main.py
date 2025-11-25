"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构
"""

import asyncio

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.message.components import File
from astrbot.core.star.filter.permission import PermissionType

# 导入重构后的模块
from .src.core.config import ConfigManager
from .src.core.bot_manager import BotManager
from .src.reports.generators import ReportGenerator
from .src.scheduler.auto_scheduler import AutoScheduler
from .src.utils.pdf_utils import PDFInstaller
from .src.utils.helpers import MessageAnalyzer


# 全局变量
config_manager = None
bot_manager = None
message_analyzer = None
report_generator = None
auto_scheduler = None


class QQGroupDailyAnalysis(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化模块化组件
        global \
            config_manager, \
            bot_manager, \
            message_analyzer, \
            report_generator, \
            auto_scheduler

        config_manager = ConfigManager(config)
        bot_manager = BotManager(config_manager)
        bot_manager.set_context(context)
        message_analyzer = MessageAnalyzer(context, config_manager, bot_manager)
        report_generator = ReportGenerator(config_manager)
        auto_scheduler = AutoScheduler(
            config_manager,
            message_analyzer.message_handler,
            message_analyzer,
            report_generator,
            bot_manager,
            self.html_render,  # 传入html_render函数
        )

        # 延迟启动自动调度器，给系统时间初始化
        if config_manager.get_enable_auto_analysis():
            asyncio.create_task(self._delayed_start_scheduler())

        logger.info("QQ群日常分析插件已初始化（模块化版本）")

    async def _delayed_start_scheduler(self):
        """延迟启动调度器，给系统时间初始化"""
        try:
            # 等待10秒让系统完全初始化
            await asyncio.sleep(30)

            # 初始化所有bot实例
            discovered = await bot_manager.initialize_from_config()
            if discovered:
                platform_count = len(discovered)
                logger.info(f"Bot管理器初始化成功，发现 {platform_count} 个适配器")
                for platform_id, bot_instance in discovered.items():
                    logger.info(
                        f"  - 平台 {platform_id}: {type(bot_instance).__name__}"
                    )

                # 启动调度器
                await auto_scheduler.start_scheduler()
            else:
                logger.warning("Bot管理器初始化失败，未发现任何适配器")
                status = bot_manager.get_status_info()
                logger.info(f"Bot管理器状态: {status}")

        except Exception as e:
            logger.debug(f"延迟启动调度器失败，可能由于短时间内多次更新插件配置: {e}")

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        try:
            logger.info("开始清理QQ群日常分析插件资源...")

            global \
                auto_scheduler, \
                bot_manager, \
                message_analyzer, \
                report_generator, \
                config_manager

            # 停止自动调度器
            if auto_scheduler:
                logger.info("正在停止自动调度器...")
                await auto_scheduler.stop_scheduler()
                logger.info("自动调度器已停止")

            # 清理bot管理器资源
            # if bot_manager:
            #     logger.info("正在清理bot管理器资源...")
            #     # 如果有其他需要清理的资源，可以在这里添加

            # # 清理消息分析器资源
            # if message_analyzer:
            #     logger.info("正在清理消息分析器资源...")
            #     # 如果有其他需要清理的资源，可以在这里添加

            # # 清理报告生成器资源
            # if report_generator:
            #     logger.info("正在清理报告生成器资源...")
            #     # 如果有其他需要清理的资源，可以在这里添加

            # 重置全局变量
            auto_scheduler = None
            bot_manager = None
            message_analyzer = None
            report_generator = None
            config_manager = None

            logger.info("QQ群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    @filter.command("群分析")
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AiocqhttpMessageEvent, days: int | None = None
    ):
        """
        分析群聊日常活动
        用法: /群分析 [天数]
        """
        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        # 更新bot实例（用于手动命令）
        bot_manager.update_from_event(event)

        # 检查群组权限
        if not config_manager.is_group_allowed(group_id):
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return

        # 设置分析天数
        analysis_days = (
            days if days and 1 <= days <= 7 else config_manager.get_analysis_days()
        )

        yield event.plain_result(f"🔍 开始分析群聊近{analysis_days}天的活动，请稍候...")

        # 调试：输出当前配置
        logger.info(f"当前输出格式配置: {config_manager.get_output_format()}")

        try:
            # 获取该群对应的平台ID和bot实例
            platform_id = auto_scheduler._get_platform_id_for_group(group_id)
            bot_instance = bot_manager.get_bot_instance(platform_id)

            if not bot_instance:
                yield event.plain_result(
                    f"❌ 未找到群 {group_id} 对应的bot实例（平台: {platform_id}）"
                )
                return

            # 获取群聊消息
            messages = await message_analyzer.message_handler.fetch_group_messages(
                bot_instance, group_id, analysis_days, platform_id
            )
            if not messages:
                yield event.plain_result(
                    "❌ 未找到足够的群聊记录，请确保群内有足够的消息历史"
                )
                return

            # 检查消息数量是否足够分析
            min_threshold = config_manager.get_min_messages_threshold()
            if len(messages) < min_threshold:
                yield event.plain_result(
                    f"❌ 消息数量不足（{len(messages)}条），至少需要{min_threshold}条消息才能进行有效分析"
                )
                return

            yield event.plain_result(
                f"📊 已获取{len(messages)}条消息，正在进行智能分析..."
            )

            # 进行分析 - 传递 unified_msg_origin 以获取正确的 LLM 提供商
            analysis_result = await message_analyzer.analyze_messages(
                messages, group_id, event.unified_msg_origin
            )

            # 检查分析结果
            if not analysis_result or not analysis_result.get("statistics"):
                yield event.plain_result("❌ 分析过程中出现错误，请稍后重试")
                return

            # 生成报告
            output_format = config_manager.get_output_format()
            if output_format == "image":
                image_url = await report_generator.generate_image_report(
                    analysis_result, group_id, self.html_render
                )
                if image_url:
                    yield event.image_result(image_url)
                else:
                    # 如果图片生成失败，回退到文本报告
                    logger.warning("图片报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(
                        f"⚠️ 图片报告生成失败，以下是文本版本：\n\n{text_report}"
                    )
            elif output_format == "pdf":
                if not config_manager.pyppeteer_available:
                    yield event.plain_result(
                        "❌ PDF 功能不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
                    )
                    return

                pdf_path = await report_generator.generate_pdf_report(
                    analysis_result, group_id
                )
                if pdf_path:
                    # 发送 PDF 文件
                    from pathlib import Path

                    pdf_file = File(name=Path(pdf_path).name, file=pdf_path)
                    result = event.make_result()
                    result.chain.append(pdf_file)
                    yield result
                else:
                    # 如果 PDF 生成失败，提供详细的错误信息和解决方案
                    # yield event.plain_result("❌ PDF 报告生成失败")
                    # yield event.plain_result("🔧 可能的解决方案：")
                    # yield event.plain_result("1. 使用 /安装PDF 命令重新安装依赖")
                    # yield event.plain_result("2. 检查网络连接是否正常")
                    # yield event.plain_result("3. 暂时使用图片格式：/设置格式 image")

                    # 回退到文本报告
                    logger.warning("PDF 报告生成失败，回退到文本报告")
                    text_report = report_generator.generate_text_report(analysis_result)
                    yield event.plain_result(
                        f"\n📝 以下是文本版本的分析报告：\n\n{text_report}"
                    )
            else:
                text_report = report_generator.generate_text_report(analysis_result)
                yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )

    @filter.command("设置格式")
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(
        self, event: AiocqhttpMessageEvent, format_type: str = ""
    ):
        """
        设置分析报告输出格式
        用法: /设置格式 [image|text|pdf]
        """
        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not format_type:
            current_format = config_manager.get_output_format()
            pdf_status = (
                "✅" if config_manager.pyppeteer_available else "❌ (需安装 pyppeteer)"
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

        if format_type == "pdf" and not config_manager.pyppeteer_available:
            yield event.plain_result(
                "❌ PDF 格式不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
            )
            return

        config_manager.set_output_format(format_type)
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

    @filter.command("设置模板")
    @filter.permission_type(PermissionType.ADMIN)
    async def set_report_template(
        self, event: AiocqhttpMessageEvent, template_name: str = ""
    ):
        """
        设置分析报告模板
        用法: /设置模板 [模板名称]
        """
        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        if not template_name:
            current_template = config_manager.get_report_template()
            # 列出可用的模板
            import os
            template_dir = os.path.join(os.path.dirname(__file__), "src", "reports", "templates")
            available_templates = []
            if os.path.exists(template_dir):
                available_templates = [d for d in os.listdir(template_dir) if os.path.isdir(os.path.join(template_dir, d)) and not d.startswith("__")]
            
            template_list_str = "\n".join([f"• {t}" for t in available_templates])
            yield event.plain_result(f"""🎨 当前报告模板: {current_template}

可用模板:
{template_list_str}

用法: /设置模板 [模板名称]""")
            return

        # 检查模板是否存在
        import os
        template_dir = os.path.join(os.path.dirname(__file__), "src", "reports", "templates", template_name)
        if not os.path.exists(template_dir):
             yield event.plain_result(f"❌ 模板 '{template_name}' 不存在")
             return

        config_manager.set_report_template(template_name)
        yield event.plain_result(f"✅ 报告模板已设置为: {template_name}")

    @filter.command("安装PDF")
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: AiocqhttpMessageEvent):
        """
        安装 PDF 功能依赖
        用法: /安装PDF
        """
        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            # 安装 pyppeteer
            result = await PDFInstaller.install_pyppeteer(config_manager)
            yield event.plain_result(result)

            # 提供系统依赖安装指导
            system_deps_result = await PDFInstaller.install_system_deps()
            yield event.plain_result(system_deps_result)

        except Exception as e:
            logger.error(f"安装 PDF 依赖失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 安装过程中出现错误: {str(e)}")

    @filter.command("分析设置")
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(
        self, event: AiocqhttpMessageEvent, action: str = "status"
    ):
        """
        管理分析设置
        用法: /分析设置 [enable|disable|status|reload|test]
        - enable: 启用当前群的分析功能
        - disable: 禁用当前群的分析功能
        - status: 查看当前状态
        - reload: 重新加载配置并重启定时任务
        - test: 测试自动分析功能
        """
        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if action == "enable":
            mode = config_manager.get_group_list_mode()
            if mode == "whitelist":
                glist = config_manager.get_group_list()
                if group_id not in glist:
                    glist.append(group_id)
                    config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群加入白名单")
                    # 重新启动定时任务
                    await auto_scheduler.restart_scheduler()
                else:
                    yield event.plain_result("ℹ️ 当前群已在白名单中")
            elif mode == "blacklist":
                glist = config_manager.get_group_list()
                if group_id in glist:
                    glist.remove(group_id)
                    config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群从黑名单移除")
                    # 重新启动定时任务
                    await auto_scheduler.restart_scheduler()
                else:
                    yield event.plain_result("ℹ️ 当前群不在黑名单中")
            else:
                yield event.plain_result("ℹ️ 当前为无限制模式，所有群聊默认启用")

        elif action == "disable":
            mode = config_manager.get_group_list_mode()
            if mode == "whitelist":
                glist = config_manager.get_group_list()
                if group_id in glist:
                    glist.remove(group_id)
                    config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群从白名单移除")
                    # 重新启动定时任务
                    await auto_scheduler.restart_scheduler()
                else:
                    yield event.plain_result("ℹ️ 当前群不在白名单中")
            elif mode == "blacklist":
                glist = config_manager.get_group_list()
                if group_id not in glist:
                    glist.append(group_id)
                    config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群加入黑名单")
                    # 重新启动定时任务
                    await auto_scheduler.restart_scheduler()
                else:
                    yield event.plain_result("ℹ️ 当前群已在黑名单中")
            else:
                yield event.plain_result(
                    "ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式"
                )

        elif action == "reload":
            # 重新启动定时任务
            await auto_scheduler.restart_scheduler()
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")

        elif action == "test":
            # 测试自动分析功能
            if not config_manager.is_group_allowed(group_id):
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            # 更新bot实例（用于测试）
            bot_manager.update_from_event(event)

            # 执行自动分析
            try:
                await auto_scheduler._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 自动分析测试完成，请查看群消息")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")

        else:  # status
            is_allowed = config_manager.is_group_allowed(group_id)
            status = "已启用" if is_allowed else "未启用"
            mode = config_manager.get_group_list_mode()

            auto_status = (
                "已启用" if config_manager.get_enable_auto_analysis() else "未启用"
            )
            auto_time = config_manager.get_auto_analysis_time()

            pdf_status = PDFInstaller.get_pdf_status(config_manager)
            output_format = config_manager.get_output_format()
            min_threshold = config_manager.get_min_messages_threshold()

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time})
• 输出格式: {output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test
💡 支持的输出格式: image, text, pdf (图片和PDF包含活跃度可视化)
💡 其他命令: /设置格式, /安装PDF""")
