import asyncio
import base64
import hashlib
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import aiohttp

from ...shared.trace_context import REPORT_CAPTION_PATTERN
from ...utils.logger import logger


@dataclass
class RetryTask:
    """重试任务数据类"""

    html_content: str
    analysis_result: dict  # 保存原始分析结果，用于文本回退
    group_id: str
    platform_id: str  # 需要保存 platform_id 以便找回 Bot
    caption: str = ""  # 保存原始消息提示词
    retry_count: int = 0
    max_retries: int = 2
    created_at: float = 0.0
    task_key: str = ""

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
        self._active_groups = set()  # 正在处理中的群，防止重试地狱
        self._active_task_keys = set()  # 任务级去重锁，防止同一报告重复入队
        self._recent_task_key_ts: dict[str, float] = {}  # 最近完成任务用于短时去重
        self._dedupe_ttl_seconds = 15 * 60

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
        self._active_groups.clear()
        self._active_task_keys.clear()

        logger.info("[RetryManager] 图片重试管理器已停止")

    async def add_task(
        self,
        html_content: str,
        analysis_result: dict,
        group_id: str,
        platform_id: str,
        caption: str = "",
    ):
        """添加重试任务"""
        if not self.running:
            logger.warning(
                "[RetryManager] 警告：添加任务时管理器未运行，正在尝试启动..."
            )
            await self.start()

        self._cleanup_expired_task_keys()
        task_key = self._build_task_key(group_id, platform_id, caption, html_content)

        # 任务级去重：同一份报告在观察窗口内只保留一个任务
        if task_key in self._active_task_keys:
            logger.debug(f"[RetryManager] 任务 {task_key} 已在重试流程中，跳过重复入队")
            return

        if task_key in self._recent_task_key_ts:
            logger.debug(
                f"[RetryManager] 任务 {task_key} 在去重窗口内已处理过，跳过重复入队"
            )
            return

        task = RetryTask(
            html_content=html_content,
            analysis_result=analysis_result,
            group_id=group_id,
            platform_id=platform_id,
            caption=caption,
            created_at=time.time(),
            task_key=task_key,
        )
        self._active_task_keys.add(task_key)
        self._recent_task_key_ts[task_key] = time.time()
        await self.queue.put(task)
        logger.info(f"[RetryManager] 已添加群 {group_id} 的重试任务 (key={task_key})")

    async def _worker(self):
        """工作进程主循环：仅负责分发任务到协程，不阻塞"""
        while self.running:
            try:
                task: RetryTask = await self.queue.get()

                # 【修复】去掉原本在这里的 group_id in self._active_groups 判断
                # 因为重新排队的任务本身就在 active_groups 中，会导致任务死在队列里被彻底丢弃

                # 启动非阻塞的延迟执行协程
                asyncio.create_task(self._run_task_with_delay(task))
                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RetryManager] Worker 调度异常: {e}")
                await asyncio.sleep(1)

    def _cleanup_expired_task_keys(self):
        """清理过期的去重记录。"""
        now = time.time()
        expired_keys = [
            key
            for key, ts in self._recent_task_key_ts.items()
            if now - ts > self._dedupe_ttl_seconds
        ]
        for key in expired_keys:
            self._recent_task_key_ts.pop(key, None)

    def _build_task_key(
        self, group_id: str, platform_id: str, caption: str, html_content: str
    ) -> str:
        """
        构造用于去重的稳定任务 key。

        优先级：
        1）优先使用 caption 中的 TraceID 时间戳
        2）若无则取 HTML 内容的哈希前缀
        """
        token = None
        if caption:
            match = REPORT_CAPTION_PATTERN.search(caption)
            if match:
                token = match.group(0)

        if not token:
            digest = hashlib.sha1(html_content[:2048].encode("utf-8")).hexdigest()[:16]
            token = f"html:{digest}"

        return f"{platform_id}:{group_id}:{token}"

    def _mark_task_finished(self, task: RetryTask):
        """释放任务级去重锁并刷新冷却时间。"""
        if task.task_key:
            self._active_task_keys.discard(task.task_key)
            self._recent_task_key_ts[task.task_key] = time.time()

    async def _run_task_with_delay(self, task: RetryTask):
        """异步执行带延迟的单体重试任务"""
        # 锁定该群，防止其他“新”重试任务进入。
        # 如果是重试任务（retry_count > 0），它已经在队列循环中，之前已经释放过锁。
        if task.group_id in self._active_groups and task.retry_count == 0:
            # 群正在被其它重试任务占用，重新排队避免任务被静默丢弃
            await asyncio.sleep(5)
            if self.running:
                await self.queue.put(task)
            return
        self._active_groups.add(task.group_id)

        try:
            # 1. 策略计算：指数回落 + 抖动
            jitter = random.uniform(2, 8)
            delay = 20 * (2**task.retry_count) + jitter

            if task.retry_count == 0:
                logger.info(
                    f"[RetryManager] 群 {task.group_id} 启动 {delay:.1f}s 重试观察期..."
                )
            else:
                logger.info(
                    f"[RetryManager] 群 {task.group_id} 准备第 {task.retry_count + 1} 轮重试，退避 {delay:.1f}s..."
                )

            await asyncio.sleep(delay)

            if not self.running:
                return

            # 【真相检查 1】：睡醒后先核实群里图片是不是其实已经出来了
            adapter = self.bot_manager.get_adapter(task.platform_id)
            if adapter and hasattr(adapter, "was_image_sent_recently"):
                # 检查过去 5 分钟内的消息回显 (覆盖初发和之前的重试)
                if await adapter.was_image_sent_recently(
                    task.group_id, seconds=300, token=task.caption
                ):
                    logger.info(
                        f"[RetryManager] [拦截] 根据历史回显，群 {task.group_id} 的图片已成功送达。取消本次重试。"
                    )
                    return

            # 2. 执行渲染与发送
            success = await self._process_task(task)

            if success:
                logger.info(f"[RetryManager] 群 {task.group_id} 重试流程圆满完成")
                self._mark_task_finished(task)
            else:
                # 3. 失败后续处理
                task.retry_count += 1
                if task.retry_count < task.max_retries:
                    # 将任务重新放回队列。
                    # 注意：锁会在 finally 释放，这样下一个 worker 就能拉取到它并进入睡眠。
                    await self.queue.put(task)
                    logger.warning(
                        f"[RetryManager] 群 {task.group_id} 本轮调用返回失败，已排期下一轮..."
                    )
                else:
                    logger.error(
                        f"[RetryManager] 群 {task.group_id} 已达最大重试次数，执行文本回退"
                    )
                    await self._send_fallback_text(task)
                    self._mark_task_finished(task)
        except Exception as e:
            logger.error(f"[RetryManager] 重试协程发生意外: {e}", exc_info=True)
            self._mark_task_finished(task)
        finally:
            # 释放群锁
            if task.group_id in self._active_groups:
                self._active_groups.discard(task.group_id)

    async def _requeue_after_delay(self, task: RetryTask, delay: float):
        # 这是一个遗留辅助方法，新逻辑已在 _run_task_with_delay 中处理
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

            # 修改：return_url=False 获取二进制数据而不是 URL
            # 这可以规避 NTQQ/NT 的“Timeout”假失败，因为下载本地/内网 URL 造成的网络等待会被跳过
            image_data = await self.html_render_func(
                task.html_content,
                {},
                False,  # return_url=False，获取 bytes
                image_options,
            )

            # 修复：某些实现即使 return_url=False 也仍返回 URL 字符串
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
                            if not image_data.startswith(
                                b"\xff\xd8"
                            ) and not image_data.startswith(b"\x89PNG"):
                                if len(image_data) < 1024 and (
                                    b"Error" in image_data or b"Exception" in image_data
                                ):
                                    logger.error(
                                        f"[RetryManager] 渲染器生成了错误文件而非图片: {image_data.decode('utf-8', errors='ignore')}"
                                    )
                                    return False
                        else:
                            logger.error(
                                f"[RetryManager] 渲染器返回的路径不存在: {image_data}"
                            )
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

            # 3. 【临界检查 2】发送图片前最后一次复核 (针对渲染耗时极长产生的盲窗)
            # 例如渲染 10s 期间图片出来了，这里可以最后贴身拦截一次
            if adapter and hasattr(adapter, "was_image_sent_recently"):
                if await adapter.was_image_sent_recently(
                    task.group_id, seconds=120, token=task.caption
                ):
                    logger.info(
                        f"[RetryManager] [临界拦截] 渲染完成后检测到群 {task.group_id} 已有报告。拦截重复发送。"
                    )
                    return True

            # 4. 执行实际发送
            logger.info(
                f"[RetryManager] 正在向群 {task.group_id} 发送回补图片 (Adapter: {type(adapter).__name__})..."
            )

            # 注意：某些适配器可能需要 URL，某些需要 Base64。
            # 适配器内部通常应处理好 bytes/base64 的发送。
            # 这里我们尝试直接传 image_file_str (base64://)
            try:
                success = await adapter.send_image(
                    task.group_id, image_file_str, caption=task.caption
                )
                return success
            except Exception as e:
                logger.error(f"[RetryManager] 适配器发送图片异常: {e}")
                return False

        except Exception as e:
            logger.error(f"[RetryManager] 处理任务时发生意外错误: {e}", exc_info=True)
            return False

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
