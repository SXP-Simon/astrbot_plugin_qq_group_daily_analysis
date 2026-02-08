import asyncio
import time

from .logger import logger


class CircuitBreaker:
    """
    韧性设计：熔断器 (Circuit Breaker)

    用于监控外部服务（如 LLM API）的调用状态。当错误率达到阈值时，自动开启熔断，
    拦截对故障服务的进一步请求，保护系统不被连锁故障拖累，直到服务窗口恢复。

    States:
        CLOSED: 正常工作状态，允许请求
        OPEN: 熔断状态，拒绝请求
        HALF_OPEN: 尝试恢复状态，允许少量测试请求
    """

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

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
        self.state = self.STATE_CLOSED
        self.last_failure_time = 0.0

    def record_failure(self) -> None:
        """记录一次调用失败，并根据阈值决定是否切换到 OPEN 状态。"""
        self.failure_count += 1
        if (
            self.state == self.STATE_CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self._open_circuit()
        elif self.state == self.STATE_HALF_OPEN:
            # 半开状态下任何一次失败都将立即导致熔断重开
            self._open_circuit()

    def record_success(self) -> None:
        """记录一次调用成功，并尝试重置或关闭熔断器。"""
        if self.state == self.STATE_HALF_OPEN:
            self._close_circuit()
        elif self.state == self.STATE_CLOSED:
            # 正常状态下的成功重置累积计数值
            self.failure_count = 0

    def allow_request(self) -> bool:
        """
        判断是否允许本次服务请求。

        Returns:
            bool: True 为允许，False 为拦截
        """
        if self.state == self.STATE_OPEN:
            # 检查冷却时间是否已过，过则进入试探性的半开状态
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._half_open_circuit()
                return True
            return False
        return True

    def _open_circuit(self) -> None:
        """动作：开启熔断"""
        self.state = self.STATE_OPEN
        self.last_failure_time = time.time()
        logger.warning(
            f"熔断器 CircuitBreaker[{self.name}] 已激活！将拦截请求 {self.recovery_timeout} 秒。"
        )

    def _close_circuit(self) -> None:
        """动作：关闭熔断，恢复常态"""
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        logger.info(f"熔断器 CircuitBreaker[{self.name}] 已恢复至关闭 (CLOSED) 状态。")

    def _half_open_circuit(self) -> None:
        """动作：进入半开状态"""
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

    _instance: "GlobalRateLimiter | None" = None
    _semaphore: asyncio.Semaphore | None = None

    @classmethod
    def get_instance(cls, max_concurrency: int = 3) -> "GlobalRateLimiter":
        """
        获取或创建限流器单例。

        Args:
            max_concurrency (int): 允许的最大并发行数

        Returns:
            GlobalRateLimiter: 唯一实例
        """
        if cls._instance is None:
            cls._instance = cls()
            cls._semaphore = asyncio.Semaphore(max_concurrency)
        return cls._instance

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """返回核心的异步信号量对象。"""
        if self._semaphore is None:
            # 兜底：若直接通过属性访问则初始化默认值
            self._semaphore = asyncio.Semaphore(3)
        return self._semaphore


# 导出默认实例：用于 LLM 调用的全局限流
global_llm_rate_limiter: asyncio.Semaphore = GlobalRateLimiter.get_instance(
    max_concurrency=3
).semaphore
