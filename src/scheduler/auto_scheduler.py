"""
自动调度器模块
负责定时任务和自动分析功能
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from astrbot.api import logger


class AutoScheduler:
    """自动调度器"""

    def __init__(self, config_manager, message_handler, analyzer, report_generator, bot_manager, html_render_func=None):
        self.config_manager = config_manager
        self.message_handler = message_handler
        self.analyzer = analyzer
        self.report_generator = report_generator
        self.bot_manager = bot_manager
        self.html_render_func = html_render_func
        self.scheduler_task = None
        self.last_execution_date = None  # 记录上次执行日期，防止重复执行

    def set_bot_instance(self, bot_instance):
        """设置bot实例（保持向后兼容）"""
        self.bot_manager.set_bot_instance(bot_instance)

    def set_bot_qq_id(self, bot_qq_id: str):
        """设置bot QQ号（保持向后兼容）"""
        self.bot_manager.set_bot_qq_id(bot_qq_id)

    def _get_platform_id(self):
        """获取平台ID"""
        try:
            if hasattr(self.bot_manager, '_context') and self.bot_manager._context:
                context = self.bot_manager._context
                if hasattr(context, 'platform_manager') and hasattr(context.platform_manager, 'platform_insts'):
                    platforms = context.platform_manager.platform_insts
                    for platform in platforms:
                        if hasattr(platform, 'metadata') and hasattr(platform.metadata, 'id'):
                            platform_id = platform.metadata.id
                            return platform_id
            return "aiocqhttp"  # 默认值
        except Exception as e:
            return "aiocqhttp"  # 默认值

    async def start_scheduler(self):
        """启动定时任务调度器"""
        if not self.config_manager.get_enable_auto_analysis():
            logger.info("自动分析功能未启用")
            return

        # 延迟启动，给系统时间初始化
        await asyncio.sleep(10)

        logger.info(f"启动定时任务调度器，自动分析时间: {self.config_manager.get_auto_analysis_time()}")

        self.scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """停止定时任务调度器"""
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            logger.info("已停止定时任务调度器")

    async def restart_scheduler(self):
        """重启定时任务调度器"""
        await self.stop_scheduler()
        if self.config_manager.get_enable_auto_analysis():
            await self.start_scheduler()

    async def _scheduler_loop(self):
        """调度器主循环"""
        while True:
            try:
                now = datetime.now()
                target_time = datetime.strptime(self.config_manager.get_auto_analysis_time(), "%H:%M").replace(
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
                if self.config_manager.get_enable_auto_analysis():
                    # 检查今天是否已经执行过，防止重复执行
                    if self.last_execution_date == target_time.date():
                        logger.info(f"今天 {target_time.date()} 已经执行过自动分析，跳过执行")
                        # 等待到明天再检查
                        await asyncio.sleep(3600)  # 等待1小时后再检查
                        continue

                    logger.info("开始执行定时分析")
                    await self._run_auto_analysis()
                    self.last_execution_date = target_time.date()  # 记录执行日期
                    logger.info(f"定时分析执行完成，记录执行日期: {self.last_execution_date}")
                else:
                    logger.info("自动分析已禁用，跳过执行")
                    break

            except Exception as e:
                logger.error(f"定时任务调度器错误: {e}")
                # 等待5分钟后重试
                await asyncio.sleep(300)

    async def _run_auto_analysis(self):
        """执行自动分析 - 并发处理所有群聊"""
        try:
            logger.info("开始执行自动群聊分析（并发模式）")

            enabled_groups = self.config_manager.get_enabled_groups()
            if not enabled_groups:
                logger.info("没有启用的群聊需要分析")
                return

            logger.info(f"将为 {len(enabled_groups)} 个群聊并发执行分析: {enabled_groups}")
            
            # 创建并发任务 - 为每个群聊创建独立的分析任务
            analysis_tasks = []
            for group_id in enabled_groups:
                task = asyncio.create_task(
                    self._perform_auto_analysis_for_group_with_timeout(group_id),
                    name=f"analysis_group_{group_id}"
                )
                analysis_tasks.append(task)
            
            # 并发执行所有分析任务，使用 return_exceptions=True 确保单个任务失败不影响其他任务
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            # 统计执行结果
            success_count = 0
            error_count = 0
            
            for i, result in enumerate(results):
                group_id = enabled_groups[i]
                if isinstance(result, Exception):
                    logger.error(f"群 {group_id} 分析任务异常: {result}")
                    error_count += 1
                else:
                    success_count += 1
            
            logger.info(f"并发分析完成 - 成功: {success_count}, 失败: {error_count}, 总计: {len(enabled_groups)}")

        except Exception as e:
            logger.error(f"自动分析执行失败: {e}", exc_info=True)

    async def _perform_auto_analysis_for_group_with_timeout(self, group_id: str):
        """为指定群执行自动分析（带超时控制）"""
        try:
            # 为每个群聊设置独立的超时时间（20分钟）- 使用 asyncio.wait_for 兼容所有 Python 版本
            await asyncio.wait_for(self._perform_auto_analysis_for_group(group_id), timeout=1200)
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 分析超时（20分钟），跳过该群分析")
        except Exception as e:
            logger.error(f"群 {group_id} 分析任务执行失败: {e}")
    
    async def _perform_auto_analysis_for_group(self, group_id: str):
        """为指定群执行自动分析（核心逻辑）"""
        # 为每个群聊使用独立的锁，避免全局锁导致串行化
        group_lock_key = f"analysis_{group_id}"
        if not hasattr(self, '_group_locks'):
            self._group_locks = {}
        
        if group_lock_key not in self._group_locks:
            self._group_locks[group_lock_key] = asyncio.Lock()
        
        async with self._group_locks[group_lock_key]:
            try:
                start_time = asyncio.get_event_loop().time()
                
                # 检查bot管理器状态
                if not self.bot_manager.is_ready_for_auto_analysis():
                    status = self.bot_manager.get_status_info()
                    logger.warning(f"群 {group_id} 自动分析跳过：bot管理器未就绪 - {status}")
                    return

                logger.info(f"开始为群 {group_id} 执行自动分析（并发任务）")

                # 获取群聊消息
                analysis_days = self.config_manager.get_analysis_days()
                bot_instance = self.bot_manager.get_bot_instance()

                messages = await self.message_handler.fetch_group_messages(bot_instance, group_id, analysis_days)
                    
                if not messages:
                    logger.warning(f"群 {group_id} 未获取到足够的消息记录")
                    return

                # 检查消息数量
                min_threshold = self.config_manager.get_min_messages_threshold()
                if len(messages) < min_threshold:
                    logger.warning(f"群 {group_id} 消息数量不足（{len(messages)}条），跳过分析")
                    return

                logger.info(f"群 {group_id} 获取到 {len(messages)} 条消息，开始分析")

                # 进行分析 - 构造正确的 unified_msg_origin
                platform_id = self._get_platform_id()
                umo = f"{platform_id}:GroupMessage:{group_id}" if platform_id else None
                analysis_result = await self.analyzer.analyze_messages(messages, group_id, umo)
                if not analysis_result:
                    logger.error(f"群 {group_id} 分析失败")
                    return

                # 生成并发送报告
                await self._send_analysis_report(group_id, analysis_result)
                
                # 记录执行时间
                end_time = asyncio.get_event_loop().time()
                execution_time = end_time - start_time
                logger.info(f"群 {group_id} 分析完成，耗时: {execution_time:.2f}秒")

            except Exception as e:
                logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)
            
            finally:
                # 清理群聊锁资源（可选，防止内存泄漏）
                if hasattr(self, '_group_locks') and len(self._group_locks) > 50:
                    old_locks = list(self._group_locks.keys())[:10]
                    for lock_key in old_locks:
                        if not self._group_locks[lock_key].locked():
                            del self._group_locks[lock_key]

    async def _send_analysis_report(self, group_id: str, analysis_result: dict):
        """发送分析报告到群"""
        try:
            output_format = self.config_manager.get_output_format()

            if output_format == "image":
                if self.html_render_func:
                    # 使用图片格式
                    logger.info(f"群 {group_id} 自动分析使用图片报告格式")
                    try:
                        image_url = await self.report_generator.generate_image_report(analysis_result, group_id, self.html_render_func)
                        if image_url:
                            await self._send_image_message(group_id, image_url)
                            logger.info(f"群 {group_id} 图片报告发送成功")
                        else:
                            # 图片生成失败，回退到文本
                            logger.warning(f"群 {group_id} 图片报告生成失败（返回None），回退到文本报告")
                            text_report = self.report_generator.generate_text_report(analysis_result)
                            await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")
                    except Exception as img_e:
                        logger.error(f"群 {group_id} 图片报告生成异常: {img_e}，回退到文本报告")
                        text_report = self.report_generator.generate_text_report(analysis_result)
                        await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")
                else:
                    # 没有html_render函数，回退到文本报告
                    logger.warning(f"群 {group_id} 缺少html_render函数，回退到文本报告")
                    text_report = self.report_generator.generate_text_report(analysis_result)
                    await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")

            elif output_format == "pdf":
                if not self.config_manager.pyppeteer_available:
                    logger.warning(f"群 {group_id} PDF功能不可用，回退到文本报告")
                    text_report = self.report_generator.generate_text_report(analysis_result)
                    await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")
                else:
                    try:
                        pdf_path = await self.report_generator.generate_pdf_report(analysis_result, group_id)
                        if pdf_path:
                            await self._send_pdf_file(group_id, pdf_path)
                            logger.info(f"群 {group_id} 自动分析完成，已发送PDF报告")
                        else:
                            logger.error(f"群 {group_id} PDF报告生成失败（返回None），回退到文本报告")
                            text_report = self.report_generator.generate_text_report(analysis_result)
                            await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")
                    except Exception as pdf_e:
                        logger.error(f"群 {group_id} PDF报告生成异常: {pdf_e}，回退到文本报告")
                        text_report = self.report_generator.generate_text_report(analysis_result)
                        await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")
            else:
                text_report = self.report_generator.generate_text_report(analysis_result)
                await self._send_text_message(group_id, f"📊 每日群聊分析报告：\n\n{text_report}")

            logger.info(f"群 {group_id} 自动分析完成，已发送报告")

        except Exception as e:
            logger.error(f"发送分析报告到群 {group_id} 失败: {e}")

    async def _send_image_message(self, group_id: str, image_url: str):
        """发送图片消息到群"""
        try:
            bot_instance = self.bot_manager.get_bot_instance()
            if not bot_instance:
                logger.error(f"群 {group_id} 发送图片失败：缺少bot实例")
                return

            # 发送图片消息到群
            await bot_instance.api.call_action(
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
            logger.info(f"群 {group_id} 图片消息发送成功")

        except Exception as e:
            logger.error(f"发送图片消息到群 {group_id} 失败: {e}")

    async def _send_text_message(self, group_id: str, text_content: str):
        """发送文本消息到群"""
        try:
            bot_instance = self.bot_manager.get_bot_instance()
            if not bot_instance:
                logger.error(f"群 {group_id} 发送文本失败：缺少bot实例")
                return

            # 发送文本消息到群
            await bot_instance.api.call_action(
                "send_group_msg",
                group_id=group_id,
                message=text_content
            )
            logger.info(f"群 {group_id} 文本消息发送成功")

        except Exception as e:
            logger.error(f"发送文本消息到群 {group_id} 失败: {e}")

    async def _send_pdf_file(self, group_id: str, pdf_path: str):
        """发送PDF文件到群"""
        try:
            bot_instance = self.bot_manager.get_bot_instance()
            if not bot_instance:
                logger.error(f"群 {group_id} 发送PDF失败：缺少bot实例")
                return

            # 发送PDF文件到群
            await bot_instance.api.call_action(
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
            logger.info(f"群 {group_id} PDF文件发送成功")

        except Exception as e:
            logger.error(f"发送PDF文件到群 {group_id} 失败: {e}")
            # 发送失败提示
            try:
                await bot_instance.api.call_action(
                    "send_group_msg",
                    group_id=group_id,
                    message=f"📊 每日群聊分析报告已生成，但发送PDF文件失败。PDF文件路径：{pdf_path}"
                )
            except Exception as e2:
                logger.error(f"发送PDF失败提示到群 {group_id} 也失败: {e2}")