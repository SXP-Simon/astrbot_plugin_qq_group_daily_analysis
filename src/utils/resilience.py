import asyncio
import time

from astrbot.api import logger


class CircuitBreaker:
    """
    简单的熔断器实现 (Simple Circuit Breaker)
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
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.state = self.STATE_CLOSED
        self.last_failure_time = 0

    def record_failure(self):
        """记录一次失败"""
        self.failure_count += 1
        if (
            self.state == self.STATE_CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self._open_circuit()
        elif self.state == self.STATE_HALF_OPEN:
            # 在半开状态下，一次失败直接重新打开熔断器
            self._open_circuit()

    def record_success(self):
        """记录一次成功"""
        if self.state == self.STATE_HALF_OPEN:
            self._close_circuit()
        elif self.state == self.STATE_CLOSED:
            # 成功则重置失败计数 (可选，这里选择连续失败才熔断)
            self.failure_count = 0

    def allow_request(self) -> bool:
        """是否允许请求"""
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._half_open_circuit()
                return True
            return False
        return True

    def _open_circuit(self):
        self.state = self.STATE_OPEN
        self.last_failure_time = time.time()
        logger.warning(
            f"CircuitBreaker[{self.name}] 熔断器已打开! 暂停请求 {self.recovery_timeout} 秒。"
        )

    def _close_circuit(self):
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        logger.info(f"CircuitBreaker[{self.name}] 熔断器已关闭，服务恢复。")

    def _half_open_circuit(self):
        self.state = self.STATE_HALF_OPEN
        logger.info(f"CircuitBreaker[{self.name}] 进入半开状态，尝试恢复...")


class GlobalRateLimiter:
    """
    全局限流器 (Global Rate Limiter)
    使用 asyncio.Semaphore 控制并发数
    """

    _instance = None
    _semaphore = None

    @classmethod
    def get_instance(cls, max_concurrency: int = 3):
        if cls._instance is None:
            cls._instance = cls()
            cls._semaphore = asyncio.Semaphore(max_concurrency)
        return cls._instance

    @property
    def semaphore(self):
        if self._semaphore is None:
            # Fallback if accessed before get_instance called with arg
            self._semaphore = asyncio.Semaphore(3)
        return self._semaphore


# 默认全局限流实例
global_llm_rate_limiter = GlobalRateLimiter.get_instance(max_concurrency=3).semaphore
