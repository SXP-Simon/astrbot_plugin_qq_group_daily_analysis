"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等
"""

import json
import asyncio
import base64
import aiohttp
import subprocess
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.message.components import File
from astrbot.core.star.filter.permission import PermissionType

# PDF 生成相关导入
PYPPETEER_AVAILABLE = False
PYPPETEER_VERSION = None

# 尝试导入 pyppeteer
try:
    import pyppeteer
    from pyppeteer import launch
    PYPPETEER_AVAILABLE = True

    # 检查版本
    try:
        PYPPETEER_VERSION = pyppeteer.__version__
        logger.info(f"使用 pyppeteer {PYPPETEER_VERSION} 作为 PDF 引擎")
    except AttributeError:
        PYPPETEER_VERSION = "unknown"
        logger.info("使用 pyppeteer (版本未知) 作为 PDF 引擎")

except ImportError:
    logger.warning("pyppeteer 未安装，PDF 功能将不可用。请使用 /安装PDF 命令安装 pyppeteer==1.0.2")


@dataclass
class SummaryTopic:
    """话题总结数据结构"""
    topic: str
    contributors: List[str]
    detail: str


@dataclass
class UserTitle:
    """用户称号数据结构"""
    name: str
    qq: int
    title: str
    mbti: str
    reason: str


@dataclass 
class GoldenQuote:
    """群聊金句数据结构"""
    content: str
    sender: str
    reason: str

@dataclass
class GroupStatistics:
    """群聊统计数据结构"""
    message_count: int
    total_characters: int
    participant_count: int
    most_active_period: str
    golden_quotes: List[GoldenQuote]
    emoji_count: int


@register(
    "astrbot_qq_group_daily_analysis",
    "SXP-Simon",
    "QQ群日常分析插件 - 生成精美的群聊日常分析报告",
    "1.1.0",
    "https://github.com/SXP-Simon/astrbot-qq-group-daily-analysis"
)
class QQGroupDailyAnalysis(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 直接从AstrBot配置系统读取配置
        self.enabled_groups = config.get("enabled_groups", [])
        self.max_messages = config.get("max_messages", 1000)
        self.analysis_days = config.get("analysis_days", 1)
        self.auto_analysis_time = config.get("auto_analysis_time", "09:00")
        self.enable_auto_analysis = config.get("enable_auto_analysis", False)
        self.output_format = config.get("output_format", "image")

        self.min_messages_threshold = config.get("min_messages_threshold", 50)
        self.topic_analysis_enabled = config.get("topic_analysis_enabled", True)
        self.user_title_analysis_enabled = config.get("user_title_analysis_enabled", True)
        self.max_topics = config.get("max_topics", 5)
        self.max_user_titles = config.get("max_user_titles", 8)
        self.max_query_rounds = config.get("max_query_rounds", 35)

        # PDF 相关配置
        self.pdf_output_dir = config.get("pdf_output_dir", "data/plugins/astrbot-qq-group-daily-analysis/reports")
        self.pdf_filename_format = config.get("pdf_filename_format", "群聊分析报告_{group_id}_{date}.pdf")

        # 启动定时任务
        self.scheduler_task = None
        self.bot_instance = None  # 保存bot实例用于自动分析
        self.bot_qq_id = None  # 保存机器人QQ号，用于过滤机器人消息

        # 延迟启动定时任务，给系统时间初始化
        if self.enable_auto_analysis:
            asyncio.create_task(self._delayed_start_scheduler())
        
        logger.info("QQ群日常分析插件已初始化")

    @filter.command("群分析")
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(self, event: AiocqhttpMessageEvent, days: Optional[int] = None):
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

        # 保存bot实例用于自动分析
        self.bot_instance = event.bot
        
        # 获取机器人QQ号
        await self._get_bot_qq_id()
            
        # 检查群组权限
        if self.enabled_groups and group_id not in self.enabled_groups:
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return


            
        # 设置分析天数
        analysis_days = days if days and 1 <= days <= 7 else self.analysis_days
        
        yield event.plain_result(f"🔍 开始分析群聊近{analysis_days}天的活动，请稍候...")

        # 调试：输出当前配置
        logger.info(f"当前输出格式配置: {self.output_format}")

        try:
            # 获取群聊消息
            messages = await self._fetch_group_messages(event, analysis_days)
            if not messages:
                yield event.plain_result("❌ 未找到足够的群聊记录，请确保群内有足够的消息历史")
                return

            # 检查消息数量是否足够分析
            if len(messages) < self.min_messages_threshold:
                yield event.plain_result(f"❌ 消息数量不足（{len(messages)}条），至少需要{self.min_messages_threshold}条消息才能进行有效分析")
                return

            yield event.plain_result(f"📊 已获取{len(messages)}条消息，正在进行智能分析...")

            # 进行分析
            analysis_result = await self._analyze_messages(messages, group_id)

            # 检查分析结果
            if not analysis_result or not analysis_result.get("statistics"):
                yield event.plain_result("❌ 分析过程中出现错误，请稍后重试")
                return

            # 生成报告
            if self.output_format == "image":
                image_url = await self._generate_image_report(analysis_result, group_id)
                if image_url:
                    yield event.image_result(image_url)
                else:
                    # 如果图片生成失败，回退到文本报告
                    logger.warning("图片报告生成失败，回退到文本报告")
                    text_report = await self._generate_text_report(analysis_result)
                    yield event.plain_result(f"⚠️ 图片报告生成失败，以下是文本版本：\n\n{text_report}")
            elif self.output_format == "pdf":
                if not PYPPETEER_AVAILABLE:
                    yield event.plain_result("❌ PDF 功能不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2")
                    return

                # yield event.plain_result("📄 正在生成 PDF 报告，请稍候...")
                # yield event.plain_result("💡 首次使用可能需要下载 Chromium 浏览器，请耐心等待...")

                pdf_path = await self._generate_pdf_report(analysis_result, group_id)
                if pdf_path:
                    # 发送 PDF 文件
                    pdf_file = File(name=Path(pdf_path).name, file=pdf_path)
                    result = event.make_result()
                    result.chain.append(pdf_file)
                    yield result
                    # yield event.plain_result(f"✅ PDF 报告已生成并发送")
                else:
                    # 如果 PDF 生成失败，提供详细的错误信息和解决方案
                    yield event.plain_result("❌ PDF 报告生成失败")
                    yield event.plain_result("🔧 可能的解决方案：")
                    yield event.plain_result("1. 使用 /安装PDF 命令重新安装依赖")
                    yield event.plain_result("2. 检查网络连接是否正常")
                    yield event.plain_result("3. 暂时使用图片格式：/设置格式 image")

                    # 回退到文本报告
                    logger.warning("PDF 报告生成失败，回退到文本报告")
                    text_report = await self._generate_text_report(analysis_result)
                    yield event.plain_result(f"\n📝 以下是文本版本的分析报告：\n\n{text_report}")
            else:
                text_report = await self._generate_text_report(analysis_result)
                yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员")

    @filter.command("设置格式")
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: AiocqhttpMessageEvent, format_type: str = ""):
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

        # 检查管理员权限
        if not await self._is_admin(event):
            yield event.plain_result("❌ 仅群管理员可以修改设置")
            return

        if not format_type:
            yield event.plain_result(f"""📊 当前输出格式: {self.output_format}

可用格式:
• image - 图片格式 (默认)
• text - 文本格式
• pdf - PDF 格式 {'✅' if PYPPETEER_AVAILABLE else '❌ (需安装 pyppeteer)'}

