"""
速率限制器 - 控制请求速率

实现令牌桶速率限制，防止服务过载。
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from astrbot.api import logger


@dataclass
class RateLimiter:
    """
    令牌桶速率限制器。

    使用令牌桶算法控制操作速率。
    """

    name: str
    rate: float  # 每秒令牌数
    burst: int  # 最大突发大小（桶容量）

    # 内部状态
    _tokens: float = field(default=0, init=False)
    _last_update: float = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        """初始化令牌桶。"""
        self._tokens = float(self.burst)
        self._last_update = time.time()

    def _refill(self) -> None:
        """根据经过的时间补充令牌。"""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now

    async def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        从桶中获取令牌。

        参数:
            tokens: 要获取的令牌数
            timeout: 最大等待时间（None = 无限等待）

        返回:
            如果获取到令牌返回 True，超时返回 False
        """
        start_time = time.time()

        async with self._lock:
            while True:
                self._refill()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False

                # 计算获取足够令牌的等待时间
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

                if timeout is not None:
                    remaining = timeout - (time.time() - start_time)
                    wait_time = min(wait_time, remaining)

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取令牌而不等待。

        参数:
            tokens: 要获取的令牌数

        返回:
            如果获取到令牌返回 True，否则返回 False
        """
        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available_tokens(self) -> float:
        """获取当前可用令牌数。"""
        self._refill()
        return self._tokens

    def reset(self) -> None:
        """重置速率限制器到满容量。"""
        self._tokens = float(self.burst)
        self._last_update = time.time()


class RateLimiterGroup:
    """
    不同操作的速率限制器组。
    """

    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}

    def get_or_create(
        self,
        name: str,
        rate: float = 1.0,
        burst: int = 5,
    ) -> RateLimiter:
        """
        获取或创建速率限制器。

        参数:
            name: 限制器名称
            rate: 每秒令牌数
            burst: 最大突发大小

        返回:
            RateLimiter 实例
        """
        if name not in self._limiters:
            self._limiters[name] = RateLimiter(name=name, rate=rate, burst=burst)
        return self._limiters[name]

    def reset_all(self) -> None:
        """重置所有速率限制器。"""
        for limiter in self._limiters.values():
            limiter.reset()
