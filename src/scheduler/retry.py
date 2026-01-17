import asyncio
import random
import time
from dataclasses import dataclass
from collections.abc import Callable

from astrbot.api import logger


@dataclass
class RetryTask:
    """重试任务数据类"""

    html_content: str
    group_id: str
    platform_id: str  # 需要保存 platform_id 以便找回 Bot
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class RetryManager:
    """
    重试管理器

    实现了一个简单的延迟队列 + 死信队列机制：
    1. 任务加入队列
    2. Worker 取出任务，尝试执行
    3. 失败则指数退避（延迟）后放回队列
    4. 超过最大重试次数放入死信队列
    """

    def __init__(self, bot_manager, html_render_func: Callable):
        self.bot_manager = bot_manager
        self.html_render_func = html_render_func
        self.queue = asyncio.Queue()
        self.running = False
        self.worker_task = None
        self._dlq = []  # 死信队列 (Failures)

    async def start(self):
        """启动重试工作进程"""
        if self.running:
            return
        self.running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("[RetryManager] 图片重试管理器已启动")

    async def stop(self):
        """停止重试工作进程"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        # 检查剩余任务
        pending_count = self.queue.qsize()
        if pending_count > 0:
            logger.warning(
                f"[RetryManager] 停止时仍有 {pending_count} 个任务在队列中 pending"
            )

        logger.info("[RetryManager] 图片重试管理器已停止")

    async def add_task(self, html_content: str, group_id: str, platform_id: str):
        """添加重试任务"""
        if not self.running:
            logger.warning(
                "[RetryManager] 警告：添加任务时管理器未运行，正在尝试启动..."
            )
            await self.start()

        task = RetryTask(
            html_content=html_content,
            group_id=group_id,
            platform_id=platform_id,
            created_at=time.time(),
        )
        await self.queue.put(task)
        logger.info(f"[RetryManager] 已添加群 {group_id} 的重试任务")

    async def _worker(self):
        """工作进程循环"""
        while self.running:
            try:
                task: RetryTask = await self.queue.get()

                # 延迟策略：指数回退 (5s, 10s, 20s...) + 随机波动 (1~5s)
                jitter = random.uniform(1, 5)
                delay = 5 * (2**task.retry_count) + jitter

                logger.info(
                    f"[RetryManager] 处理群 {task.group_id} 的重试任务 (第 {task.retry_count + 1} 次尝试)"
                )

                success = await self._process_task(task)

                if success:
                    logger.info(f"[RetryManager] 群 {task.group_id} 重试成功")
                    self.queue.task_done()
                else:
                    task.retry_count += 1
                    if task.retry_count < task.max_retries:
                        logger.warning(
                            f"[RetryManager] 群 {task.group_id} 重试失败，{delay}秒后再次尝试"
                        )
                        asyncio.create_task(self._requeue_after_delay(task, delay))
                        self.queue.task_done()
                    else:
                        logger.error(
                            f"[RetryManager] 群 {task.group_id} 超过最大重试次数，移入死信队列"
                        )
                        self._dlq.append(task)
                        self.queue.task_done()
                        await self._notify_failure(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RetryManager] Worker 异常: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _requeue_after_delay(self, task: RetryTask, delay: float):
        await asyncio.sleep(delay)
        await self.queue.put(task)

    async def _process_task(self, task: RetryTask) -> bool:
        """执行具体的渲染和发送逻辑"""
        try:
            # 1. 尝试渲染
            image_options = {
                "full_page": True,
                "type": "jpeg",
                "quality": 85,
            }
            logger.debug(f"[RetryManager] 正在重新渲染群 {task.group_id} 的图片...")
            image_url = await self.html_render_func(
                task.html_content,
                {},
                True,  # 返回 URL
                image_options,
            )

            if not image_url:
                logger.warning(
                    f"[RetryManager] 重新渲染失败（返回空 URL）{task.group_id}"
                )
                return False

            # 2. 获取 Bot 实例
            bot = self.bot_manager.get_bot_instance(task.platform_id)
            if not bot:
                logger.error(
                    f"[RetryManager] 平台 {task.platform_id} 的 Bot 实例未找到，无法重试"
                )
                return False  # 无法重试，因为 Bot 已离线

            # 3. 发送图片
            logger.info(f"[RetryManager] 正在向群 {task.group_id} 发送重试图片...")

            # 使用 OneBot v11 标准 API
            if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                try:
                    # 构造消息
                    # 使用 list 格式兼容性更好
                    message = [
                        {
                            "type": "text",
                            "data": {"text": "📊 每日群聊分析报告（重试发送）：\n"},
                        },
                        {"type": "image", "data": {"file": image_url}},
                    ]

                    result = await bot.api.call_action(
                        "send_group_msg", group_id=int(task.group_id), message=message
                    )

                    # 检查 retcode
                    if isinstance(result, dict):
                        retcode = result.get("retcode", 0)
                        if retcode == 0:
                            return True
                        elif retcode == 1200:
                            logger.warning(
                                f"[RetryManager] 发送失败 (retcode=1200): 可能是Bot被禁言或不在群内，稍后重试"
                            )
                            return False
                        else:
                            logger.warning(
                                f"[RetryManager] 发送失败 (retcode={retcode}): {result}"
                            )
                            return False
                    return (
                        True  # 假设非 dict 类型返回即成功（某些适配器可能返回不同类型）
                    )

                except Exception as e:
                    logger.error(f"[RetryManager] 发送API调用异常: {e}")
                    return False

            elif hasattr(bot, "send_msg"):  # 尝试 AstrBot 抽象接口
                try:
                    # 尝试直接发送
                    await bot.send_msg(image_url, group_id=task.group_id)
                    return True
                except Exception as e:
                    logger.error(f"[RetryManager] 抽象接口发送失败: {e}")
                    return False

            else:
                logger.warning(
                    f"[RetryManager] 未知的 Bot 类型 {type(bot)}，无法发送消息。"
                )
                return False

        except Exception as e:
            logger.error(f"[RetryManager] 处理任务时发生意外错误: {e}", exc_info=True)
            return False

    async def _notify_failure(self, task: RetryTask):
        """通知最终失败"""
        try:
            bot = self.bot_manager.get_bot_instance(task.platform_id)
            if bot and hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                await bot.api.call_action(
                    "send_group_msg",
                    group_id=int(task.group_id),
                    message=f"[AstrBot QQ群日常分析总结插件] 报告生成/发送多次失败 (Group: {task.group_id})，请检查服务器日志。",
                )
        except Exception:
            pass
