import asyncio
import base64
import random
import time
import aiohttp
from collections.abc import Callable
from dataclasses import dataclass

from ..utils.logger import logger


@dataclass
class RetryTask:
    """重试任务数据类"""

    html_content: str
    analysis_result: dict  # 保存原始分析结果，用于文本回退
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

    def __init__(self, bot_manager, html_render_func: Callable, report_generator=None):
        self.bot_manager = bot_manager
        self.html_render_func = html_render_func
        self.report_generator = report_generator  # 用于生成文本报告
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

    async def add_task(
        self, html_content: str, analysis_result: dict, group_id: str, platform_id: str
    ):
        """添加重试任务"""
        if not self.running:
            logger.warning(
                "[RetryManager] 警告：添加任务时管理器未运行，正在尝试启动..."
            )
            await self.start()

        task = RetryTask(
            html_content=html_content,
            analysis_result=analysis_result,
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
                            f"[RetryManager] 群 {task.group_id} 超过最大重试次数，移入死信队列并尝试文本回退"
                        )
                        self._dlq.append(task)
                        self.queue.task_done()
                        # 尝试发送文本回退
                        await self._send_fallback_text(task)

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

            # 修改：return_url=False 获取二进制数据而不是URL
            # 这对于解决 NTQQ "Timeout" 错误至关重要，因为它避免了 QQ 客户端下载本地/内网 URL 的网络问题
            image_data = await self.html_render_func(
                task.html_content,
                {},
                False,  # return_url=False, 获取 bytes
                image_options,
            )

            # Fix: html_render might return URL (str) even if return_url=False in some implementations
            if isinstance(image_data, str) and image_data.startswith(
                ("http://", "https://")
            ):
                logger.warning(
                    f"[RetryManager] html_render 返回了 URL 而不是 bytes，尝试下载: {image_data}"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_data) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                        else:
                            logger.error(
                                f"[RetryManager] 下载重试图片失败: {resp.status}"
                            )
                            image_data = None

            if not image_data:
                logger.warning(
                    f"[RetryManager] 重新渲染失败（返回空数据）{task.group_id}"
                )
                return False

            # 将 bytes 转换为 base64 字符串
            try:
                base64_str = base64.b64encode(image_data).decode("utf-8")
                image_file_str = f"base64://{base64_str}"
                logger.debug(
                    f"[RetryManager] 图片转Base64成功，长度: {len(base64_str)}"
                )
            except Exception as e:
                logger.error(f"[RetryManager] Base64编码失败: {e}")
                return False

            # 2. 获取 Bot 实例
            bot = self.bot_manager.get_bot_instance(task.platform_id)
            if not bot:
                logger.error(
                    f"[RetryManager] 平台 {task.platform_id} 的 Bot 实例未找到，无法重试"
                )
                return False  # 无法重试，因为 Bot 已离线

            # 3. 发送图片
            logger.info(
                f"[RetryManager] 正在向群 {task.group_id} 发送重试图片 (Base64模式)..."
            )

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
                        {"type": "image", "data": {"file": image_file_str}},
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
                            # 即使是 Base64 也可能超时，但概率小很多
                            logger.warning(
                                "[RetryManager] 发送失败 (retcode=1200): 消息可能过大或Bot连接不稳定"
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
                    await bot.send_msg(image_file_str, group_id=task.group_id)
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

        except Exception:
            pass

    async def _send_fallback_text(self, task: RetryTask):
        """发送文本回退报告（使用合并转发）"""
        if not self.report_generator:
            logger.warning("[RetryManager] 未配置 ReportGenerator，无法发送文本回退")
            return

        try:
            logger.info(f"[RetryManager] 正在为群 {task.group_id} 生成文本回退报告...")
            text_report = self.report_generator.generate_text_report(
                task.analysis_result
            )

            bot = self.bot_manager.get_bot_instance(task.platform_id)
            if not bot:
                return

            # 构造合并转发节点
            # 注意：这里需要构造符合 OneBot v11 标准的节点列表
            # 即使没有 self_id，我们也可以尝试发送

            # 获取 bot self_id (如果能获取到)
            bot_id = "10000"  # fallback id
            if hasattr(bot, "self_id"):
                bot_id = str(bot.self_id)

            nickname = "AstrBot日常分析"

            nodes = [
                {
                    "type": "node",
                    "data": {
                        "name": nickname,
                        "uin": bot_id,
                        "content": "⚠️ 图片报告多次生成失败，为您呈现文本版报告：",
                    },
                },
                {
                    "type": "node",
                    "data": {"name": nickname, "uin": bot_id, "content": text_report},
                },
            ]

            if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                # 尝试发送群合并转发消息
                # 一般使用 send_group_forward_msg 或 send_group_msg (带 nodes)
                try:
                    await bot.api.call_action(
                        "send_group_forward_msg",
                        group_id=int(task.group_id),
                        messages=nodes,
                    )
                    logger.info(
                        f"[RetryManager] 群 {task.group_id} 文本回退报告发送成功 (合并转发)"
                    )
                except Exception as e:
                    logger.warning(
                        f"[RetryManager] 合并转发失败，尝试直接发送文本: {e}"
                    )
                    # 回退到直接发送宽文本
                    await bot.api.call_action(
                        "send_group_msg",
                        group_id=int(task.group_id),
                        message=f"⚠️ 图片报告生成失败，文本报告：\n{text_report}"[
                            :4500
                        ],  # 截断防止过长
                    )

        except Exception as e:
            logger.error(f"[RetryManager] 文本回退发送失败: {e}", exc_info=True)
