from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Final, Literal, TypedDict

from .logger import logger


class CircuitBreakerSnapshot(TypedDict):
    """熔断器的只读运行快照，不触发恢复尝试。"""

    state: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    failure_count: int
    failure_threshold: int
    recovery_timeout_seconds: int
    retry_after_seconds: float


class CircuitBreakerRejected(Exception):
    """熔断保护拒绝请求；调用方应跳过当前模型，不消耗普通重试等待。"""


@dataclass(frozen=True)
class CircuitRequestPermit:
    """请求所属的熔断轮次和恢复探测资格，防止旧请求干扰新一轮恢复。"""

    generation: int
    is_probe: bool


class CircuitBreaker:
    """
    韧性设计：熔断器 (Circuit Breaker)

    用于监控外部服务（如 LLM API）的调用状态。当连续失败次数达到阈值时，自动开启熔断，
    拦截对故障服务的进一步请求，保护系统不被连锁故障拖累，直到服务窗口恢复。

    States:
        CLOSED: 正常工作状态，允许请求
        OPEN: 熔断状态，拒绝请求
        HALF_OPEN: 尝试恢复状态，仅允许一个恢复探测请求
    """

    STATE_CLOSED: Final = "CLOSED"
    STATE_OPEN: Final = "OPEN"
    STATE_HALF_OPEN: Final = "HALF_OPEN"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default",
    ):
        """
        初始化熔断器。

        Args:
            failure_threshold (int): 连续失败触发熔断的次数上限
            recovery_timeout (int): 熔断开启后尝试恢复之前的冷却时间（秒）
            name (str): 熔断器标识符（用于日志区分）
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.state: Literal["CLOSED", "OPEN", "HALF_OPEN"] = self.STATE_CLOSED
        self.last_failure_time = 0.0
        self._generation = 0

    def snapshot(self) -> CircuitBreakerSnapshot:
        """读取当前状态与剩余冷却时间，不改变熔断器状态。

        Returns:
            读取时的状态、失败计数、阈值和剩余冷却秒数。

        Raises:
            不主动抛出异常。
        """
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
            "retry_after_seconds": max(
                0.0, self.recovery_timeout - (time.monotonic() - self.last_failure_time)
            )
            if self.state == self.STATE_OPEN
            else 0.0,
        }

    def record_failure(self, permit: CircuitRequestPermit | None = None) -> None:
        """记录当前轮次的失败，忽略熔断前已发出请求的迟到结果。

        Args:
            permit: 请求许可；省略时直接记录当前轮次的失败。

        Raises:
            不主动抛出异常。
        """
        if permit is not None and permit.generation != self._generation:
            return
        self.failure_count += 1
        if (
            self.state == self.STATE_CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self._open_circuit()
        elif self.state == self.STATE_HALF_OPEN:
            # 半开状态下任何一次失败都将立即导致熔断重开
            self._open_circuit()

    def record_success(self, permit: CircuitRequestPermit | None = None) -> None:
        """记录当前轮次的成功，恢复探测成功后解除熔断。

        Args:
            permit: 请求许可；省略时直接记录当前轮次的成功。

        Raises:
            不主动抛出异常。
        """
        if permit is not None and permit.generation != self._generation:
            return
        if self.state == self.STATE_HALF_OPEN:
            self._close_circuit()
        elif self.state == self.STATE_CLOSED:
            # 正常状态下的成功重置累积计数值
            self.failure_count = 0

    def check_request(self) -> None:
        """只检查是否可进入请求，不预占恢复探测资格。

        Raises:
            CircuitBreakerRejected: 模型仍在冷却或已有恢复探测请求。
        """
        if self.state == self.STATE_HALF_OPEN:
            raise CircuitBreakerRejected("已有恢复探测请求进行中，跳过当前模型")
        if self.state == self.STATE_OPEN:
            remaining = self.recovery_timeout - (
                time.monotonic() - self.last_failure_time
            )
            if remaining > 0:
                raise CircuitBreakerRejected(
                    f"模型熔断冷却中，剩余约 {remaining:.1f} 秒，跳过当前模型"
                )

    def acquire_request(self) -> CircuitRequestPermit:
        """取得并发槽位后复查状态，并原子取得单次恢复探测资格。

        同一事件循环内检查与状态切换之间没有 await，不会放行多个恢复探测。

        Returns:
            当前请求的许可，完成或取消时必须反馈或释放。

        Raises:
            CircuitBreakerRejected: 模型仍在冷却或已有恢复探测请求。
        """
        self.check_request()
        is_probe = self.state == self.STATE_OPEN
        if is_probe:
            self._half_open_circuit()
        return CircuitRequestPermit(self._generation, is_probe)

    def release_request(self, permit: CircuitRequestPermit) -> None:
        """取消或不计数异常时释放恢复资格，供下一次真实请求继续探测。

        Args:
            permit: 本次请求持有的许可；过期许可不会影响新请求。

        Raises:
            不主动抛出异常。
        """
        if (
            permit.is_probe
            and permit.generation == self._generation
            and self.state == self.STATE_HALF_OPEN
        ):
            # 保留已经到期的冷却时间，不计失败，也不将未完成探测误报为恢复。
            self.state = self.STATE_OPEN
            self._generation += 1

    def _open_circuit(self) -> None:
        """动作：开启熔断"""
        self._generation += 1
        self.state = self.STATE_OPEN
        self.last_failure_time = time.monotonic()
        logger.warning(
            f"熔断器 CircuitBreaker[{self.name}] 已激活！将拦截请求 {self.recovery_timeout} 秒。"
        )

    def _close_circuit(self) -> None:
        """动作：关闭熔断，恢复常态"""
        self._generation += 1
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        logger.info(f"熔断器 CircuitBreaker[{self.name}] 已恢复至关闭 (CLOSED) 状态。")

    def _half_open_circuit(self) -> None:
        """动作：进入半开状态"""
        self._generation += 1
        self.state = self.STATE_HALF_OPEN
        logger.info(
            f"熔断器 CircuitBreaker[{self.name}] 进入半开 (HALF_OPEN) 测试模式。"
        )


class GlobalRateLimiter:
    """
    韧性设计：全局并发动态限流器

    基于单例模式管理 asyncio.Semaphore，确保在插件内的异步任务
    不会超过设定的最大并发限制（如保护 LLM 账单或避免 API 拥塞）。
    """

    _instance: GlobalRateLimiter | None = None
    _semaphore: asyncio.Semaphore | None = None
    _max_concurrency: int | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, max_concurrency: int | None = None) -> GlobalRateLimiter:
        """
        获取或创建限流器单例。

        Args:
            max_concurrency (int, optional): 允许的最大并发数。如果提供且与当前不同，则重置信号量。

        Returns:
            GlobalRateLimiter: 唯一实例
        """
        instance = cls()
        if max_concurrency is not None:
            instance.reconfigure(max_concurrency)
        elif cls._semaphore is None:
            # 默认兜底
            cls._semaphore = asyncio.Semaphore(4)
            cls._max_concurrency = 4
        return instance

    def reconfigure(self, max_concurrency: int):
        """重新配置并发上限。注意：这会替换信号量对象。

        Args:
            max_concurrency: 新的全局 LLM 并发上限。
        """
        max_concurrency = max(1, int(max_concurrency))
        if self.__class__._semaphore is None or (
            self.__class__._max_concurrency != max_concurrency
        ):
            old_val = self.__class__._max_concurrency or "None"
            logger.info(
                f"GlobalRateLimiter 重新配置并发上限：{old_val} -> {max_concurrency}"
            )
            self.__class__._semaphore = asyncio.Semaphore(max_concurrency)
            self.__class__._max_concurrency = max_concurrency

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """返回核心的异步信号量对象。"""
        if self._semaphore is None:
            self.__class__._semaphore = asyncio.Semaphore(4)
            self.__class__._max_concurrency = 4
        assert self._semaphore is not None
        return self._semaphore

    @property
    def max_concurrency(self) -> int:
        """返回当前配置的全局并发上限。"""
        if self.__class__._max_concurrency is None:
            return 4
        return self.__class__._max_concurrency

    @property
    def available_slots(self) -> int | None:
        """返回当前可用槽位数量，仅用于诊断日志。"""
        semaphore = self.__class__._semaphore
        if semaphore is None:
            return None
        return getattr(semaphore, "_value", None)
