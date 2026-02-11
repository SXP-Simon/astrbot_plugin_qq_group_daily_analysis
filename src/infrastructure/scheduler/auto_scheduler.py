"""
自动调度器模块
负责定时任务和自动分析功能，支持传统单次分析与增量多次分析两种调度模式。
"""

import asyncio
import time as time_mod
import weakref
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ...utils.logger import logger
from ...utils.trace_context import TraceContext
from ..messaging.message_sender import MessageSender
from ..platform.factory import PlatformAdapterFactory
from ..reporting.dispatcher import ReportDispatcher


class AutoScheduler:
    """自动调度器，支持传统模式和增量模式"""

    def __init__(
        self,
        config_manager,
        analysis_service,
        bot_manager,
        retry_manager,
        report_generator=None,
        html_render_func=None,
        plugin_instance: Any | None = None,
    ):
        self.config_manager = config_manager
        self.analysis_service = analysis_service
        self.bot_manager = bot_manager
        self.retry_manager = retry_manager
        self.report_generator = report_generator
        self.html_render_func = html_render_func
        self.plugin_instance = plugin_instance

        # 初始化核心组件
        self.message_sender = MessageSender(bot_manager, config_manager, retry_manager)
        self.report_dispatcher = ReportDispatcher(
            config_manager, report_generator, self.message_sender, retry_manager
        )
        if html_render_func:
            self.report_dispatcher.set_html_render(html_render_func)

        self.scheduler_job_ids = []  # 存储已注册的定时任务 ID
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
                if self.bot_manager.get_platform_count() == 1:
                    platform_id = self.bot_manager.get_platform_ids()[0]
                    logger.debug(f"只有一个适配器，使用平台: {platform_id}")
                    return platform_id

                # 如果有多个实例，尝试通过适配器检查群属于哪个平台
                logger.info(f"检测到多个适配器，正在验证群 {group_id} 属于哪个平台...")
                for platform_id in self.bot_manager.get_platform_ids():
                    try:
                        adapter = self.bot_manager.get_adapter(platform_id)
                        if adapter:
                            # 通过统一接口尝试获取群信息，如果能获取到则说明属于该平台
                            info = await adapter.get_group_info(str(group_id))
                            if info:
                                logger.info(f"✅ 群 {group_id} 属于平台 {platform_id}")
                                return platform_id
                            else:
                                logger.debug(
                                    f"平台 {platform_id} 无法获取群 {group_id} 信息"
                                )
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

    # ================================================================
    # 任务注册与取消
    # ================================================================

    def schedule_jobs(self, context):
        """注册定时任务，根据配置选择传统模式或增量模式"""
        # 先清理旧任务
        self.unschedule_jobs(context)

        if not self.config_manager.get_enable_auto_analysis():
            logger.info("自动分析功能未启用，不注册定时任务")
            return

        scheduler = context.cron_manager.scheduler

        # 根据增量模式开关决定调度策略
        if self.config_manager.get_incremental_enabled():
            logger.info("增量分析模式已启用，注册增量调度任务")
            self._schedule_incremental_jobs(scheduler)
        else:
            logger.info("使用传统分析模式，注册定时分析任务")
            self._schedule_traditional_jobs(scheduler)

    def _schedule_traditional_jobs(self, scheduler):
        """注册传统模式的定时任务（在配置的时间点执行完整分析）"""
        time_config = self.config_manager.get_auto_analysis_time()
        if isinstance(time_config, str):
            time_config = [time_config]

        for i, t_str in enumerate(time_config):
            try:
                # t_str 格式: "HH:MM"
                t_str = str(t_str).replace("：", ":").strip()
                hour, minute = t_str.split(":")

                # 创建 CronTrigger
                trigger = CronTrigger(hour=int(hour), minute=int(minute))

                # 任务 ID
                job_id = f"astrbot_plugin_qq_group_daily_analysis_trigger_{i}"

                # 添加任务
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

    def _schedule_incremental_jobs(self, scheduler):
        """
        注册增量模式的定时任务。

        在活跃时段内按固定间隔注册增量分析任务，
        并在配置的报告时间点注册最终报告生成任务。
        """
        active_start_hour = self.config_manager.get_incremental_active_start_hour()
        active_end_hour = self.config_manager.get_incremental_active_end_hour()
        interval_minutes = self.config_manager.get_incremental_interval_minutes()
        max_daily = self.config_manager.get_incremental_max_daily_analyses()

        # 计算增量分析触发时间点
        trigger_times = []
        current_minutes = active_start_hour * 60  # 从活跃开始小时的 :00 开始
        end_minutes = active_end_hour * 60

        while current_minutes < end_minutes and len(trigger_times) < max_daily:
            hour = current_minutes // 60
            minute = current_minutes % 60
            trigger_times.append((hour, minute))
            current_minutes += interval_minutes

        # 注册增量分析任务
        for hour, minute in trigger_times:
            try:
                trigger = CronTrigger(hour=hour, minute=minute)
                job_id = f"incremental_analysis_{hour:02d}{minute:02d}"

                scheduler.add_job(
                    self._run_incremental_analysis,
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=60,
                )
                self.scheduler_job_ids.append(job_id)
                logger.info(
                    f"已注册增量分析任务: {hour:02d}:{minute:02d} (Job ID: {job_id})"
                )
            except Exception as e:
                logger.error(f"注册增量分析任务失败 ({hour:02d}:{minute:02d}): {e}")

        # 注册最终报告生成任务（使用配置的自动分析时间点）
        time_config = self.config_manager.get_auto_analysis_time()
        if isinstance(time_config, str):
            time_config = [time_config]

        for i, t_str in enumerate(time_config):
            try:
                t_str = str(t_str).replace("：", ":").strip()
                hour_str, minute_str = t_str.split(":")

                trigger = CronTrigger(hour=int(hour_str), minute=int(minute_str))
                job_id = f"incremental_final_report_{i}"

                scheduler.add_job(
                    self._run_incremental_final_report,
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=60,
                )
                self.scheduler_job_ids.append(job_id)
                logger.info(f"已注册增量最终报告任务: {t_str} (Job ID: {job_id})")
            except Exception as e:
                logger.error(f"注册增量最终报告任务失败 ({t_str}): {e}")

        logger.info(
            f"增量调度注册完成: {len(trigger_times)} 个增量分析任务, "
            f"{len(time_config)} 个最终报告任务"
        )

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

    # ================================================================
    # 共享辅助方法：获取启用的群聊目标
    # ================================================================

    async def _get_enabled_targets(self) -> set[tuple[str, str]]:
        """
        获取所有启用分析的群聊目标。

        根据群组列表模式（白名单/黑名单/无限制）过滤群聊，
        返回去重后的 (group_id, platform_id) 集合。

        Returns:
            set[tuple[str, str]]: 启用分析的 (群ID, 平台ID) 集合
        """
        group_list_mode = self.config_manager.get_group_list_mode()

        # 使用 set 存储 (group_id, platform_id) 元组，避免重复
        enabled_targets = set()

        # 1. 通过 API 获取所有群组（自动发现）
        logger.info(f"自动分析使用 {group_list_mode} 模式，正在获取群列表...")
        all_groups = await self._get_all_groups()
        logger.info(f"共获取到 {len(all_groups)} 个群组")

        for platform_id, group_id in all_groups:
            # 构造 UMO 进行权限检查
            umo = f"{platform_id}:GroupMessage:{group_id}"
            if self.config_manager.is_group_allowed(umo):
                enabled_targets.add((str(group_id), str(platform_id)))

        # 2. 白名单模式下，额外检查配置中的 UMO
        # 解决 get_group_list 失败但配置了明确 UMO 的情况
        if group_list_mode == "whitelist":
            whitelist_config = self.config_manager.get_group_list()
            logger.info(
                f"正在检查白名单配置中的额外 UMO ({len(whitelist_config)} 条)..."
            )

            for item in whitelist_config:
                item = str(item).strip()
                # 如果是 UMO 格式 (例: platform_id:GroupMessage:group_id)
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

        return enabled_targets

    # ================================================================
    # 传统模式：自动分析
    # ================================================================

    async def _run_auto_analysis(self):
        """执行传统自动分析 - 并发处理所有群聊"""
        try:
            logger.info("开始执行自动群聊分析（并发模式）")

            enabled_targets = await self._get_enabled_targets()

            if not enabled_targets:
                logger.info("没有启用的群聊需要分析")
                return

            # 转为列表以便索引
            target_list = list(enabled_targets)

            logger.info(f"将为 {len(target_list)} 个群聊并发执行分析")

            # 创建并发任务，限制最大并发数
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
        """为指定群执行自动分析（业务逻辑委派给 AnalysisApplicationService）"""
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
                # 设置 TraceID
                trace_id = TraceContext.generate(prefix=f"group_{group_id}")
                TraceContext.set(trace_id)

                logger.info(
                    f"开始为群 {group_id} 执行自动分析 (Platform: {target_platform_id or 'Auto'})"
                )

                # 检查平台状态 (BotManager 为基础设施层，用于获取平台就绪状态)
                if not self.bot_manager.is_ready_for_auto_analysis():
                    logger.warning(f"群 {group_id} 自动分析跳过：bot管理器未就绪")
                    return

                # 委派给应用层服务执行核心用例
                result = await self.analysis_service.execute_daily_analysis(
                    group_id=group_id, platform_id=target_platform_id, manual=False
                )

                if not result.get("success"):
                    reason = result.get("reason")
                    logger.info(f"群 {group_id} 自动分析跳过: {reason}")
                    return

                # 获取分析结果及适配器
                analysis_result = result["analysis_result"]
                adapter = result["adapter"]

                # 调度导出并发送报告（由 ReportDispatcher 协调）
                await self.report_dispatcher.dispatch(
                    group_id,
                    analysis_result,
                    adapter.platform_id
                    if hasattr(adapter, "platform_id")
                    else target_platform_id,
                )

                logger.info(f"群 {group_id} 自动分析任务执行成功")

            except Exception as e:
                logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)
            finally:
                logger.debug(f"群 {group_id} 自动分析流程结束")

    # ================================================================
    # 增量模式：增量分析
    # ================================================================

    async def _run_incremental_analysis(self):
        """执行增量分析 - 为所有启用的群聊执行一次增量分析批次"""
        try:
            logger.info("开始执行增量分析（交错并发模式）")

            enabled_targets = await self._get_enabled_targets()

            if not enabled_targets:
                logger.info("没有启用的群聊需要增量分析")
                return

            target_list = list(enabled_targets)
            stagger = self.config_manager.get_incremental_stagger_seconds()
            max_concurrent = self.config_manager.get_max_concurrent_tasks()

            logger.info(
                f"将为 {len(target_list)} 个群聊执行增量分析 "
                f"(并发限制: {max_concurrent}, 交错间隔: {stagger}秒)"
            )

            sem = asyncio.Semaphore(max_concurrent)

            async def staggered_incremental(idx, gid, pid):
                async with sem:
                    # 按索引交错延迟，均匀分散 API 压力
                    if idx > 0 and stagger > 0:
                        await asyncio.sleep(stagger * idx)

                    result = (
                        await self._perform_incremental_analysis_for_group_with_timeout(
                            gid, pid
                        )
                    )

                    # 检查是否需要立即发送报告（调试模式）
                    if self.config_manager.get_incremental_report_immediately():
                        if isinstance(result, dict) and result.get("success"):
                            logger.info(
                                f"增量分析立即报告模式生效，正在为群 {gid} 生成报告..."
                            )
                            # 立即生成最终报告
                            await self._perform_incremental_final_report_for_group_with_timeout(
                                gid, pid
                            )

                    return result

            analysis_tasks = []
            for idx, (gid, pid) in enumerate(target_list):
                task = asyncio.create_task(
                    staggered_incremental(idx, gid, pid),
                    name=f"incremental_group_{gid}",
                )
                analysis_tasks.append(task)

            # 并发执行所有增量分析任务
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # 统计执行结果
            success_count = 0
            skip_count = 0
            error_count = 0

            for i, result in enumerate(results):
                gid, _ = target_list[i]
                if isinstance(result, Exception):
                    logger.error(f"群 {gid} 增量分析任务异常: {result}")
                    error_count += 1
                elif isinstance(result, dict) and not result.get("success", True):
                    skip_count += 1
                else:
                    success_count += 1

            logger.info(
                f"增量分析完成 - 成功: {success_count}, 跳过: {skip_count}, "
                f"失败: {error_count}, 总计: {len(target_list)}"
            )

        except Exception as e:
            logger.error(f"增量分析执行失败: {e}", exc_info=True)

    async def _perform_incremental_analysis_for_group_with_timeout(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群执行增量分析（带超时控制，10分钟）"""
        try:
            result = await asyncio.wait_for(
                self._perform_incremental_analysis_for_group(
                    group_id, target_platform_id
                ),
                timeout=600,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 增量分析超时（10分钟），跳过")
            return {"success": False, "reason": "timeout"}
        except Exception as e:
            logger.error(f"群 {group_id} 增量分析任务执行失败: {e}")
            return {"success": False, "reason": str(e)}

    async def _perform_incremental_analysis_for_group(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群执行增量分析（业务逻辑委派给 AnalysisApplicationService）"""
        # 为每个群聊使用独立的锁
        group_lock_key = f"incremental_{group_id}"
        if not hasattr(self, "_group_locks"):
            self._group_locks = weakref.WeakValueDictionary()

        lock = self._group_locks.get(group_lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._group_locks[group_lock_key] = lock

        async with lock:
            try:
                # 设置 TraceID
                trace_id = TraceContext.generate(prefix=f"incr_{group_id}")
                TraceContext.set(trace_id)

                logger.info(
                    f"开始为群 {group_id} 执行增量分析 "
                    f"(Platform: {target_platform_id or 'Auto'})"
                )

                # 检查平台状态
                if not self.bot_manager.is_ready_for_auto_analysis():
                    logger.warning(f"群 {group_id} 增量分析跳过：bot管理器未就绪")
                    return {"success": False, "reason": "bot_not_ready"}

                # 委派给应用层服务执行增量分析用例
                result = await self.analysis_service.execute_incremental_analysis(
                    group_id=group_id, platform_id=target_platform_id
                )

                if not result.get("success"):
                    reason = result.get("reason", "unknown")
                    logger.info(f"群 {group_id} 增量分析跳过: {reason}")
                    return result

                # 增量分析只累积数据，不发送报告
                batch_summary = result.get("batch_summary", {})
                logger.info(
                    f"群 {group_id} 增量分析完成: "
                    f"消息数={result.get('messages_count', 0)}, "
                    f"话题={batch_summary.get('topics_count', 0)}, "
                    f"金句={batch_summary.get('quotes_count', 0)}"
                )
                return result

            except Exception as e:
                logger.error(f"群 {group_id} 增量分析执行失败: {e}", exc_info=True)
                return {"success": False, "reason": str(e)}
            finally:
                logger.debug(f"群 {group_id} 增量分析流程结束")

    # ================================================================
    # 增量模式：最终报告生成
    # ================================================================

    async def _run_incremental_final_report(self):
        """基于当天增量累积数据生成并发送最终报告"""
        try:
            logger.info("开始生成增量最终报告（交错并发模式）")

            enabled_targets = await self._get_enabled_targets()

            if not enabled_targets:
                logger.info("没有启用的群聊需要生成最终报告")
                return

            target_list = list(enabled_targets)
            stagger = self.config_manager.get_incremental_stagger_seconds()
            max_concurrent = self.config_manager.get_max_concurrent_tasks()

            logger.info(
                f"将为 {len(target_list)} 个群聊生成增量最终报告 "
                f"(并发限制: {max_concurrent}, 交错间隔: {stagger}秒)"
            )

            sem = asyncio.Semaphore(max_concurrent)

            async def staggered_final_report(idx, gid, pid):
                async with sem:
                    if idx > 0 and stagger > 0:
                        await asyncio.sleep(stagger * idx)
                    return await self._perform_incremental_final_report_for_group_with_timeout(
                        gid, pid
                    )

            report_tasks = []
            for idx, (gid, pid) in enumerate(target_list):
                task = asyncio.create_task(
                    staggered_final_report(idx, gid, pid),
                    name=f"final_report_group_{gid}",
                )
                report_tasks.append(task)

            # 并发执行所有最终报告任务
            results = await asyncio.gather(*report_tasks, return_exceptions=True)

            # 统计执行结果
            success_count = 0
            skip_count = 0
            error_count = 0

            for i, result in enumerate(results):
                gid, _ = target_list[i]
                if isinstance(result, Exception):
                    logger.error(f"群 {gid} 最终报告任务异常: {result}")
                    error_count += 1
                elif isinstance(result, dict) and not result.get("success", True):
                    skip_count += 1
                else:
                    success_count += 1

            logger.info(
                f"增量最终报告完成 - 成功: {success_count}, 跳过: {skip_count}, "
                f"失败: {error_count}, 总计: {len(target_list)}"
            )

        except Exception as e:
            logger.error(f"增量最终报告执行失败: {e}", exc_info=True)

    async def _perform_incremental_final_report_for_group_with_timeout(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群生成增量最终报告（带超时控制，20分钟）"""
        try:
            result = await asyncio.wait_for(
                self._perform_incremental_final_report_for_group(
                    group_id, target_platform_id
                ),
                timeout=1200,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 最终报告超时（20分钟），跳过")
            return {"success": False, "reason": "timeout"}
        except Exception as e:
            logger.error(f"群 {group_id} 最终报告任务执行失败: {e}")
            return {"success": False, "reason": str(e)}

    async def _perform_incremental_final_report_for_group(
        self, group_id: str, target_platform_id: str = None
    ):
        """为指定群生成增量最终报告（业务逻辑委派给 AnalysisApplicationService）"""
        # 为每个群聊使用独立的锁
        group_lock_key = f"final_report_{group_id}"
        if not hasattr(self, "_group_locks"):
            self._group_locks = weakref.WeakValueDictionary()

        lock = self._group_locks.get(group_lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._group_locks[group_lock_key] = lock

        async with lock:
            try:
                # 设置 TraceID
                trace_id = TraceContext.generate(prefix=f"report_{group_id}")
                TraceContext.set(trace_id)

                logger.info(
                    f"开始为群 {group_id} 生成增量最终报告 "
                    f"(Platform: {target_platform_id or 'Auto'})"
                )

                # 检查平台状态
                if not self.bot_manager.is_ready_for_auto_analysis():
                    logger.warning(f"群 {group_id} 最终报告跳过：bot管理器未就绪")
                    return {"success": False, "reason": "bot_not_ready"}

                # 委派给应用层服务执行最终报告用例
                result = await self.analysis_service.execute_incremental_final_report(
                    group_id=group_id, platform_id=target_platform_id
                )

                if not result.get("success"):
                    reason = result.get("reason", "unknown")
                    logger.info(f"群 {group_id} 最终报告跳过: {reason}")
                    return result

                # 获取分析结果及适配器，分发报告
                analysis_result = result["analysis_result"]
                adapter = result["adapter"]

                await self.report_dispatcher.dispatch(
                    group_id,
                    analysis_result,
                    adapter.platform_id
                    if hasattr(adapter, "platform_id")
                    else target_platform_id,
                )

                # 清理过期批次（保留 2 倍窗口范围的数据作为缓冲）
                try:
                    analysis_days = self.config_manager.get_analysis_days()
                    before_ts = time_mod.time() - (analysis_days * 2 * 24 * 3600)
                    incremental_store = self.analysis_service.incremental_store
                    if incremental_store:
                        cleaned = await incremental_store.cleanup_old_batches(
                            group_id, before_ts
                        )
                        if cleaned > 0:
                            logger.info(
                                f"群 {group_id} 报告发送后清理了 {cleaned} 个过期批次"
                            )
                except Exception as cleanup_err:
                    logger.warning(
                        f"群 {group_id} 过期批次清理失败（不影响报告）: {cleanup_err}"
                    )

                logger.info(f"群 {group_id} 增量最终报告发送成功")
                return result

            except Exception as e:
                logger.error(f"群 {group_id} 最终报告执行失败: {e}", exc_info=True)
                return {"success": False, "reason": str(e)}
            finally:
                logger.debug(f"群 {group_id} 最终报告流程结束")

    # ================================================================
    # 群列表获取（基础设施层）
    # ================================================================

    async def _get_all_groups(self) -> list[tuple[str, str]]:
        """
        获取所有bot实例所在的群列表（使用 PlatformAdapter）

        Returns:
            list[tuple[str, str]]: [(platform_id, group_id), ...]
        """
        all_groups = set()

        # 强制刷新一次 Bot 实例，确保最新的 Bot 被发现
        if hasattr(self.bot_manager, "auto_discover_bot_instances"):
            try:
                await self.bot_manager.auto_discover_bot_instances()
            except Exception as e:
                logger.warning(f"[AutoScheduler] 自动发现失败: {e}")

        bot_ids = list(self.bot_manager._bot_instances.keys())
        adapter_ids = list(self.bot_manager._adapters.keys())

        # 调试模式下记录详细信息，INFO级别仅显示概览
        logger.debug(f"[AutoScheduler] Bot实例: {bot_ids}, 适配器: {adapter_ids}")

        if not bot_ids:
            logger.warning("[AutoScheduler] 自动发现后未找到任何Bot实例")
            return []

        for platform_id, bot_instance in self.bot_manager._bot_instances.items():
            # 检查该平台是否启用了此插件
            if not self.bot_manager.is_plugin_enabled(
                platform_id, "astrbot_plugin_qq_group_daily_analysis"
            ):
                logger.debug(f"平台 {platform_id} 未启用此插件，跳过获取群列表")
                continue

            try:
                # 1. 优先从 BotManager 获取已创建的适配器
                adapter = self.bot_manager.get_adapter(platform_id)

                # 2. 如果没有，尝试临时创建（降级方案）
                platform_name = None
                if not adapter:
                    platform_name = self.bot_manager._detect_platform_name(bot_instance)
                    if platform_name:
                        adapter = PlatformAdapterFactory.create(
                            platform_name,
                            bot_instance,
                            config={
                                "bot_self_ids": self.config_manager.get_bot_self_ids(),
                                "platform_id": str(platform_id),
                            },
                        )

                # 3. 使用适配器获取群列表
                if adapter:
                    try:
                        groups = await adapter.get_group_list()
                        groups = [
                            str(group_id).strip()
                            for group_id in groups
                            if str(group_id).strip()
                        ]

                        # 获取平台名称（用于 Telegram 回退判定）
                        p_name = None
                        if hasattr(adapter, "get_platform_name"):
                            try:
                                p_name = adapter.get_platform_name()
                            except Exception:
                                p_name = None
                        if not p_name:
                            p_name = (
                                self.bot_manager._detect_platform_name(bot_instance)
                                or "unknown"
                            )
                        p_name = str(p_name).strip()

                        used_tg_kv_fallback = False
                        if not groups and p_name.lower() == "telegram":
                            groups = await self._get_telegram_groups_from_plugin_kv(
                                str(platform_id)
                            )
                            used_tg_kv_fallback = bool(groups)

                        for group_id in groups:
                            all_groups.add((platform_id, str(group_id)))

                        logger.info(
                            f"平台 {platform_id} ({p_name}) 成功获取 {len(groups)} 个群组"
                            + (" (KV回退)" if used_tg_kv_fallback else "")
                        )
                        continue

                    except Exception as e:
                        logger.warning(f"适配器 {platform_id} 获取群列表失败: {e}")

                # 4. 降级：无法通过适配器获取
                logger.debug(f"平台 {platform_id} 无法通过适配器获取群列表")

            except Exception as e:
                logger.error(f"平台 {platform_id} 获取群列表异常: {e}")

        return list(all_groups)

    async def _get_telegram_groups_from_plugin_kv(self, platform_id: str) -> list[str]:
        """从插件 KV 获取 Telegram 已见群/话题，作为 get_group_list 的回退。"""
        if not self.plugin_instance:
            return []

        getter = getattr(self.plugin_instance, "get_telegram_seen_group_ids", None)
        if not callable(getter):
            return []

        try:
            groups = await getter(platform_id=platform_id)
            return sorted(
                {str(group_id).strip() for group_id in groups if str(group_id).strip()}
            )
        except Exception as e:
            logger.warning(
                "[TGRegistry] Scheduler fetch failed: "
                f"platform_id={platform_id} error={e}"
            )
            return []
