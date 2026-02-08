"""
自动调度器模块
负责定时任务和自动分析功能
"""

import asyncio
import weakref

from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger

from ..core.message_sender import MessageSender
from ..reports.dispatcher import ReportDispatcher
from ..utils.trace_context import TraceContext


class AutoScheduler:
    """自动调度器"""

    def __init__(
        self,
        config_manager,
        message_handler,
        analyzer,
        report_generator,
        bot_manager,
        retry_manager,
        history_manager,
        html_render_func=None,
    ):
        self.config_manager = config_manager
        self.message_handler = message_handler
        self.analyzer = analyzer
        self.report_generator = report_generator
        self.bot_manager = bot_manager
        self.retry_manager = retry_manager  # 保存引用
        self.history_manager = history_manager
        self.html_render_func = html_render_func

        # Initialize Core Components
        self.message_sender = MessageSender(bot_manager, config_manager, retry_manager)
        self.report_dispatcher = ReportDispatcher(
            config_manager, report_generator, self.message_sender, retry_manager
        )
        if html_render_func:
            self.report_dispatcher.set_html_render(html_render_func)

        self.scheduler_job_ids = []  # Store scheduled job IDs
        self.last_executed_target = None  # 记录上次执行的具体时间点，防止重复执行

    def set_bot_instance(self, bot_instance):
        """设置bot实例（保持向后兼容）"""
        self.bot_manager.set_bot_instance(bot_instance)

    def set_bot_qq_ids(self, bot_qq_ids):
        """设置bot QQ号（支持单个QQ号或QQ号列表）"""
        # 确保传入的是列表，保持统一处理
        if isinstance(bot_qq_ids, list):
            self.bot_manager.set_bot_qq_ids(bot_qq_ids)
        elif bot_qq_ids:
            self.bot_manager.set_bot_qq_ids([bot_qq_ids])

    async def get_platform_id_for_group(self, group_id):
        """根据群ID获取对应的平台ID"""
        try:
            # 首先检查已注册的bot实例
            if (
                hasattr(self.bot_manager, "_bot_instances")
                and self.bot_manager._bot_instances
            ):
                # 如果只有一个实例，直接返回
                if len(self.bot_manager._bot_instances) == 1:
                    platform_id = list(self.bot_manager._bot_instances.keys())[0]
                    logger.debug(f"只有一个适配器，使用平台: {platform_id}")
                    return platform_id

                # 如果有多个实例，尝试通过API检查群属于哪个适配器
                logger.info(f"检测到多个适配器，正在验证群 {group_id} 属于哪个平台...")
                for platform_id in self.bot_manager.get_all_bot_instances().keys():
                    try:
                        # 优先使用 Adapter (DDD)
                        adapter = self.bot_manager.get_adapter(platform_id)
                        if adapter:
                            info = await adapter.get_group_info(str(group_id))
                            if info:
                                logger.info(f"✅ 群 {group_id} 属于平台 {platform_id}")
                                return platform_id
                            else:
                                logger.debug(
                                    f"平台 {platform_id} 无法获取群 {group_id} 信息 (返回None)"
                                )
                            continue

                        # 回退到原始逻辑 (Legacy)
                        bot_instance = self.bot_manager.get_bot_instance(platform_id)
                        if hasattr(bot_instance, "call_action"):
                            result = await bot_instance.call_action(
                                "get_group_info", group_id=int(group_id)
                            )
                            if result and result.get("group_id"):
                                logger.info(f"✅ 群 {group_id} 属于平台 {platform_id}")
                                return platform_id
                    except Exception as e:
                        logger.debug(f"平台 {platform_id} 验证群 {group_id} 失败: {e}")
                        continue

                        # 回退到原始逻辑 (Legacy)
                        bot_instance = self.bot_manager.get_bot_instance(platform_id)
                        if hasattr(bot_instance, "call_action"):
                            result = await bot_instance.call_action(
                                "get_group_info", group_id=int(group_id)
                            )
                            if result and result.get("group_id"):
                                logger.info(f"✅ 群 {group_id} 属于平台 {platform_id}")
                                return platform_id
                    except Exception as e:
                        logger.debug(f"平台 {platform_id} 验证群 {group_id} 失败: {e}")
                        continue

                # 如果所有适配器都尝试失败，记录错误并返回 None
                logger.error(
                    f"❌ 无法确定群 {group_id} 属于哪个平台 (已尝试: {list(self.bot_manager._bot_instances.keys())})"
                )
                return None

            # 没有任何bot实例，返回None
            logger.error("❌ 没有注册的bot实例")
            return None
        except Exception as e:
            logger.error(f"❌ 获取平台ID失败: {e}")
            return None

    def schedule_jobs(self, context):
        """注册定时任务"""
        # 先清理旧任务
        self.unschedule_jobs(context)

        if not self.config_manager.get_enable_auto_analysis():
            logger.info("自动分析功能未启用，不注册定时任务")
            return

        time_config = self.config_manager.get_auto_analysis_time()
        if isinstance(time_config, str):
            time_config = [time_config]

        scheduler = context.cron_manager.scheduler

        for i, t_str in enumerate(time_config):
            try:
                # t_str format: "HH:MM"
                t_str = str(t_str).replace("：", ":").strip()
                hour, minute = t_str.split(":")

                # Create CronTrigger
                trigger = CronTrigger(hour=int(hour), minute=int(minute))

                # Job ID
                job_id = f"astrbot_plugin_qq_group_daily_analysis_trigger_{i}"

                # Add job
                scheduler.add_job(
                    self._run_auto_analysis,
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=60,
                )
                self.scheduler_job_ids.append(job_id)
                logger.info(f"已注册定时自动分析任务: {t_str} (Job ID: {job_id})")

            except Exception as e:
                logger.error(f"注册定时任务失败 ({t_str}): {e}")

    def unschedule_jobs(self, context):
        """取消定时任务"""
        scheduler = context.cron_manager.scheduler
        for job_id in self.scheduler_job_ids:
            try:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                    logger.debug(f"已移除定时任务: {job_id}")
            except Exception as e:
                logger.warning(f"移除定时任务失败 ({job_id}): {e}")
        self.scheduler_job_ids.clear()

    async def _run_auto_analysis(self):
        """执行自动分析 - 并发处理所有群聊"""
        try:
            logger.info("开始执行自动群聊分析（并发模式）")

            # 根据配置确定需要分析的群组
            group_list_mode = self.config_manager.get_group_list_mode()

            # 始终获取所有群组并进行过滤
            logger.info(f"自动分析使用 {group_list_mode} 模式，正在获取群列表...")
            all_groups = await self._get_all_groups()
            logger.info(f"共获取到 {len(all_groups)} 个群组")
            enabled_groups = []

            for platform_id, group_id in all_groups:
                # 构造 UMO 进行检查
                umo = f"{platform_id}:GroupMessage:{group_id}"
                # 检查 UMO 是否允许 (ConfigManager 会自动处理 UMO 和 Simple ID 的匹配逻辑)
                if self.config_manager.is_group_allowed(umo):
                    enabled_groups.append(group_id)

            logger.info(
                f"根据 {group_list_mode} 过滤后，共有 {len(enabled_groups)} 个群聊需要分析"
            )

            if not enabled_groups:
                logger.info("没有启用的群聊需要分析")
                return

            logger.info(
                f"将为 {len(enabled_groups)} 个群聊并发执行分析: {enabled_groups}"
            )

            # 创建并发任务 - 为每个群聊创建独立的分析任务
            # 限制最大并发数
            max_concurrent = self.config_manager.get_max_concurrent_tasks()
            logger.info(f"自动分析并发数限制: {max_concurrent}")
            sem = asyncio.Semaphore(max_concurrent)

            async def safe_perform_analysis(group_id):
                async with sem:
                    return await self._perform_auto_analysis_for_group_with_timeout(
                        group_id
                    )

            analysis_tasks = []
            for group_id in enabled_groups:
                task = asyncio.create_task(
                    safe_perform_analysis(group_id),
                    name=f"analysis_group_{group_id}",
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

            logger.info(
                f"并发分析完成 - 成功: {success_count}, 失败: {error_count}, 总计: {len(enabled_groups)}"
            )

        except Exception as e:
            logger.error(f"自动分析执行失败: {e}", exc_info=True)

    async def _perform_auto_analysis_for_group_with_timeout(self, group_id: str):
        """为指定群执行自动分析（带超时控制）"""
        try:
            # 为每个群聊设置独立的超时时间（20分钟）- 使用 asyncio.wait_for 兼容所有 Python 版本
            await asyncio.wait_for(
                self._perform_auto_analysis_for_group(group_id), timeout=1200
            )
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 分析超时（20分钟），跳过该群分析")
        except Exception as e:
            logger.error(f"群 {group_id} 分析任务执行失败: {e}")

    async def _perform_auto_analysis_for_group(self, group_id: str):
        """为指定群执行自动分析（核心逻辑）"""
        # 为每个群聊使用独立的锁，避免全局锁导致串行化
        group_lock_key = f"analysis_{group_id}"
        if not hasattr(self, "_group_locks"):
            self._group_locks = weakref.WeakValueDictionary()

        # 从 WeakValueDictionary 获取锁，如果不存在则创建
        # 注意：必须将锁赋值给局部变量以保持引用，否则可能会被回收
        lock = self._group_locks.get(group_lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._group_locks[group_lock_key] = lock

        async with lock:
            try:
                start_time = asyncio.get_event_loop().time()

                # 设置 TraceID
                trace_id = TraceContext.generate(prefix=f"group_{group_id}")
                TraceContext.set(trace_id)

                # 获取当前日期和时间槽 (HH-MM)
                import datetime

                now = datetime.datetime.now()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H-%M")

                # 检查是否已有该时间段分析记录
                if await self.history_manager.has_history(group_id, date_str, time_str):
                    logger.info(
                        f"群 {group_id} 在 {date_str} {time_str} 已有分析记录，跳过自动分析"
                    )
                    return

                logger.info(f"开始为群 {group_id} 执行自动分析（并发任务）")

                # 检查bot管理器状态
                if not self.bot_manager.is_ready_for_auto_analysis():
                    status = self.bot_manager.get_status_info()
                    logger.warning(
                        f"群 {group_id} 自动分析跳过：bot管理器未就绪 - {status}"
                    )
                    return

                logger.info(f"开始为群 {group_id} 执行自动分析（并发任务）")

                # 获取所有可用的平台，依次尝试获取消息
                messages = None
                platform_id = None
                bot_instance = None

                # 获取所有可用的平台ID和bot实例
                if (
                    hasattr(self.bot_manager, "_bot_instances")
                    and self.bot_manager._bot_instances
                ):
                    available_platforms = list(self.bot_manager._bot_instances.items())
                    logger.info(
                        f"群 {group_id} 检测到 {len(available_platforms)} 个可用平台，开始依次尝试..."
                    )

                    for test_platform_id, test_bot_instance in available_platforms:
                        # 检查该平台是否启用了此插件
                        if not self.bot_manager.is_plugin_enabled(
                            test_platform_id, "astrbot_plugin_qq_group_daily_analysis"
                        ):
                            logger.debug(f"平台 {test_platform_id} 未启用此插件，跳过")
                            continue

                        try:
                            logger.info(
                                f"尝试使用平台 {test_platform_id} 获取群 {group_id} 的消息..."
                            )
                            analysis_days = self.config_manager.get_analysis_days()
                            test_messages = (
                                await self.message_handler.fetch_group_messages(
                                    test_bot_instance,
                                    group_id,
                                    analysis_days,
                                    test_platform_id,
                                )
                            )

                            if test_messages and len(test_messages) > 0:
                                # 成功获取到消息，使用这个平台
                                messages = test_messages
                                platform_id = test_platform_id
                                bot_instance = test_bot_instance
                                logger.info(
                                    f"✅ 群 {group_id} 成功通过平台 {platform_id} 获取到 {len(messages)} 条消息"
                                )
                                break
                            else:
                                logger.debug(
                                    f"平台 {test_platform_id} 未获取到消息，继续尝试下一个平台"
                                )
                        except Exception as e:
                            logger.debug(
                                f"平台 {test_platform_id} 获取消息失败: {e}，继续尝试下一个平台"
                            )
                            continue

                    if not messages:
                        logger.warning(
                            f"群 {group_id} 所有平台都尝试失败，未获取到足够的消息记录"
                        )
                        return
                else:
                    # 回退到原来的逻辑（单个平台）
                    logger.warning(f"群 {group_id} 没有多个平台可用，使用回退逻辑")
                    platform_id = await self.get_platform_id_for_group(group_id)

                    if not platform_id:
                        logger.error(f"❌ 群 {group_id} 无法获取平台ID，跳过分析")
                        return

                    bot_instance = self.bot_manager.get_bot_instance(platform_id)

                    if not bot_instance:
                        logger.error(
                            f"❌ 群 {group_id} 未找到对应的bot实例（平台: {platform_id}）"
                        )
                        return

                    # 获取群聊消息
                    analysis_days = self.config_manager.get_analysis_days()
                    messages = await self.message_handler.fetch_group_messages(
                        bot_instance, group_id, analysis_days, platform_id
                    )

                    if messages is None:
                        logger.warning(f"群 {group_id} 获取消息失败，跳过分析")
                        return
                    elif not messages:
                        logger.warning(f"群 {group_id} 未获取到足够的消息记录")
                        return

                # 检查消息数量
                min_threshold = self.config_manager.get_min_messages_threshold()
                if len(messages) < min_threshold:
                    logger.warning(
                        f"群 {group_id} 消息数量不足（{len(messages)}条），跳过分析"
                    )
                    return

                logger.info(f"群 {group_id} 获取到 {len(messages)} 条消息，开始分析")

                # 进行分析 - 构造正确的 unified_msg_origin
                # platform_id 已经在前面获取，直接使用
                umo = f"{platform_id}:GroupMessage:{group_id}" if platform_id else None
                analysis_result = await self.analyzer.analyze_messages(
                    messages, group_id, umo
                )
                if not analysis_result:
                    logger.error(f"群 {group_id} 分析失败")
                    return

                # 生成并发送报告
                # await self._send_analysis_report(group_id, analysis_result, platform_id)
                await self.report_dispatcher.dispatch(
                    group_id, analysis_result, platform_id
                )

                # 保存到历史记录
                await self.history_manager.save_analysis(
                    group_id, analysis_result, date_str, time_str
                )

                # 记录执行时间
                end_time = asyncio.get_event_loop().time()
                execution_time = end_time - start_time
                logger.info(f"群 {group_id} 分析完成，耗时: {execution_time:.2f}秒")

            except Exception as e:
                logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)

            finally:
                # 锁资源由 WeakValueDictionary 自动管理，无需手动清理
                logger.info(f"群 {group_id} 自动分析完成")

    async def _get_all_groups(self) -> list[tuple[str, str]]:
        """
        获取所有bot实例所在的群列表 (使用 PlatformAdapter)
        Returns:
            list[tuple[str, str]]: [(platform_id, group_id), ...]
        """
        all_groups = set()

        if (
            not hasattr(self.bot_manager, "_bot_instances")
            or not self.bot_manager._bot_instances
        ):
            return []

        # 延迟导入以避免循环依赖
        from ..infrastructure.platform.factory import PlatformAdapterFactory

        for platform_id, bot_instance in self.bot_manager._bot_instances.items():
            # 检查该平台是否启用了此插件
            if not self.bot_manager.is_plugin_enabled(
                platform_id, "astrbot_plugin_qq_group_daily_analysis"
            ):
                logger.debug(f"平台 {platform_id} 未启用此插件，跳过获取群列表")
                continue

            try:
                # 1. 尝试检测平台名称
                platform_name = self.bot_manager._detect_platform_name(bot_instance)

                # 2. 创建适配器
                adapter = None
                if platform_name:
                    adapter = PlatformAdapterFactory.create(
                        platform_name,
                        bot_instance,
                        config={"bot_qq_ids": self.config_manager.get_bot_qq_ids()},
                    )

                # 3. 如果适配器创建成功，使用通用接口获取群列表
                if adapter:
                    try:
                        groups = await adapter.get_group_list()
                        for group_id in groups:
                            all_groups.add((platform_id, str(group_id)))
                        logger.info(
                            f"平台 {platform_id} ({platform_name}) 成功获取 {len(groups)} 个群组"
                        )
                        continue  # 成功则跳过后续尝试
                    except Exception as e:
                        logger.warning(f"适配器 {platform_name} 获取群列表失败: {e}")

                # 4. (可选) 保留降级逻辑，或者直接依赖适配器
                # 鉴于我们已经确认 OneBot 和 Discord 都有适配器，这里可以简化
                logger.debug(f"平台 {platform_id} 无法通过适配器获取群列表")

            except Exception as e:
                logger.error(f"平台 {platform_id} 获取群列表异常: {e}")

        return list(all_groups)
