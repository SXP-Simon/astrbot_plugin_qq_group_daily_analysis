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

    def set_bot_self_ids(self, bot_self_ids):
        """设置bot ID（支持单个ID或ID列表）"""
        # 确保传入的是列表，保持统一处理
        if isinstance(bot_self_ids, list):
            self.bot_manager.set_bot_self_ids(bot_self_ids)
        elif bot_self_ids:
            self.bot_manager.set_bot_self_ids([bot_self_ids])

    def set_bot_qq_ids(self, bot_qq_ids):
        """设置bot QQ号（已弃用，使用 set_bot_self_ids）"""
        self.set_bot_self_ids(bot_qq_ids)

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

            # 使用 set 存储 (group_id, platform_id) 元组，避免重复
            # platform_id 可以为 None (如果是从纯群号配置通过 get_group_list 获取的，或者只是纯群号配置)
            # 但为了准确性，我们尽量保留 platform_id
            enabled_targets = set()

            # 1. 尝试通过 API 获取所有群组 (Discovery)
            logger.info(f"自动分析使用 {group_list_mode} 模式，正在获取群列表...")
            all_groups = await self._get_all_groups()
            logger.info(f"共获取到 {len(all_groups)} 个群组")

            for platform_id, group_id in all_groups:
                # 构造 UMO 进行检查
                umo = f"{platform_id}:GroupMessage:{group_id}"
                if self.config_manager.is_group_allowed(umo):
                    enabled_targets.add((str(group_id), str(platform_id)))

            # 2. 如果是 whitelist 模式，额外检查配置中的 UMO
            # 这可以解决 get_group_list 失败 (返回0个群) 但配置了明确 UMO 的情况
            if group_list_mode == "whitelist":
                whitelist_config = self.config_manager.get_group_list()
                logger.info(
                    f"正在检查白名单配置中的额外 UMO ({len(whitelist_config)} 条)..."
                )

                for item in whitelist_config:
                    item = str(item).strip()
                    # 如果是 UMO 格式 (e.g. lulouch:GroupMessage:123456)
                    if ":" in item:
                        parts = item.split(":")
                        if len(parts) >= 3:
                            p_id = parts[0]
                            g_id = parts[-1]

                            # 检查该平台是否存在
                            if self.bot_manager.get_bot_instance(p_id):
                                enabled_targets.add((str(g_id), str(p_id)))
                                logger.debug(f"添加白名单 UMO 目标: {item}")
                            else:
                                logger.warning(
                                    f"白名单 UMO {item} 对应的平台 {p_id} 不存在或未加载"
                                )

            logger.info(
                f"根据 {group_list_mode} 过滤及合并后，共有 {len(enabled_targets)} 个群聊需要分析"
            )

            if not enabled_targets:
                logger.info("没有启用的群聊需要分析")
                return

            # 转为列表以便索引
            target_list = list(enabled_targets)  # [(group_id, platform_id), ...]

            logger.info(f"将为 {len(target_list)} 个群聊并发执行分析")

            # 创建并发任务 - 为每个群聊创建独立的分析任务
            # 限制最大并发数
            max_concurrent = self.config_manager.get_max_concurrent_tasks()
            logger.info(f"自动分析并发数限制: {max_concurrent}")
            sem = asyncio.Semaphore(max_concurrent)

            async def safe_perform_analysis(gid, pid):
                async with sem:
                    return await self._perform_auto_analysis_for_group_with_timeout(
                        gid, pid
                    )

            analysis_tasks = []
            for gid, pid in target_list:
                task = asyncio.create_task(
                    safe_perform_analysis(gid, pid),
                    name=f"analysis_group_{gid}",
                )
                analysis_tasks.append(task)

            # 并发执行所有分析任务
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # 统计执行结果
            success_count = 0
            error_count = 0

            for i, result in enumerate(results):
                gid, _ = target_list[i]
                if isinstance(result, Exception):
                    logger.error(f"群 {gid} 分析任务异常: {result}")
                    error_count += 1
                else:
                    success_count += 1

            logger.info(
                f"并发分析完成 - 成功: {success_count}, 失败: {error_count}, 总计: {len(target_list)}"
            )

        except Exception as e:
            logger.error(f"自动分析执行失败: {e}", exc_info=True)

    async def _perform_auto_analysis_for_group_with_timeout(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群执行自动分析（带超时控制）"""
        try:
            # 为每个群聊设置独立的超时时间（20分钟）
            await asyncio.wait_for(
                self._perform_auto_analysis_for_group(group_id, target_platform_id),
                timeout=1200,
            )
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 分析超时（20分钟），跳过该群分析")
        except Exception as e:
            logger.error(f"群 {group_id} 分析任务执行失败: {e}")

    async def _perform_auto_analysis_for_group(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群执行自动分析（核心逻辑）"""
        # 为每个群聊使用独立的锁
        group_lock_key = f"analysis_{group_id}"
        if not hasattr(self, "_group_locks"):
            self._group_locks = weakref.WeakValueDictionary()

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

                import datetime

                now = datetime.datetime.now()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H-%M")

                if await self.history_manager.has_history(group_id, date_str, time_str):
                    logger.info(
                        f"群 {group_id} 在 {date_str} {time_str} 已有分析记录，跳过自动分析"
                    )
                    return

                logger.info(f"开始为群 {group_id} 执行自动分析（并发任务）")

                if not self.bot_manager.is_ready_for_auto_analysis():
                    status = self.bot_manager.get_status_info()
                    logger.warning(
                        f"群 {group_id} 自动分析跳过：bot管理器未就绪 - {status}"
                    )
                    return

                messages = None
                platform_id = None
                bot_instance = None

                # 1. 优先使用指定的 platform_id (如果有)
                if target_platform_id:
                    if self.bot_manager.is_plugin_enabled(
                        target_platform_id, "astrbot_plugin_qq_group_daily_analysis"
                    ):
                        try:
                            logger.info(
                                f"使用指定平台 {target_platform_id} 获取群 {group_id} 的消息..."
                            )
                            bot_instance = self.bot_manager.get_bot_instance(
                                target_platform_id
                            )
                            if bot_instance:
                                analysis_days = self.config_manager.get_analysis_days()
                                messages = (
                                    await self.message_handler.fetch_group_messages(
                                        bot_instance,
                                        group_id,
                                        analysis_days,
                                        target_platform_id,
                                    )
                                )
                                if messages:
                                    platform_id = target_platform_id
                                    logger.info(
                                        f"✅ 群 {group_id} 成功通过平台 {platform_id} 获取到 {len(messages)} 条消息"
                                    )
                        except Exception as e:
                            logger.error(
                                f"指定平台 {target_platform_id} 获取消息失败: {e}"
                            )

                # 2. 如果指定平台失败或没有指定，尝试自动检测 (原有逻辑)
                if not messages:
                    # 获取所有可用的平台ID和bot实例
                    if (
                        hasattr(self.bot_manager, "_bot_instances")
                        and self.bot_manager._bot_instances
                    ):
                        available_platforms = list(
                            self.bot_manager._bot_instances.items()
                        )
                        logger.info(
                            f"群 {group_id} 检测到 {len(available_platforms)} 个可用平台，开始依次尝试..."
                        )

                        for test_platform_id, test_bot_instance in available_platforms:
                            # 如果已经试过 target_platform_id，跳过
                            if (
                                target_platform_id
                                and test_platform_id == target_platform_id
                            ):
                                continue

                            # 检查该平台是否启用了此插件
                            if not self.bot_manager.is_plugin_enabled(
                                test_platform_id,
                                "astrbot_plugin_qq_group_daily_analysis",
                            ):
                                logger.debug(
                                    f"平台 {test_platform_id} 未启用此插件，跳过"
                                )
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
                        # 回退到原来的逻辑（单个平台）- 几乎不会走到这里，除非 _bot_instances 为空
                        pass  # 省略 legacy 逻辑，因为 _bot_instances 为空在上面 is_ready 检查了

                if not messages:
                    # 最后尝试 legacy get_platform_id_for_group
                    # ... (Keep existing fallback if needed, but the loop above covers most cases)
                    pass

                # 检查消息数量
                min_threshold = self.config_manager.get_min_messages_threshold()
                if not messages or len(messages) < min_threshold:
                    logger.warning(
                        f"群 {group_id} 消息数量不足（{len(messages) if messages else 0}条），跳过分析"
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
                        config={
                            "bot_self_ids": self.config_manager.get_bot_self_ids(),
                        },
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
