import asyncio
import base64
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import aiohttp

from ...utils.logger import logger


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
            if isinstance(image_data, str):
                if image_data.startswith(("http://", "https://")):
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
                else:
                    # 本地文件路径
                    try:
                        import os
                        if os.path.exists(image_data):
                            with open(image_data, "rb") as f:
                                image_data = f.read()
                            
                            # 校验文件头 (防御性编程，避免发送错误文本)
                            if not image_data.startswith(b"\xff\xd8") and not image_data.startswith(b"\x89PNG"):
                                if len(image_data) < 1024 and (b"Error" in image_data or b"Exception" in image_data):
                                    logger.error(f"[RetryManager] 渲染器生成了错误文件而非图片: {image_data.decode('utf-8', errors='ignore')}")
                                    return False
                        else:
                            logger.error(f"[RetryManager] 渲染器返回的路径不存在: {image_data}")
                            image_data = None
                    except Exception as e:
                        logger.error(f"[RetryManager] 读取本地图片失败: {e}")
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

            # 2. 获取适配器 (DDD 基础设施层)
            adapter = self.bot_manager.get_adapter(task.platform_id)
            if not adapter:
                logger.error(
                    f"[RetryManager] 平台 {task.platform_id} 的适配器未找到，无法重试"
                )
                return False

            # 3. 发送图片 (通过统一适配器接口)
            logger.info(
                f"[RetryManager] 正在向群 {task.group_id} 发送重试图片 (Adapter: {type(adapter).__name__})..."
            )

            # 注意：某些适配器可能需要 URL，某些需要 Base64。
            # 适配器内部通常应处理好 bytes/base64 的发送。
            # 这里我们尝试直接传 image_file_str (base64://)
            try:
                success = await adapter.send_image(task.group_id, image_file_str)
                return success
            except Exception as e:
                logger.error(f"[RetryManager] 适配器发送图片异常: {e}")
                return False

        except Exception as e:
            logger.error(f"[RetryManager] 处理任务时发生意外错误: {e}", exc_info=True)
            return False

        except Exception:
            pass

    async def _send_fallback_text(self, task: RetryTask):
        """发送文本回退报告（业务逻辑委派给适配器）"""
        if not self.report_generator:
            logger.warning("[RetryManager] 未配置 ReportGenerator，无法发送文本回退")
            return

        try:
            logger.info(f"[RetryManager] 正在为群 {task.group_id} 生成文本回退报告...")
            text_report = self.report_generator.generate_text_report(
                task.analysis_result
            )

            # 2. 获取适配器 (DDD 基础设施层)
            adapter = self.bot_manager.get_adapter(task.platform_id)
            if not adapter:
                logger.error(
                    f"[RetryManager] 无法获取适配器 {task.platform_id}，放弃发送回退文本"
                )
                return

            nickname = "AstrBot日常分析"
            nodes = [
                {
                    "type": "node",
                    "data": {
                        "name": nickname,
                        "content": "⚠️ 图片报告多次生成失败，为您呈现文本版报告：",
                    },
                },
                {
                    "type": "node",
                    "data": {"name": nickname, "content": text_report},
                },
            ]

            # 3. 通过适配器发送结构化消息
            success = await adapter.send_forward_msg(task.group_id, nodes)

            if success:
                logger.info(f"[RetryManager] 群 {task.group_id} 文本回退报告发送成功")
            else:
                # 最终兜底：发送简单文本
                logger.warning("[RetryManager] 结构化发送失败，尝试直接发送文本回退")
                await adapter.send_text(
                    task.group_id,
                    f"⚠️ 图片报告生成失败，文本报告：\n{text_report}"[:4500],
                )

        except Exception as e:
            logger.error(f"[RetryManager] 文本回退流程异常: {e}", exc_info=True)
