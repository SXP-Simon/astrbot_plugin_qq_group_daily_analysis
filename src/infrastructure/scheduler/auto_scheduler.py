"""
自动调度器模块
负责定时任务和自动分析功能，支持传统单次分析与增量多次分析两种调度模式。
"""

import asyncio
import time as time_mod
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ...application.services.analysis_application_service import DuplicateGroupTaskError
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
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

        # Cache: group_id -> group_name (populated lazily)
        self._group_name_cache: dict[str, str] = {}
        self._terminating = False  # 终止标志位

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

    async def _get_group_name_safe(
        self, group_id: str, platform_id: str | None = None
    ) -> str:
        """
        为 TraceID 生成解析可读的群名。
        使用内存缓存以避免重复的 API 调用。
        若名称不可用，则回退到 group_id。
        """
        if group_id in self._group_name_cache:
            return self._group_name_cache[group_id]

        try:
            pid = platform_id or await self.get_platform_id_for_group(group_id)
            if pid:
                adapter = self.bot_manager.get_adapter(pid)
                if adapter:
                    info = await adapter.get_group_info(group_id)
                    if info and info.group_name:
                        self._group_name_cache[group_id] = info.group_name
                        return info.group_name
        except Exception:
            pass

        return group_id

    # ================================================================
    # 任务注册与取消
    # ================================================================

    def schedule_jobs(self, context):
        """根据分层名单配置注册定时任务。"""
        # 首先清理之前的任务
        self.unschedule_jobs(context)

        # unschedule_jobs 会将 _terminating 设为 True (用于关闭场景),
        # 但 schedule_jobs 意味着插件仍在运行；因此需要重置此标志位
        self._terminating = False

        if not self.config_manager.is_auto_analysis_enabled():
            logger.info("定时分析名单为空且为白名单模式，不注册定时任务。")
            return

        scheduler = context.cron_manager.scheduler

        # 1. 注册核心报告生成任务（涵盖全量分析与增量总结报告）
        # 每个配置的时间点都会触发一次解析
        logger.info("注册定时分析报告任务...")
        self._schedule_report_time_jobs(scheduler)

        # 2. 只有在增量功能总开关开启时，才注册全天候的增量提取任务
        if self.config_manager.get_incremental_enabled():
            logger.info("增量分析功能已开启，正在注册全天增量提取任务...")
            self._schedule_incremental_cron_jobs(scheduler)
        else:
            logger.info("增量分析总开关未启用，仅执行传统定时全量分析。")

    def _schedule_report_time_jobs(self, scheduler):
        """在配置的时间点注册报告生成任务。

        这些任务根据运行时解析出的生效模式，决定执行传统的全量分析还是增量汇报。
        """
        time_config = self.config_manager.get_auto_analysis_time()
        if isinstance(time_config, str):
            time_config = [time_config]

        for i, t_str in enumerate(time_config):
            try:
                t_str = str(t_str).replace("：", ":").strip()
                hour, minute = t_str.split(":")

                trigger = CronTrigger(hour=int(hour), minute=int(minute))
                job_id = f"astrbot_plugin_qq_group_daily_analysis_trigger_{i}"

                scheduler.add_job(
                    self._run_scheduled_report,
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=60,
                )
                self.scheduler_job_ids.append(job_id)
                logger.info(f"已注册定时报告任务: {t_str} (Job ID: {job_id})")

            except Exception as e:
                logger.error(f"注册定时任务失败 ({t_str}): {e}")

    def _schedule_incremental_cron_jobs(self, scheduler):
        """
        在活跃时段注册增量分析定时任务。

        这类任务仅执行增量数据的提取；而报告生成阶段在配置的每日分析时间点进行。
        """
        active_start_hour = self.config_manager.get_incremental_active_start_hour()
        active_end_hour = self.config_manager.get_incremental_active_end_hour()
        interval_minutes = self.config_manager.get_incremental_interval_minutes()
        max_daily = self.config_manager.get_incremental_max_daily_analyses()

        # 计算活跃时段内的触发时间点
        trigger_times = []
        current_minutes = active_start_hour * 60
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

        logger.info(f"增量调度注册完成: {len(trigger_times)} 个增量分析任务")

    def unschedule_jobs(self, context):
        """取消定时任务"""
        self._terminating = True
        if (
            not context
            or not hasattr(context, "cron_manager")
            or not context.cron_manager
        ):
            return

        scheduler = context.cron_manager.scheduler
        if not scheduler:
            return

        for job_id in self.scheduler_job_ids:
            try:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                    logger.debug(f"已移除定时任务: {job_id}")
            except Exception as e:
                logger.warning(f"移除定时任务失败 ({job_id}): {e}")
        self.scheduler_job_ids.clear()

    # ================================================================
    # 共享辅助方法：解析定时分析目标
    # ================================================================

    async def _get_scheduled_targets(
        self, mode_filter: str | None = None
    ) -> list[tuple[str, str, str]]:
        """
        根据分层过滤逻辑判定所有应参与计划分析的目标群组及其分析策略。

        判定过程：
        1. 准入层：群组必须在基础设置的允许名单内。
        2. 定时层：群组需通过定时分析名单的过滤。
        3. 模式层：如果群组在增量名单内，则使用增量模式，否则使用默认策略。

        参数：
            mode_filter: 如果提供，则只返回匹配指定模式的目标 (traditional 或 incremental)。
        """
        # 获取基础信息
        all_groups = await self._get_all_groups()

        # 预加载所有配置名单和模式
        sched_list = self.config_manager.get_scheduled_group_list()
        sched_list_mode = self.config_manager.get_scheduled_group_list_mode()

        incr_list = self.config_manager.get_incremental_group_list()
        incr_list_mode = self.config_manager.get_incremental_group_list_mode()

        result = []

        # 遍历所有平台上的群组
        for platform_id, group_id_orig in all_groups:
            group_id = str(group_id_orig)
            umo = f"{platform_id}:GroupMessage:{group_id}"

            # 1. 准入层判定 (基础黑白名单)
            if not self.config_manager.is_group_allowed(umo):
                continue

            # 2. 定时层判定 (定时分析黑白名单)
            if not self.config_manager.is_group_in_filtered_list(
                umo, sched_list_mode, sched_list
            ):
                continue

            # 3. 模式层判定 (增量黑白名单)
            # 3. 模式层判定 (增量黑白名单)
            if self.config_manager.is_group_in_filtered_list(
                umo, incr_list_mode, incr_list
            ):
                # 如果在增量名单内，则执行增量模式
                effective_mode = "incremental"
            else:
                # 不在增量名单内，则执行普通模式
                effective_mode = "traditional"

            # 4. 模式过滤 (如果函数调用者要求过滤)
            if mode_filter and effective_mode != mode_filter:
                continue

            result.append((group_id, platform_id, effective_mode))

        logger.info(
            f"分层调度解析完成：符合条件的群组共 {len(result)} 个"
            + (f" (模式过滤: {mode_filter})" if mode_filter else "")
        )
        return result

    # ================================================================
    # 统一报告调度入口
    # ================================================================

    async def _run_scheduled_report(self):
        """统一的定时分析入口。

        在配置的时间点触发，解析所有目标群并根据其分析模式分发任务：
        - traditional: 执行全量拉取分析并发送报告
        - incremental: 执行增量最终报告阶段（合并并汇报）
        """
        if self._terminating:
            return
        try:
            logger.info("定时报告触发 — 开始解析调度目标")

            all_targets = await self._get_scheduled_targets()

            if not all_targets:
                logger.info("没有配置的群聊需要定时分析")
                return

            max_concurrent = self.config_manager.get_max_concurrent_tasks()
            sem = asyncio.Semaphore(max_concurrent)
            logger.info(
                f"定时报告: {len(all_targets)} 个目标 (并发限制: {max_concurrent})"
            )

            async def dispatch_group(gid, pid, mode):
                async with sem:
                    if mode == "incremental":
                        return await self._perform_incremental_final_report_for_group_with_timeout(
                            gid, pid
                        )
                    else:
                        return await self._perform_auto_analysis_for_group_with_timeout(
                            gid, pid
                        )

            tasks = []
            stagger = self.config_manager.get_stagger_seconds() or 2
            # 针对定时大任务加入交错等待，减少瞬间峰值延迟
            for idx, (gid, pid, mode) in enumerate(all_targets):
                if self._terminating:
                    logger.info("检测到插件正在停止，取消后续任务创建")
                    break

                # 为前几个任务添加微小的启动间隔，均匀分散 API 压力
                if idx > 0 and stagger > 0:
                    await asyncio.sleep(stagger)

                task = asyncio.create_task(
                    dispatch_group(gid, pid, mode),
                    name=f"report_{mode}_{gid}",
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计结果
            success_count = 0
            skip_count = 0
            error_count = 0

            for i, result in enumerate(results):
                gid, _, _ = all_targets[i]
                if isinstance(result, DuplicateGroupTaskError):
                    skip_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"群 {gid} 定时报告任务异常: {result}")
                    error_count += 1
                elif isinstance(result, dict) and not result.get("success", True):
                    skip_count += 1
                else:
                    success_count += 1

            logger.info(
                f"定时报告完成 — 成功: {success_count}, 跳过: {skip_count}, "
                f"失败: {error_count}, 总计: {len(all_targets)}"
            )

        except Exception as e:
            logger.error(f"定时报告执行失败: {e}", exc_info=True)

    async def _perform_auto_analysis_for_group_with_timeout(
        self, group_id: str, target_platform_id: str | None = None
    ):
        """为指定群执行自动分析（带超时控制）"""
        try:
            # 为每个群聊设置独立的超时时间，适当放宽到 30 分钟以支持大型批次
            await asyncio.wait_for(
                self._perform_auto_analysis_for_group(group_id, target_platform_id),
                timeout=1800,
            )
        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 分析超时（30分钟），跳过该群分析")
        except Exception as e:
            logger.error(f"群 {group_id} 分析任务执行失败: {e}")

    async def _perform_auto_analysis_for_group(
        self, group_id: str, target_platform_id: str | None = None
    ):
        """为指定群执行自动分析（业务逻辑委派给 AnalysisApplicationService）"""
        try:
            # 解析可读群名以生成语义化的 TraceID
            group_name = await self._get_group_name_safe(group_id, target_platform_id)
            trace_id = TraceContext.generate(prefix="group", group_name=group_name)
            TraceContext.set(trace_id)

            if self._terminating:
                return

            logger.info(
                f"开始为群 {group_id} 执行自动分析 (Platform: {target_platform_id or 'Auto'})"
            )

            # 检查平台状态 (BotManager 为基础设施层，用于获取平台就绪状态)
            if not self.bot_manager.is_ready_for_auto_analysis():
                logger.warning(f"群 {group_id} 自动分析跳过：bot管理器未就绪")
                return

            # 委派给应用层服务执行核心用例
            # AnalysisApplicationService 内部已处理群锁 (group_lock)
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

            # 调度导出并发送报告
            await self.report_dispatcher.dispatch(
                group_id,
                analysis_result,
                adapter.platform_id
                if hasattr(adapter, "platform_id")
                else target_platform_id,
            )

            logger.info(f"群 {group_id} 自动分析任务执行成功")

        except DuplicateGroupTaskError:
            # group_lock 抛出的 DuplicateGroupTaskError 表示任务正在运行，优雅跳过
            logger.debug(f"群 {group_id} 任务因并发锁冲突而跳过（已在运行）")
            raise  # 重新抛出，让上层知道任务并没真正执行而是跳过了
        except Exception as e:
            logger.error(f"群 {group_id} 自动分析执行失败: {e}", exc_info=True)
        finally:
            logger.debug(f"群 {group_id} 自动分析流程结束")

    # ================================================================
    # 增量模式：增量分析
    # ================================================================

    async def _run_incremental_analysis(self):
        """为所有目标模式设定为 incremental 的群执行增量分析任务。"""
        if self._terminating:
            return
        try:
            logger.info("开始执行自动增量分析（并发模式）")

            # 仅选取模式为 incremental 的目标群
            incr_targets = await self._get_scheduled_targets(mode_filter="incremental")

            if not incr_targets:
                logger.info("没有配置为增量模式的群聊需要增量分析")
                return

            target_list = incr_targets
            stagger = self.config_manager.get_incremental_stagger_seconds()
            max_concurrent = self.config_manager.get_max_concurrent_tasks()

            logger.info(
                f"将为 {len(target_list)} 个群聊执行增量分析 "
                f"(并发限制: {max_concurrent}, 交错间隔: {stagger}秒)"
            )

            sem = asyncio.Semaphore(max_concurrent)

            async def staggered_incremental(idx, gid, pid):
                if idx > 0 and stagger > 0:
                    await asyncio.sleep(stagger * idx)

                async with sem:
                    result = (
                        await self._perform_incremental_analysis_for_group_with_timeout(
                            gid, pid
                        )
                    )

                    # 为调试提供的立即上报选项
                    if self.config_manager.get_incremental_report_immediately():
                        if isinstance(result, dict) and result.get("success"):
                            logger.info(
                                f"增量分析立即报告模式生效，正在为群 {gid} 生成报告..."
                            )
                            await self._perform_incremental_final_report_for_group_with_timeout(
                                gid, pid
                            )

                    return result

            analysis_tasks = []
            for idx, (gid, pid, _mode) in enumerate(target_list):
                if self._terminating:
                    logger.info("检测到插件正在停止，取消后续增量分析任务创建")
                    break
                task = asyncio.create_task(
                    staggered_incremental(idx, gid, pid),
                    name=f"incremental_group_{gid}",
                )
                analysis_tasks.append(task)

            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            success_count = 0
            skip_count = 0
            error_count = 0

            for i, result in enumerate(results):
                gid, _, _ = target_list[i]
                if isinstance(result, DuplicateGroupTaskError):
                    skip_count += 1
                elif isinstance(result, Exception):
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
        self, group_id: str, target_platform_id: str | None = None
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
        self, group_id: str, target_platform_id: str | None = None
    ):
        """为指定群执行增量分析（业务逻辑委派给 AnalysisApplicationService）"""
        try:
            # 解析可读群名以生成语义化的 TraceID
            group_name = await self._get_group_name_safe(group_id, target_platform_id)
            trace_id = TraceContext.generate(prefix="incr", group_name=group_name)
            TraceContext.set(trace_id)

            if self._terminating:
                return

            logger.info(
                f"开始为群 {group_id} 执行增量分析 "
                f"(Platform: {target_platform_id or 'Auto'})"
            )

            # 检查平台状态
            if not self.bot_manager.is_ready_for_auto_analysis():
                logger.warning(f"群 {group_id} 增量分析跳过：bot管理器未就绪")
                return {"success": False, "reason": "bot_not_ready"}

            # 委派给应用层服务执行增量分析用例
            # AnalysisApplicationService 内部已处理群锁 (group_lock)
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

        except DuplicateGroupTaskError:
            # group_lock 抛出的 DuplicateGroupTaskError 表示任务正在运行，优雅跳过
            logger.debug(f"群 {group_id} 增量分析因并发锁冲突而跳过（已在运行）")
            return {"success": False, "reason": "already_running"}
        except Exception as e:
            logger.error(f"群 {group_id} 增量分析执行失败: {e}", exc_info=True)
            return {"success": False, "reason": str(e)}
        finally:
            logger.debug(f"群 {group_id} 增量分析流程结束")

    # ================================================================
    # 增量最终报告（单群）与回退逻辑
    # ================================================================

    async def _perform_incremental_final_report_for_group_with_timeout(
        self, group_id: str, target_platform_id: str | None = None
    ):
        """带超时及回退机制的增量最终报告生成。

        若增量汇报失败（非 '消息不足' 或 '正在运行' 导致的），
        且启用了自动回退，则将该群转由传统模式执行全量分析。
        """
        try:
            result = await asyncio.wait_for(
                self._perform_incremental_final_report_for_group(
                    group_id, target_platform_id
                ),
                timeout=1800,
            )

            # 判定是否需要触发回退 (例如：无增量数据等)
            if isinstance(result, dict) and not result.get("success"):
                reason = result.get("reason", "")
                if reason in ("below_threshold", "already_running"):
                    return result  # 正常跳过，无需回退
                if self.config_manager.get_incremental_fallback_enabled():
                    logger.warning(
                        f"群 {group_id} 增量最终报告失败 (reason={reason})，"
                        f"正在回退到传统全量分析..."
                    )
                    return await self._fallback_to_traditional(
                        group_id, target_platform_id
                    )

            return result

        except asyncio.TimeoutError:
            logger.error(f"群 {group_id} 最终报告超时（30分钟）")
            if self.config_manager.get_incremental_fallback_enabled():
                logger.warning(f"群 {group_id} 增量报告超时，正在回退到传统全量分析...")
                return await self._fallback_to_traditional(group_id, target_platform_id)
            return {"success": False, "reason": "timeout"}

        except Exception as e:
            logger.error(f"群 {group_id} 最终报告任务执行失败: {e}")
            if self.config_manager.get_incremental_fallback_enabled():
                logger.warning(f"群 {group_id} 增量报告异常，正在回退到传统全量分析...")
                return await self._fallback_to_traditional(group_id, target_platform_id)
            return {"success": False, "reason": str(e)}

    async def _fallback_to_traditional(
        self, group_id: str, target_platform_id: str | None = None
    ):
        """回退操作：在增量报告失败时，执行传统的全量拉取分析。"""
        try:
            logger.info(
                f"⬆️ 群 {group_id} 回退到传统全量分析 "
                f"(Platform: {target_platform_id or 'Auto'})"
            )
            await self._perform_auto_analysis_for_group_with_timeout(
                group_id, target_platform_id
            )
            return {"success": True, "fallback": True}
        except Exception as fallback_err:
            logger.error(
                f"群 {group_id} 回退传统分析也失败: {fallback_err}",
                exc_info=True,
            )
            return {"success": False, "reason": f"fallback_failed: {fallback_err}"}

    async def _perform_incremental_final_report_for_group(
        self, group_id: str, target_platform_id: str | None = None
    ):
        """为指定群生成增量最终报告（业务逻辑委派给 AnalysisApplicationService）"""
        try:
            # 解析可读群名以生成语义化的 TraceID
            group_name = await self._get_group_name_safe(group_id, target_platform_id)
            trace_id = TraceContext.generate(prefix="report", group_name=group_name)
            TraceContext.set(trace_id)

            if self._terminating:
                return

            logger.info(
                f"开始为群 {group_id} 生成增量最终报告 "
                f"(Platform: {target_platform_id or 'Auto'})"
            )

            # 检查平台状态
            if not self.bot_manager.is_ready_for_auto_analysis():
                logger.warning(f"群 {group_id} 最终报告跳过：bot管理器未就绪")
                return {"success": False, "reason": "bot_not_ready"}

            # 委派给应用层服务执行最终报告用例
            # AnalysisApplicationService 内部已处理群锁 (group_lock)
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

        except DuplicateGroupTaskError:
            # group_lock 抛出的 DuplicateGroupTaskError 表示任务正在运行，优雅跳过
            logger.debug(f"群 {group_id} 最终报告因并发锁冲突而跳过（已在运行）")
            return {"success": False, "reason": "already_running"}
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

        # 1. [韧性增强] 进入扫描前，尝试最后一次实时发现机器人
        # 这确保了即使冷启动初始化失败，定时任务触发时仍能刷新状态
        if hasattr(self.bot_manager, "auto_discover_bot_instances"):
            try:
                await self.bot_manager.auto_discover_bot_instances()
            except Exception as e:
                logger.warning(f"[AutoScheduler] 周期性扫描中的平台发现失败: {e}")

        bot_ids = list(self.bot_manager._bot_instances.keys())

        if not bot_ids:
            logger.warning(
                "[AutoScheduler] 分析周期开启，但全局未发现任何在线 Bot。任务将跳过。"
            )
            return []

        logger.info(f"[AutoScheduler] 正在扫描 {len(bot_ids)} 个平台的群聊资源...")

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

                        # 获取平台名称（仅用于日志）
                        p_name = None
                        if hasattr(adapter, "get_platform_name"):
                            try:
                                p_name = adapter.get_platform_name()
                            except Exception:
                                p_name = None

                        for group_id in groups:
                            all_groups.add((platform_id, str(group_id)))

                        logger.info(
                            f"平台 {platform_id} ({p_name or 'unknown'}) 成功获取 {len(groups)} 个群组"
                        )
                        continue

                    except Exception as e:
                        logger.warning(f"适配器 {platform_id} 获取群列表失败: {e}")

                # 4. 降级：无法通过适配器获取
                logger.debug(f"平台 {platform_id} 无法通过适配器获取群列表")

            except Exception as e:
                logger.error(f"平台 {platform_id} 获取群列表异常: {e}")

        return list(all_groups)