用法: /设置格式 [格式名称]""")
            return

        format_type = format_type.lower()
        if format_type not in ["image", "text", "pdf"]:
            yield event.plain_result("❌ 无效的格式类型，支持: image, text, pdf")
            return

        if format_type == "pdf" and not PYPPETEER_AVAILABLE:
            yield event.plain_result("❌ PDF 格式不可用，请使用 /安装PDF 命令安装 pyppeteer==1.0.2")
            return

        self.output_format = format_type
        self.config["output_format"] = format_type
        self.config.save_config()
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

    @filter.command("安装PDF")
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: AiocqhttpMessageEvent):
        """
        安装 PDF 功能依赖
        用法: /安装PDF
        """
        global PYPPETEER_AVAILABLE

        if not isinstance(event, AiocqhttpMessageEvent):
            yield event.plain_result("❌ 此功能仅支持QQ群聊")
            return

        # 检查管理员权限
        if not await self._is_admin(event):
            yield event.plain_result("❌ 仅群管理员可以安装依赖")
            return

        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            # 检查是否已安装
            if PYPPETEER_AVAILABLE:
                yield event.plain_result("✅ pyppeteer 已安装，正在检查 Chromium...")

                # 检查 Chromium
                try:
                    import pyppeteer
                    # 尝试获取 Chromium 路径
                    try:
                        chromium_path = pyppeteer.executablePath()
                        if Path(chromium_path).exists():
                            yield event.plain_result("✅ PDF 功能已完全可用！")
                            return
                    except Exception:
                        # executablePath() 可能失败，说明 Chromium 未安装
                        pass

                    yield event.plain_result("🔄 Chromium 未安装，正在下载...")
                    success = await self._install_chromium()
                    if success:
                        yield event.plain_result("✅ PDF 功能安装完成！")
                    else:
                        yield event.plain_result("❌ Chromium 安装失败，请检查网络连接。\n💡 可尝试手动安装：在 Python 中运行 'import pyppeteer; await pyppeteer.launch()'")
                    return
                except Exception as e:
                    yield event.plain_result(f"⚠️ 检查 Chromium 时出错: {e}")

            # 尝试安装更新版本的 pyppeteer
            yield event.plain_result("📦 正在安装/更新 pyppeteer 库...")

            # 强制安装稳定版本的 pyppeteer (1.0.2)
            yield event.plain_result("🔄 强制安装 pyppeteer 稳定版本 (1.0.2)...")
            yield event.plain_result("� 使用 1.0.2 版本可避免 Chromium 下载问题")
            success = await self._install_package("pyppeteer==1.0.2")

            if not success:
                yield event.plain_result("❌ pyppeteer 安装失败")
                yield event.plain_result("🔧 请尝试手动安装稳定版本：")
                yield event.plain_result("   pip install pyppeteer==1.0.2")
                yield event.plain_result("💡 如果仍然失败，请检查网络连接或使用代理")
                return

            yield event.plain_result("✅ pyppeteer 安装成功！")

            # 重新检查可用性
            try:
                # 重新导入以获取最新版本
                import importlib
                if 'pyppeteer' in sys.modules:
                    importlib.reload(sys.modules['pyppeteer'])

                from pyppeteer import launch
                PYPPETEER_AVAILABLE = True

                yield event.plain_result("🎉 PDF 功能安装完成！")
                yield event.plain_result("💡 现在可以使用 /设置格式 pdf 启用 PDF 报告")
                yield event.plain_result("✨ 使用稳定版本 pyppeteer 1.0.2，兼容性更好")
                yield event.plain_result("� 注意：首次生成 PDF 时会自动下载 Chromium")

            except ImportError:
                yield event.plain_result("⚠️ pyppeteer 安装可能未完成，请重启插件后重试")

        except Exception as e:
            logger.error(f"安装 PDF 依赖失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 安装过程中出现错误: {str(e)}")

    @filter.command("分析设置")
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(self, event: AiocqhttpMessageEvent, action: str = "status"):
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
            
        # 检查管理员权限
        if not await self._is_admin(event):
            yield event.plain_result("❌ 仅群管理员可以修改设置")
            return
            
        if action == "enable":
            if group_id not in self.enabled_groups:
                self.enabled_groups.append(group_id)
                self.config["enabled_groups"] = self.enabled_groups
                self.config.save_config()
                yield event.plain_result("✅ 已为当前群启用日常分析功能")

                # 重新加载配置并启动定时任务
                await self._reload_config_and_restart_scheduler()
            else:
                yield event.plain_result("ℹ️ 当前群已启用日常分析功能")

        elif action == "disable":
            if group_id in self.enabled_groups:
                self.enabled_groups.remove(group_id)
                self.config["enabled_groups"] = self.enabled_groups
                self.config.save_config()
                yield event.plain_result("✅ 已为当前群禁用日常分析功能")
            else:
                yield event.plain_result("ℹ️ 当前群未启用日常分析功能")

        elif action == "reload":
            # 重新加载配置
            await self._reload_config_and_restart_scheduler()
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")

        elif action == "test":
            # 测试自动分析功能
            if group_id not in self.enabled_groups:
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            # 保存bot实例
            self.bot_instance = event.bot

            # 执行自动分析
            try:
                await self._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 自动分析测试完成，请查看群消息")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")

        else:  # status
            status = "已启用" if group_id in self.enabled_groups else "未启用"
            auto_status = "已启用" if self.enable_auto_analysis else "未启用"
            scheduler_status = "运行中" if hasattr(self, 'scheduler_task') and self.scheduler_task and not self.scheduler_task.done() else "未运行"

            if PYPPETEER_AVAILABLE:
                pdf_status = f"可用 (pyppeteer {PYPPETEER_VERSION})"
            else:
                pdf_status = "不可用 (使用 /安装PDF 命令安装)"
            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status}
• 自动分析: {auto_status} ({self.auto_analysis_time})
• 定时任务: {scheduler_status}
• 输出格式: {self.output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {self.min_messages_threshold}
• 最大查询轮数: {self.max_query_rounds}

💡 可用命令: enable, disable, status, reload, test
💡 支持的输出格式: image, text, pdf
💡 其他命令: /设置格式, /安装PDF""")

    async def _get_bot_qq_id(self):
        """获取机器人QQ号"""
        try:
            if self.bot_instance and not self.bot_qq_id:
                login_info = await self.bot_instance.api.call_action("get_login_info")
                self.bot_qq_id = str(login_info.get("user_id", ""))
                logger.info(f"获取到机器人QQ号: {self.bot_qq_id}")
        except Exception as e:
            logger.error(f"获取机器人QQ号失败: {e}")

    async def _is_admin(self, event: AiocqhttpMessageEvent) -> bool:
        """检查是否为管理员 - 已简化为允许所有用户"""
        # 允许所有用户使用设置功能
        return True

    async def _install_package(self, package_name: str) -> bool:
        """安装 Python 包"""
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", package_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"成功安装包: {package_name}")
                return True
            else:
                logger.error(f"安装包 {package_name} 失败: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"安装包 {package_name} 时出错: {e}")
            return False

    async def _install_chromium(self) -> bool:
        """安装 Chromium 浏览器"""
        try:
            # 尝试直接启动浏览器，这会触发自动下载
            logger.info("尝试通过启动浏览器来触发 Chromium 下载")

            import pyppeteer
            browser = await pyppeteer.launch(headless=True, args=['--no-sandbox'])
            await browser.close()

            logger.info("成功安装并测试 Chromium")
            return True

        except Exception as e:
            logger.error(f"通过启动浏览器安装 Chromium 失败: {e}")

            # 备用方法：尝试命令行安装
            try:
                logger.info("尝试命令行安装方法")
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-c",
                    "import pyppeteer; import asyncio; asyncio.run(pyppeteer.launch())",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.info("成功通过命令行安装 Chromium")
                    return True
                else:
                    logger.error(f"命令行安装失败: {stderr.decode()}")
                    return False

            except Exception as e2:
                logger.error(f"命令行安装 Chromium 时出错: {e2}")
                return False

    async def _fetch_group_messages_unified(self, client, group_id: str, days: int) -> List[Dict]:
        """统一的群聊消息获取方法"""
        try:
            if not client or not group_id:
                logger.error(f"群 {group_id} 无效的客户端或群组ID")
                return []

            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []
            message_seq = 0
            query_rounds = 0
            max_rounds = self.max_query_rounds  # 从配置读取最大查询轮数
            consecutive_failures = 0
            max_failures = 3  # 最大连续失败次数

            logger.info(f"开始获取群 {group_id} 近 {days} 天的消息记录")
            logger.info(f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            while len(messages) < self.max_messages and query_rounds < max_rounds:
                try:
                    payloads = {
                        "group_id": group_id,
                        "message_seq": message_seq,
                        "count": 200,
                        "reverseOrder": True,
                    }

                    result = await client.api.call_action("get_group_msg_history", **payloads)

                    if not result or "messages" not in result:
                        logger.warning(f"群 {group_id} API返回无效结果: {result}")
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures:
                            break
                        continue

                    round_messages = result.get("messages", [])

                    if not round_messages:
                        logger.info(f"群 {group_id} 没有更多消息，结束获取")
                        break

                    # 重置失败计数
                    consecutive_failures = 0

                    # 过滤时间范围内的消息
                    valid_messages_in_round = 0
                    oldest_msg_time = None

                    for msg in round_messages:
                        try:
                            msg_time = datetime.fromtimestamp(msg.get("time", 0))
                            oldest_msg_time = msg_time  # 记录最老的消息时间

                            # 过滤掉机器人自己的消息
                            sender_id = str(msg.get("sender", {}).get("user_id", ""))
                            if self.bot_qq_id and sender_id == self.bot_qq_id:
                                continue

                            if msg_time >= start_time and msg_time <= end_time:
                                messages.append(msg)
                                valid_messages_in_round += 1
                        except Exception as msg_error:
                            logger.warning(f"群 {group_id} 处理单条消息失败: {msg_error}")
                            continue

                    # 如果最老的消息时间已经超出范围，停止获取
                    if oldest_msg_time and oldest_msg_time < start_time:
                        logger.info(f"群 {group_id} 已获取到时间范围外的消息，停止获取。共获取 {len(messages)} 条消息")
                        break

                    if valid_messages_in_round == 0:
                        logger.warning(f"群 {group_id} 本轮未获取到有效消息")
                        break

                    message_seq = round_messages[0]["message_id"]
                    query_rounds += 1

                    # 添加延迟避免请求过快
                    if query_rounds % 5 == 0:
                        await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"群 {group_id} 获取消息失败 (第{query_rounds+1}轮): {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.error(f"群 {group_id} 连续失败 {max_failures} 次，停止获取")
                        break
                    await asyncio.sleep(1)  # 失败后等待1秒再重试

            logger.info(f"群 {group_id} 消息获取完成，共获取 {len(messages)} 条消息，查询轮数: {query_rounds}")
            return messages

        except Exception as e:
            logger.error(f"群 {group_id} 获取群聊消息记录失败: {e}", exc_info=True)
            return []

    async def _fetch_group_messages(self, event: AiocqhttpMessageEvent, days: int) -> List[Dict]:
        """获取群聊消息记录（手动分析）"""
        return await self._fetch_group_messages_unified(event.bot, event.get_group_id(), days)

    async def _analyze_messages(self, messages: List[Dict], group_id: str) -> Dict:
        """分析消息内容"""
        # 基础统计
        stats = self._calculate_statistics(messages)
        
        # 用户活跃度分析
        user_analysis = self._analyze_users(messages)
        
        # 话题分析（根据配置决定是否启用）
        topics = []
        if self.topic_analysis_enabled:
            topics = await self._analyze_topics(messages)

        # 用户称号分析（根据配置决定是否启用）
        user_titles = []
        if self.user_title_analysis_enabled:
            user_titles = await self._analyze_user_titles(messages, user_analysis)
        
        # 群聊金句分析
        golden_quotes = await self._analyze_golden_quotes(messages)
        stats.golden_quotes = golden_quotes
        
        return {
            "group_id": group_id,
            "analysis_time": datetime.now().isoformat(),
            "statistics": stats,
            "user_analysis": user_analysis,
            "topics": topics,
            "user_titles": user_titles,
            "message_count": len(messages)
        }

    def _calculate_statistics(self, messages: List[Dict]) -> GroupStatistics:
        """计算基础统计数据"""
        total_chars = 0
        participants = set()
        hour_counts = defaultdict(int)
        emoji_count = 0
        
        for msg in messages:
            sender_id = str(msg.get("sender", {}).get("user_id", ""))
            participants.add(sender_id)
            
            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
            hour_counts[msg_time.hour] += 1
            
            # 处理消息内容
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "")
                    total_chars += len(text)
                elif content.get("type") == "face":
                    emoji_count += 1
                    
        # 找出最活跃时段
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        most_active_period = f"{most_active_hour:02d}:00-{(most_active_hour+1)%24:02d}:00"
        
        return GroupStatistics(
            message_count=len(messages),
            total_characters=total_chars,
            participant_count=len(participants),
            most_active_period=most_active_period,
            golden_quotes=[],  # 将在后续LLM分析中填充
            emoji_count=emoji_count
        )

    def _analyze_users(self, messages: List[Dict]) -> Dict[str, Dict]:
        """分析用户活跃度"""
        user_stats = defaultdict(lambda: {
            "message_count": 0,
            "char_count": 0,
            "emoji_count": 0,
            "nickname": "",
            "hours": defaultdict(int),
            "reply_count": 0
        })
        
        for msg in messages:
            sender = msg.get("sender", {})
            user_id = str(sender.get("user_id", ""))
            nickname = sender.get("nickname", "") or sender.get("card", "")
            
            user_stats[user_id]["message_count"] += 1
            user_stats[user_id]["nickname"] = nickname
            
            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
            user_stats[user_id]["hours"][msg_time.hour] += 1
            
            # 处理消息内容
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "")
                    user_stats[user_id]["char_count"] += len(text)
                elif content.get("type") == "face":
                    user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "reply":
                    user_stats[user_id]["reply_count"] += 1
                    
        return dict(user_stats)

    def _render_html_template(self, template: str, data: Dict) -> str:
        """简单的 HTML 模板渲染"""
        result = template

        # 调试：记录渲染数据
        logger.info(f"渲染数据键: {list(data.keys())}")

        for key, value in data.items():
            placeholder = f"{{{key}}}"  # 修正：使用单大括号
            # 调试：记录替换过程
            if placeholder in result:
                logger.debug(f"替换 {placeholder} -> {str(value)[:100]}...")
            result = result.replace(placeholder, str(value))

        # 检查是否还有未替换的占位符
        import re
        remaining_placeholders = re.findall(r'\{[^}]+\}', result)
        if remaining_placeholders:
            logger.warning(f"未替换的占位符: {remaining_placeholders[:10]}")

        return result

    async def _get_user_avatar(self, user_id: str) -> Optional[str]:
        """获取用户头像的base64编码"""
        try:
            avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
            async with aiohttp.ClientSession() as client:
                response = await client.get(avatar_url)
                response.raise_for_status()
                avatar_data = await response.read()
                # 转换为base64编码
                avatar_base64 = base64.b64encode(avatar_data).decode('utf-8')
                return f"data:image/jpeg;base64,{avatar_base64}"
        except Exception as e:
            logger.error(f"获取用户头像失败 {user_id}: {e}")
            return None

    async def _analyze_topics(self, messages: List[Dict]) -> List[SummaryTopic]:
        """使用LLM分析话题"""
        try:
            # 提取文本消息
            text_messages = []
            for msg in messages:
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        if text and len(text) > 2 and not text.startswith(("/")):  # 过滤太短的消息和对机器人的命令
                            text_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text
                            })

            if not text_messages:
                return []

            # # 限制消息数量以避免token过多
            # if len(text_messages) > 100:
            #     # 均匀采样
            #     step = len(text_messages) // 100
            #     text_messages = text_messages[::step]

            # 构建LLM提示词
            messages_text = "\n".join([
                f"[{msg['time']}] {msg['sender']}: {msg['content']}"
                for msg in text_messages
            ])

            prompt = f"""
你是一个帮我进行群聊信息总结的助手，生成总结内容时，你需要严格遵守下面的几个准则：
请分析接下来提供的群聊记录，提取出最多{self.max_topics}个主要话题。

对于每个话题，请提供：
1. 话题名称（突出主题内容，尽量简明扼要）
2. 主要参与者（最多5人）
3. 话题详细描述（包含关键信息和结论）

注意：
- 对于比较有价值的点，稍微用一两句话详细讲讲，比如不要生成 “Nolan 和 SOV 讨论了 galgame 中关于性符号的衍生情况” 这种宽泛的内容，而是生成更加具体的讨论内容，让其他人只看这个消息就能知道讨论中有价值的，有营养的信息。
- 对于其中的部分信息，你需要特意提到主题施加的主体是谁，是哪个群友做了什么事情，而不要直接生成和群友没有关系的语句。
- 对于每一条总结，尽量讲清楚前因后果，以及话题的结论，是什么，为什么，怎么做，如果用户没有讲到细节，则可以不用这么做。

群聊记录：
{messages_text}

请以JSON格式返回，格式如下：
[
  {{
    "topic": "话题名称",
    "contributors": ["参与者1", "参与者2"],
    "detail": "详细描述话题内容、讨论要点和结论，并且符合约束的准则。"
  }}
]
"""

            # 调用LLM
            provider = self.context.get_using_provider()
            if not provider:
                logger.warning("未配置LLM提供商，跳过话题分析")
                return []

            response = await provider.text_chat(
                prompt=prompt,
                max_tokens=3000,
                temperature=0.3
            )

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # 尝试解析JSON
            try:
                import re
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    topics_data = json.loads(json_match.group())
                    return [SummaryTopic(**topic) for topic in topics_data[:5]]
            except:
                pass

            return []

        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return []

    async def _analyze_user_titles(self, messages: List[Dict], user_analysis: Dict) -> List[UserTitle]:
        """使用LLM分析用户称号"""
        try:
            # 准备用户数据
            user_summaries = []
            for user_id, stats in user_analysis.items():
                if stats["message_count"] < 5:  # 过滤活跃度太低的用户
                    continue

                # 分析用户特征
                night_messages = sum(stats["hours"][h] for h in range(0, 6))
                day_messages = stats["message_count"] - night_messages
                avg_chars = stats["char_count"] / stats["message_count"] if stats["message_count"] > 0 else 0

                user_summaries.append({
                    "name": stats["nickname"],
                    "qq": int(user_id),
                    "message_count": stats["message_count"],
                    "avg_chars": round(avg_chars, 1),
                    "emoji_ratio": round(stats["emoji_count"] / stats["message_count"], 2),
                    "night_ratio": round(night_messages / stats["message_count"], 2),
                    "reply_ratio": round(stats["reply_count"] / stats["message_count"], 2)
                })

            if not user_summaries:
                return []

            # 按消息数量排序，取前N名（根据配置）
            user_summaries.sort(key=lambda x: x["message_count"], reverse=True)
            user_summaries = user_summaries[:self.max_user_titles]

            # 构建LLM提示词
            users_text = "\n".join([
                f"- {user['name']} (QQ:{user['qq']}): "
                f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
                f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
                f"回复比例{user['reply_ratio']}"
                for user in user_summaries
            ])

            prompt = f"""
请为以下群友分配合适的称号和MBTI类型。每个人只能有一个称号，每个称号只能给一个人。

可选称号：
- 龙王: 发言频繁但内容轻松的人
- 技术专家: 经常讨论技术话题的人
- 夜猫子: 经常在深夜发言的人
- 表情包军火库: 经常发表情的人
- 沉默终结者: 经常开启话题的人
- 评论家: 平均发言长度很长的人
- 阳角: 在群里很有影响力的人
- 互动达人: 经常回复别人的人
- ... (你可以自行进行拓展添加)

用户数据：
{users_text}

请以JSON格式返回，格式如下：
[
  {{
    "name": "用户名",
    "qq": 123456789,
    "title": "称号",
    "mbti": "MBTI类型",
    "reason": "获得此称号的原因"
  }}
]
"""

            # 调用LLM
            provider = self.context.get_using_provider()
            if not provider:
                logger.warning("未配置LLM提供商，跳过用户称号分析")
                return []

            response = await provider.text_chat(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.5
            )

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # 尝试解析JSON
            try:
                import re
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    titles_data = json.loads(json_match.group())
                    return [UserTitle(**title) for title in titles_data]
            except:
                pass

            return []

        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return []

    async def _analyze_golden_quotes(self, messages: List[Dict]) -> List[GoldenQuote]:
        """使用LLM分析群聊金句"""
        try:
            # 提取有趣的文本消息
            interesting_messages = []
            for msg in messages:
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        # 过滤长度适中、可能有趣的消息
                        if 5 <= len(text) <= 100 and not text.startswith(("http", "www", "/")):
                            interesting_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text
                            })

            if not interesting_messages:
                return []

            # # 限制消息数量以避免token过多
            # if len(interesting_messages) > 50:
            #     # 均匀采样
            #     step = len(interesting_messages) // 50
            #     interesting_messages = interesting_messages[::step]

            # 构建LLM提示词
            messages_text = "\n".join([
                f"[{msg['time']}] {msg['sender']}: {msg['content']}"
                for msg in interesting_messages
            ])

            # 计算金句数量，默认5句，但可以根据配置调整
            max_quotes = min(8, max(3, self.max_topics))  # 根据话题数量调整金句数量，3-8句之间

            prompt = f"""
请从以下群聊记录中挑选出{max_quotes}句最具冲击力、最令人惊叹的"金句"。这些金句需满足：
- 核心标准：**逆天的神人发言**，即具备颠覆常识的脑洞、逻辑跳脱的表达或强烈反差感的原创内容
- 典型特征：包含某些争议话题元素、夸张类比、反常规结论、一本正经的"胡说八道"或突破语境的清奇思路，并且具备一定的冲击力，让人印象深刻。

对于每个金句，请提供：
1. 原文内容（完整保留发言细节）
2. 发言人昵称
3. 选择理由（具体说明其"逆天"之处，如逻辑颠覆点/脑洞角度/反差感/争议话题元素）

此外，我将对你进行严格约束：
- 优先筛选 **逆天指数最高** 的内容：发情、性压抑话题 > 争议话题 > 元素级 > 颠覆认知级 > 逻辑跳脱级 > 趣味调侃级，剔除单纯玩梗或网络热词堆砌的普通发言
- 重点标记包含极端类比、反常识论证或无厘头结论的内容，并且包含一定的争议话题元素。

群聊记录：
{messages_text}

请以JSON格式返回，格式如下：
[
  {{
    "content": "金句原文",
    "sender": "发言人昵称", 
    "reason": "选择这句话的理由（需明确说明逆天特质）"
  }}
]
"""

            # 调用LLM
            provider = self.context.get_using_provider()
            if not provider:
                logger.warning("未配置LLM提供商，跳过金句分析")
                return []

            response = await provider.text_chat(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7
            )

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # 尝试解析JSON
            try:
                import re
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    quotes_data = json.loads(json_match.group())
                    return [GoldenQuote(**quote) for quote in quotes_data[:5]]
            except:
                pass

            return []

        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return []

    async def _html_to_pdf(self, html_content: str, output_path: str) -> bool:
        """将 HTML 内容转换为 PDF 文件"""
        try:
            # 尝试启动浏览器，如果 Chromium 不存在会自动下载
            logger.info("启动浏览器进行 PDF 转换")

            # 配置浏览器启动参数，避免 Chromium 下载问题
            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-default-apps'
                ]
            }

            # 如果是 Windows 系统，尝试使用系统 Chrome
            if sys.platform.startswith('win'):
                # 常见的 Chrome 安装路径
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.environ.get('USERNAME', '')),
                ]

                for chrome_path in chrome_paths:
                    if Path(chrome_path).exists():
                        launch_options['executablePath'] = chrome_path
                        logger.info(f"使用系统 Chrome: {chrome_path}")
                        break

            browser = await launch(**launch_options)
            page = await browser.newPage()

            # 设置页面内容 (pyppeteer 1.0.2 版本的 API)
            await page.setContent(html_content)
            # 等待页面加载完成
            try:
                await page.waitForSelector('body', {'timeout': 10000})
            except Exception:
                # 如果等待失败，继续执行（可能页面已经加载完成）
                pass

            # 导出 PDF
            await page.pdf({
                'path': output_path,
                'format': 'A4',
                'printBackground': True,
                'margin': {
                    'top': '10mm',
                    'right': '10mm',
                    'bottom': '10mm',
                    'left': '10mm'
                },
                'scale': 0.8
            })

            await browser.close()
            logger.info(f"PDF 生成成功: {output_path}")
            return True

        except Exception as e:
            error_msg = str(e)
            if "Chromium downloadable not found" in error_msg:
                logger.error("Chromium 下载失败，建议安装 pyppeteer2 或使用系统 Chrome")
            elif "No usable sandbox" in error_msg:
                logger.error("沙盒权限问题，已尝试禁用沙盒")
            else:
                logger.error(f"HTML 转 PDF 失败: {e}")
            return False

    async def _generate_pdf_report(self, analysis_result: Dict, group_id: str) -> Optional[str]:
        """生成 PDF 格式的分析报告"""
        try:
            # 确保输出目录存在
            output_dir = Path(self.pdf_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            current_date = datetime.now().strftime('%Y%m%d')
            filename = self.pdf_filename_format.format(
                group_id=group_id,
                date=current_date
            )
            pdf_path = output_dir / filename

            # 准备渲染数据
            render_data = await self._prepare_render_data(analysis_result)
            logger.info(f"PDF 渲染数据准备完成，包含 {len(render_data)} 个字段")

            # 生成 HTML 内容
            html_content = self._render_html_template(self._get_pdf_html_template(), render_data)
            logger.info(f"HTML 内容生成完成，长度: {len(html_content)} 字符")

            # 转换为 PDF
            success = await self._html_to_pdf(html_content, str(pdf_path))

            if success:
                return str(pdf_path.absolute())
            else:
                return None

        except Exception as e:
            logger.error(f"生成 PDF 报告失败: {e}")
            return None

    async def _generate_image_report(self, analysis_result: Dict, group_id: str) -> Optional[str]:
        """生成图片格式的分析报告"""
        try:
            # 准备渲染数据
            render_payload = await self._prepare_render_data(analysis_result)

            # 使用AstrBot内置的HTML渲染服务
            image_url = await self.html_render(self._get_html_template(), render_payload)
            return image_url

        except Exception as e:
            logger.error(f"生成图片报告失败: {e}")
            return None



    async def _prepare_render_data(self, analysis_result: Dict) -> Dict:
        """准备渲染数据"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        # 构建话题HTML
        topics_html = ""
        for i, topic in enumerate(topics[:self.max_topics], 1):
            contributors_str = "、".join(topic.contributors)
            topics_html += f"""
            <div class="topic-item">
                <div class="topic-header">
                    <span class="topic-number">{i}</span>
                    <span class="topic-title">{topic.topic}</span>
                </div>
                <div class="topic-contributors">参与者: {contributors_str}</div>
                <div class="topic-detail">{topic.detail}</div>
            </div>
            """

        # 构建用户称号HTML（包含头像）
        titles_html = ""
        for title in user_titles[:self.max_user_titles]:
            # 获取用户头像
            avatar_data = await self._get_user_avatar(str(title.qq))
            avatar_html = f'<img src="{avatar_data}" class="user-avatar" alt="头像">' if avatar_data else '<div class="user-avatar-placeholder">👤</div>'

            titles_html += f"""
            <div class="user-title">
                <div class="user-info">
                    {avatar_html}
                    <div class="user-details">
                        <div class="user-name">{title.name}</div>
                        <div class="user-badges">
                            <div class="user-title-badge">{title.title}</div>
                            <div class="user-mbti">{title.mbti}</div>
                        </div>
                    </div>
                </div>
                <div class="user-reason">{title.reason}</div>
            </div>
            """

        # 构建金句HTML
        quotes_html = ""
        for quote in stats.golden_quotes[:5]:
            quotes_html += f"""
            <div class="quote-item">
                <div class="quote-content">"{quote.content}"</div>
                <div class="quote-author">—— {quote.sender}</div>
                <div class="quote-reason">{quote.reason}</div>
            </div>
            """

        # 返回扁平化的渲染数据
        return {
            "current_date": datetime.now().strftime('%Y年%m月%d日'),
            "current_datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "message_count": stats.message_count,
            "participant_count": stats.participant_count,
            "total_characters": stats.total_characters,
            "emoji_count": stats.emoji_count,
            "most_active_period": stats.most_active_period,
            "topics_html": topics_html,
            "titles_html": titles_html,
            "quotes_html": quotes_html
        }

    def _get_html_template(self) -> str:
        """获取HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日常分析报告</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Noto Sans SC', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #ffffff;
            min-height: 100vh;
            padding: 40px 20px;
            line-height: 1.6;
            color: #1a1a1a;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 48px 40px;
            text-align: center;
            border-radius: 24px 24px 0 0;
        }



        .header h1 {
            font-size: 2.5em;
            font-weight: 300;
            margin-bottom: 12px;
            letter-spacing: -1px;
        }

        .header .date {
            font-size: 1em;
            opacity: 0.8;
            font-weight: 300;
            letter-spacing: 0.5px;
        }

        .content {
            padding: 48px 40px;
        }

        .section {
            margin-bottom: 56px;
        }

        .section:last-child {
            margin-bottom: 0;
        }

        .section-title {
            font-size: 1.4em;
            font-weight: 600;
            margin-bottom: 32px;
            color: #4a5568;
            letter-spacing: -0.3px;
            display: flex;
            align-items: center;
            gap: 8px;
        }



        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 48px;
        }

        .stat-card {
            background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
            padding: 32px 24px;
            text-align: center;
            border-radius: 20px;
            border: 1px solid #e2e8f0;
            transition: all 0.3s ease;
        }

        .stat-card:hover {
            background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
            transform: translateY(-4px);
            box-shadow: 0 12px 32px rgba(102, 126, 234, 0.15);
        }

        .stat-number {
            font-size: 2.5em;
            font-weight: 300;
            color: #4299e1;
            margin-bottom: 8px;
            display: block;
            letter-spacing: -1px;
        }

        .stat-label {
            font-size: 0.8em;
            color: #666666;
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .active-period {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 32px;
            text-align: center;
            margin: 48px 0;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(66, 153, 225, 0.3);
        }

        .active-period .time {
            font-size: 2.5em;
            font-weight: 200;
            margin-bottom: 8px;
            letter-spacing: -1px;
        }

        .active-period .label {
            font-size: 0.8em;
            opacity: 0.8;
            font-weight: 300;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .topic-item {
            background: #ffffff;
            padding: 32px;
            margin-bottom: 24px;
            border-radius: 20px;
            border: 1px solid #e5e5e5;
            transition: all 0.3s ease;
        }

        .topic-item:hover {
            background: #f8f9fa;
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }

        .topic-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }

        .topic-number {
            background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
            color: #ffffff;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 500;
            margin-right: 16px;
            font-size: 0.9em;
            box-shadow: 0 4px 12px rgba(49, 130, 206, 0.3);
        }

        .topic-title {
            font-weight: 600;
            color: #2d3748;
            font-size: 1.1em;
            letter-spacing: -0.3px;
        }

        .topic-contributors {
            color: #666666;
            font-size: 0.8em;
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .topic-detail {
            color: #333333;
            line-height: 1.7;
            font-size: 0.95em;
            font-weight: 300;
        }

        .user-title {
            background: #ffffff;
            padding: 32px;
            margin-bottom: 24px;
            border-radius: 20px;
            border: 1px solid #e5e5e5;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            transition: all 0.3s ease;
        }

        .user-title:hover {
            background: #f8f9fa;
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }

        .user-info {
            display: flex;
            align-items: center;
            flex: 1;
        }

        .user-avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            margin-right: 20px;
            border: 2px solid #f0f0f0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .user-avatar-placeholder {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            font-size: 1.2em;
            color: #999999;
            border: 2px solid #e5e5e5;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .user-details {
            flex: 1;
        }

        .user-name {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 12px;
            font-size: 1em;
            letter-spacing: -0.2px;
        }

        .user-badges {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .user-title-badge {
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
            color: #ffffff;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 8px rgba(66, 153, 225, 0.3);
        }

        .user-mbti {
            background: linear-gradient(135deg, #667eea 0%, #5a67d8 100%);
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 16px;
            font-weight: 500;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        .user-reason {
            color: #666666;
            font-size: 0.85em;
            max-width: 240px;
            text-align: right;
            line-height: 1.5;
            font-weight: 300;
            margin-top: 4px;
        }

        .quote-item {
            background: linear-gradient(135deg, #faf5ff 0%, #f7fafc 100%);
            padding: 24px;
            margin-bottom: 16px;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            position: relative;
            transition: all 0.3s ease;
        }

        .quote-item:hover {
            background: linear-gradient(135deg, #ffffff 0%, #faf5ff 100%);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
        }

        .quote-content {
            font-size: 1.1em;
            color: #2d3748;
            font-weight: 500;
            line-height: 1.6;
            margin-bottom: 12px;
            font-style: italic;
            letter-spacing: 0.2px;
        }

        .quote-author {
            font-size: 0.9em;
            color: #4299e1;
            font-weight: 600;
            margin-bottom: 8px;
            text-align: right;
        }

        .quote-reason {
            font-size: 0.8em;
            color: #666666;
            font-style: normal;
            background: rgba(66, 153, 225, 0.1);
            padding: 8px 12px;
            border-radius: 12px;
            border-left: 3px solid #4299e1;
        }

        .footer {
            background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
            color: #ffffff;
            text-align: center;
            padding: 32px;
            font-size: 0.8em;
            font-weight: 300;
            letter-spacing: 0.5px;
            opacity: 0.9;
        }

        @media (max-width: 768px) {
            body {
                padding: 20px 10px;
            }

            .container {
                margin: 0;
            }

            .header {
                padding: 32px 24px;
            }

            .header h1 {
                font-size: 2em;
            }

            .content {
                padding: 32px 24px;
            }

            .stats-grid {
                grid-template-columns: 1fr 1fr;
                gap: 1px;
            }

            .stat-card {
                padding: 24px 16px;
            }

            .topic-item {
                padding: 24px;
            }

            .user-title {
                flex-direction: column;
                align-items: flex-start;
                gap: 16px;
                padding: 24px;
            }

            .user-info {
                width: 100%;
            }

            .user-mbti {
                margin: 0;
            }

            .user-reason {
                text-align: left;
                max-width: none;
                margin-top: 8px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 群聊日常分析报告</h1>
            <div class="date">{{ current_date }}</div>
        </div>

        <div class="content">
            <div class="section">
                <h2 class="section-title">📈 基础统计</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{{ message_count }}</div>
                        <div class="stat-label">消息总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{ participant_count }}</div>
                        <div class="stat-label">参与人数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{ total_characters }}</div>
                        <div class="stat-label">总字符数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{{ emoji_count }}</div>
                        <div class="stat-label">表情数量</div>
                    </div>
                </div>

                <div class="active-period">
                    <div class="time">{{ most_active_period }}</div>
                    <div class="label">最活跃时段</div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💬 热门话题</h2>
                {{ topics_html | safe }}
            </div>

            <div class="section">
                <h2 class="section-title">🏆 群友称号</h2>
                {{ titles_html | safe }}
            </div>

            <div class="section">
                <h2 class="section-title">💬 群圣经</h2>
                {{ quotes_html | safe }}
            </div>
        </div>

        <div class="footer">
            由 AstrBot QQ群日常分析插件 生成 | {{ current_datetime }}
        </div>
    </div>
</body>
</html>
        """

    async def _create_html_report(self, analysis_result: Dict) -> str:
        """创建HTML报告内容"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        # 构建话题HTML
        topics_html = ""
        for i, topic in enumerate(topics[:self.max_topics], 1):
            contributors_str = "、".join(topic.contributors)
            topics_html += f"""
            <div class="topic-item">
                <div class="topic-header">
                    <span class="topic-number">{i}</span>
                    <span class="topic-title">{topic.topic}</span>
                </div>
                <div class="topic-contributors">参与者: {contributors_str}</div>
                <div class="topic-detail">{topic.detail}</div>
            </div>
            """

        # 构建用户称号HTML
        titles_html = ""
        for title in user_titles[:self.max_user_titles]:
            titles_html += f"""
            <div class="user-title">
                <div class="user-info">
                    <div class="user-details">
                        <div class="user-name">{title.name}</div>
                        <div class="user-badges">
                            <div class="user-title-badge">{title.title}</div>
                            <div class="user-mbti">{title.mbti}</div>
                        </div>
                    </div>
                </div>
                <div class="user-reason">{title.reason}</div>
            </div>
            """

        # 构建金句HTML
        quotes_html = ""
        for i, quote in enumerate(stats.golden_quotes[:5], 1):
            quotes_html += f"""
            <div class="quote-item">
                <div class="quote-content">"{quote.content}"</div>
                <div class="quote-author">—— {quote.sender}</div>
                <div class="quote-reason">{quote.reason}</div>
            </div>
            """

        # HTML模板
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日常分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}

        .header .date {{
            font-size: 16px;
            opacity: 0.9;
        }}

        .content {{
            padding: 30px;
        }}

        .section {{
            margin-bottom: 40px;
        }}

        .section-title {{
            font-size: 20px;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}

        .stat-item {{
            text-align: center;
            padding: 20px;
            background: #f8f9ff;
            border-radius: 10px;
            border: 1px solid #e1e5ff;
        }}

        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .stat-label {{
            font-size: 14px;
            color: #666;
        }}

        .topic-item {{
            background: #f8f9ff;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }}

        .topic-header {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}

        .topic-number {{
            background: #667eea;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            margin-right: 10px;
        }}

        .topic-title {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
        }}

        .topic-contributors {{
            font-size: 12px;
            color: #667eea;
            margin-bottom: 8px;
        }}

        .topic-detail {{
            font-size: 14px;
            color: #666;
            line-height: 1.5;
        }}

        .user-title {{
            background: #f8f9ff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .user-info {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .user-name {{
            font-weight: bold;
            color: #333;
        }}

        .user-title-badge {{
            background: #667eea;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
        }}

        .user-mbti {{
            background: #764ba2;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
        }}

        .user-reason {{
            font-size: 12px;
            color: #666;
            flex: 1;
            margin-left: 15px;
        }}

        .keywords {{
            background: #f8f9ff;
            border-radius: 10px;
            padding: 15px;
            font-size: 14px;
            color: #666;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 群聊日常分析报告</h1>
            <div class="date">{datetime.now().strftime('%Y年%m月%d日')}</div>
        </div>

        <div class="content">
            <div class="section">
                <h2 class="section-title">📊 基础统计</h2>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-number">{stats.message_count}</div>
                        <div class="stat-label">消息总数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.participant_count}</div>
                        <div class="stat-label">参与人数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.total_characters}</div>
                        <div class="stat-label">总字符数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats.emoji_count}</div>
                        <div class="stat-label">表情数量</div>
                    </div>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-number">{stats.most_active_period}</div>
                        <div class="stat-label">最活跃时段</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💬 热门话题</h2>
                {topics_html}
            </div>

            <div class="section">
                <h2 class="section-title">🏆 群友称号</h2>
                {titles_html}
            </div>

            <div class="section">
                <h2 class="section-title">💬 群圣经</h2>
                {quotes_html}
            </div>
        </div>
    </div>
</body>
</html>
        """

        return html_template

    async def _generate_text_report(self, analysis_result: Dict) -> str:
        """生成文本格式的分析报告"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        report = f"""
🎯 群聊日常分析报告
📅 {datetime.now().strftime('%Y年%m月%d日')}

📊 基础统计
• 消息总数: {stats.message_count}
• 参与人数: {stats.participant_count}
• 总字符数: {stats.total_characters}
• 表情数量: {stats.emoji_count}
• 最活跃时段: {stats.most_active_period}

💬 热门话题
"""

        for i, topic in enumerate(topics[:self.max_topics], 1):
            contributors_str = "、".join(topic.contributors)
            report += f"{i}. {topic.topic}\n"
            report += f"   参与者: {contributors_str}\n"
            report += f"   {topic.detail}\n\n"

        report += "🏆 群友称号\n"
        for title in user_titles[:self.max_user_titles]:
            report += f"• {title.name} - {title.title} ({title.mbti})\n"
            report += f"  {title.reason}\n\n"

        report += "💬 群圣经\n"
        for i, quote in enumerate(stats.golden_quotes[:5], 1):
            report += f"{i}. \"{quote.content}\" —— {quote.sender}\n"
            report += f"   {quote.reason}\n\n"

        return report



    async def _reload_config_and_restart_scheduler(self):
        """重新加载配置并重启调度器"""
        try:
            # 重新从配置系统读取配置
            self.enabled_groups = self.config.get("enabled_groups", [])
            self.enable_auto_analysis = self.config.get("enable_auto_analysis", False)
            self.auto_analysis_time = self.config.get("auto_analysis_time", "09:00")
            logger.info(f"重新加载配置: 自动分析={self.enable_auto_analysis}")

            # 停止现有的调度器
            if hasattr(self, 'scheduler_task') and self.scheduler_task and not self.scheduler_task.done():
                self.scheduler_task.cancel()
                logger.info("已停止现有的定时任务")

            # 如果启用了自动分析，启动新的调度器
            if self.enable_auto_analysis:
                self.scheduler_task = asyncio.create_task(self._start_scheduler())
                logger.info("已启动新的定时任务")

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")

    async def _start_scheduler(self):
        """启动定时任务调度器"""
        logger.info(f"启动定时任务调度器，自动分析时间: {self.auto_analysis_time}")

        while True:
            try:
                now = datetime.now()
                target_time = datetime.strptime(self.auto_analysis_time, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )

                # 如果今天的目标时间已过，设置为明天
                if now >= target_time:
                    target_time += timedelta(days=1)

                # 计算等待时间
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"定时分析将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 执行，等待 {wait_seconds:.0f} 秒")

                # 等待到目标时间
                await asyncio.sleep(wait_seconds)

                # 执行自动分析
                if self.enable_auto_analysis:
                    logger.info("开始执行定时分析")
                    await self._run_auto_analysis()
                else:
                    logger.info("自动分析已禁用，跳过执行")
                    break

            except Exception as e:
                logger.error(f"定时任务调度器错误: {e}")
                # 等待5分钟后重试
                await asyncio.sleep(300)

    async def _run_auto_analysis(self):
        """执行自动分析"""
        try:
            logger.info("开始执行自动群聊分析")

            # 为每个启用的群执行分析
            for group_id in self.enabled_groups:
                try:
                    logger.info(f"为群 {group_id} 执行自动分析")

                    # 这里需要模拟一个事件对象来调用分析功能
                    # 由于自动分析没有真实的用户事件，我们直接调用内部方法
                    await self._perform_auto_analysis_for_group(group_id)

                except Exception as e:
                    logger.error(f"群 {group_id} 自动分析失败: {e}")

        except Exception as e:
            logger.error(f"自动分析执行失败: {e}")

    async def _perform_auto_analysis_for_group(self, group_id: str):
        """为指定群执行自动分析"""
        try:
            # 尝试获取bot实例
            if not self.bot_instance:
                self.bot_instance = await self._get_bot_instance()

            if not self.bot_instance:
                logger.warning(f"群 {group_id} 自动分析跳过：未获取到bot实例，请先手动触发一次分析")
                return

            # 确保有机器人QQ号
            if not self.bot_qq_id:
                await self._get_bot_qq_id()

            logger.info(f"开始为群 {group_id} 执行自动分析")

            # 获取群聊消息
            messages = await self._fetch_group_messages_for_auto(group_id)
            if not messages:
                logger.warning(f"群 {group_id} 未获取到足够的消息记录")
                return

            # 检查消息数量
            if len(messages) < self.min_messages_threshold:
                logger.warning(f"群 {group_id} 消息数量不足（{len(messages)}条），跳过分析")
                return

            logger.info(f"群 {group_id} 获取到 {len(messages)} 条消息，开始分析")

            # 进行分析
            analysis_result = await self._analyze_messages(messages, group_id)
            if not analysis_result:
                logger.error(f"群 {group_id} 分析失败")
                return

            # 生成报告
            if self.output_format == "image":
                image_url = await self._generate_image_report(analysis_result, group_id)
                if image_url:
                    # 发送分析报告到群
                    await self._send_auto_analysis_result(group_id, image_url)
                    logger.info(f"群 {group_id} 自动分析完成，已发送图片报告")
                else:
                    logger.error(f"群 {group_id} 图片报告生成失败")
                    # 图片生成失败时回退到文本报告
                    text_report = await self._generate_text_report(analysis_result)
                    await self._send_auto_analysis_text(group_id, text_report)
                    logger.info(f"群 {group_id} 图片报告生成失败，已发送文本报告")
            elif self.output_format == "pdf":
                if not PYPPETEER_AVAILABLE:
                    logger.warning(f"群 {group_id} PDF功能不可用，回退到文本报告")
                    text_report = await self._generate_text_report(analysis_result)
                    await self._send_auto_analysis_text(group_id, text_report)
                    logger.info(f"群 {group_id} PDF功能不可用，已发送文本报告")
                else:
                    pdf_path = await self._generate_pdf_report(analysis_result, group_id)
                    if pdf_path:
                        # 发送PDF文件到群
                        await self._send_auto_analysis_pdf(group_id, pdf_path)
                        logger.info(f"群 {group_id} 自动分析完成，已发送PDF报告")
                    else:
                        logger.error(f"群 {group_id} PDF报告生成失败，回退到文本报告")
                        text_report = await self._generate_text_report(analysis_result)
                        await self._send_auto_analysis_text(group_id, text_report)
                        logger.info(f"群 {group_id} PDF报告生成失败，已发送文本报告")
            else:
                text_report = await self._generate_text_report(analysis_result)
                await self._send_auto_analysis_text(group_id, text_report)
                logger.info(f"群 {group_id} 自动分析完成，已发送文本报告")

        except Exception as e:
            logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)

    async def _fetch_group_messages_for_auto(self, group_id: str) -> List[Dict]:
        """为自动分析获取群聊消息（使用统一方法）"""
        if not self.bot_instance:
            logger.error(f"群 {group_id} 获取消息失败：缺少bot实例")
            return []
        
        return await self._fetch_group_messages_unified(self.bot_instance, group_id, self.analysis_days)

    async def _send_auto_analysis_result(self, group_id: str, image_url: str):
        """发送自动分析的图片结果到群"""
        try:
            if not self.bot_instance:
                return

            # 发送图片消息到群
            await self.bot_instance.api.call_action(
                "send_group_msg",
                group_id=group_id,
                message=[{
                    "type": "text",
                    "data": {"text": "📊 每日群聊分析报告已生成："}
                }, {
                    "type": "image",
                    "data": {"url": image_url}
                }]
            )

        except Exception as e:
            logger.error(f"发送自动分析结果到群 {group_id} 失败: {e}")

    async def _send_auto_analysis_text(self, group_id: str, text_report: str):
        """发送自动分析的文本结果到群"""
        try:
            if not self.bot_instance:
                return

            # 发送文本消息到群
            await self.bot_instance.api.call_action(
                "send_group_msg",
                group_id=group_id,
                message=f"📊 每日群聊分析报告：\n\n{text_report}"
            )

        except Exception as e:
            logger.error(f"发送自动分析文本到群 {group_id} 失败: {e}")

    async def _send_auto_analysis_pdf(self, group_id: str, pdf_path: str):
        """发送自动分析的PDF结果到群"""
        try:
            if not self.bot_instance:
                return

            # 发送PDF文件到群
            await self.bot_instance.api.call_action(
                "send_group_msg",
                group_id=group_id,
                message=[{
                    "type": "text",
                    "data": {"text": "📊 每日群聊分析报告已生成："}
                }, {
                    "type": "file",
                    "data": {"file": pdf_path}
                }]
            )

        except Exception as e:
            logger.error(f"发送自动分析PDF到群 {group_id} 失败: {e}")
            # 如果发送PDF失败，尝试发送提示信息
            try:
                await self.bot_instance.api.call_action(
                    "send_group_msg",
                    group_id=group_id,
                    message=f"📊 每日群聊分析报告已生成，但发送PDF文件失败。PDF文件路径：{pdf_path}"
                )
            except Exception as e2:
                logger.error(f"发送PDF失败提示到群 {group_id} 也失败: {e2}")

    async def _get_bot_instance(self):
        """从Context获取bot实例"""
        try:
            # 如果已经有保存的实例，直接返回
            if self.bot_instance:
                return self.bot_instance
                
            logger.info("尝试获取bot实例...")
            
            # 简化的获取逻辑，尝试常见的几种方式
            if hasattr(self.context, 'get_platforms') and callable(self.context.get_platforms):
                platforms = self.context.get_platforms()
                for platform in platforms:
                    if hasattr(platform, 'bot') and platform.bot:
                        logger.info(f"从平台获取到bot实例")
                        return platform.bot

            # 尝试从context的platforms属性获取
            if hasattr(self.context, 'platforms') and self.context.platforms:
                for platform in self.context.platforms:
                    if hasattr(platform, 'bot') and platform.bot:
                        logger.info(f"从平台列表获取到bot实例")
                        return platform.bot

            logger.info("暂时无法获取bot实例，等待用户手动触发分析")
            return None

        except Exception as e:
            logger.error(f"获取bot实例失败: {e}")
            return None

    async def _delayed_start_scheduler(self):
        """延迟启动调度器，给系统时间初始化"""
        try:
            # 等待10秒让系统完全初始化
            await asyncio.sleep(10)

            # 尝试获取bot实例
            self.bot_instance = await self._get_bot_instance()

            if self.bot_instance:
                logger.info("成功获取bot实例，启动定时任务")
                # 获取机器人QQ号
                await self._get_bot_qq_id()
            else:
                logger.info("暂时未获取到bot实例，定时任务仍会启动。首次手动触发分析后将自动获取bot实例")

            # 启动调度器
            self.scheduler_task = asyncio.create_task(self._start_scheduler())

        except Exception as e:
            logger.error(f"延迟启动调度器失败: {e}")

    def _get_pdf_html_template(self) -> str:
        """获取 PDF 专用的 HTML 模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日常分析报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
            background: #ffffff;
            color: #1a1a1a;
            line-height: 1.6;
            font-size: 14px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 30px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .header .date {
            font-size: 16px;
            opacity: 0.9;
        }

        .section {
            margin-bottom: 40px;
            page-break-inside: avoid;
        }

        .section-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #4a5568;
            border-bottom: 2px solid #4299e1;
            padding-bottom: 8px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: #f8f9ff;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }

        .stat-number {
            font-size: 24px;
            font-weight: 600;
            color: #4299e1;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 12px;
            color: #666666;
            text-transform: uppercase;
        }

        .active-period {
            background: linear-gradient(135deg, #4299e1 0%, #667eea 100%);
            color: #ffffff;
            padding: 25px;
            text-align: center;
            margin: 30px 0;
            border-radius: 8px;
        }

        .active-period .time {
            font-size: 28px;
            font-weight: 300;
            margin-bottom: 5px;
        }

        .active-period .label {
            font-size: 14px;
            opacity: 0.9;
        }

        .topic-item {
            background: #ffffff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            page-break-inside: avoid;
        }

        .topic-header {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }

        .topic-number {
            background: #4299e1;
            color: #ffffff;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 12px;
            font-size: 12px;
        }

        .topic-title {
            font-weight: 600;
            color: #2d3748;
            font-size: 16px;
        }

        .topic-contributors {
            color: #666666;
            font-size: 12px;
            margin-bottom: 10px;
        }

        .topic-detail {
            color: #333333;
            line-height: 1.6;
            font-size: 14px;
        }

        .user-title {
            background: #ffffff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            page-break-inside: avoid;
        }

        .user-info {
            display: flex;
            align-items: center;
            flex: 1;
        }

        .user-details {
            flex: 1;
        }

        .user-name {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 8px;
            font-size: 16px;
        }

        .user-badges {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .user-title-badge {
            background: #4299e1;
            color: #ffffff;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .user-mbti {
            background: #667eea;
            color: #ffffff;
            padding: 4px 8px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 12px;
        }

        .user-reason {
            color: #666666;
            font-size: 12px;
            max-width: 200px;
            text-align: right;
            line-height: 1.4;
        }

        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin-right: 15px;
            border: 2px solid #e2e8f0;
            object-fit: cover;
            flex-shrink: 0;
        }

        .user-avatar-placeholder {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-size: 18px;
            color: #666666;
            flex-shrink: 0;
        }

        .quote-item {
            background: #faf5ff;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            page-break-inside: avoid;
        }

        .quote-content {
            font-size: 16px;
            color: #2d3748;
            font-weight: 500;
            line-height: 1.6;
            margin-bottom: 10px;
            font-style: italic;
        }

        .quote-author {
            font-size: 14px;
            color: #4299e1;
            font-weight: 600;
            margin-bottom: 8px;
            text-align: right;
        }

        .quote-reason {
            font-size: 12px;
            color: #666666;
            background: rgba(66, 153, 225, 0.1);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid #4299e1;
        }

        .footer {
            background: #f8f9ff;
            color: #666666;
            text-align: center;
            padding: 20px;
            font-size: 12px;
            border-radius: 8px;
            margin-top: 40px;
        }

        @media print {
            body {
                font-size: 12px;
            }

            .container {
                padding: 10px;
            }

            .header {
                padding: 20px;
            }

            .section {
                margin-bottom: 30px;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 群聊日常分析报告</h1>
            <div class="date">{current_date}</div>
        </div>

        <div class="section">
            <h2 class="section-title">📈 基础统计</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{message_count}</div>
                    <div class="stat-label">消息总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{participant_count}</div>
                    <div class="stat-label">参与人数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_characters}</div>
                    <div class="stat-label">总字符数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{emoji_count}</div>
                    <div class="stat-label">表情数量</div>
                </div>
            </div>

            <div class="active-period">
                <div class="time">{most_active_period}</div>
                <div class="label">最活跃时段</div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">💬 热门话题</h2>
            {topics_html}
        </div>

        <div class="section">
            <h2 class="section-title">🏆 群友称号</h2>
            {titles_html}
        </div>

        <div class="section">
            <h2 class="section-title">💬 群圣经</h2>
            {quotes_html}
        </div>

        <div class="footer">
            由 AstrBot QQ群日常分析插件 生成 | {current_datetime}
        </div>
    </div>
</body>
</html>
        """
