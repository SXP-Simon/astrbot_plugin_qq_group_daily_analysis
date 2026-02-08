"""
重试 - 带指数退避的重试工具

提供用于处理瞬态故障的重试装饰器和工具。
"""

import asyncio
import random
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional, Tuple, Type, Union

from astrbot.api import logger


@dataclass
class RetryConfig:
    """重试行为配置。"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
) -> float:
    """
    计算重试尝试的延迟。

    参数:
        attempt: 当前尝试次数（从 0 开始）
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数退避的基数
        jitter: 是否添加随机抖动

    返回:
        延迟时间（秒）
    """
    delay = base_delay * (exponential_base**attempt)
    delay = min(delay, max_delay)

    if jitter:
        delay = delay * (0.5 + random.random())

    return delay


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    带指数退避的异步函数重试装饰器。

    参数:
        max_attempts: 最大尝试次数
        base_delay: 重试之间的基础延迟
        max_delay: 重试之间的最大延迟
        exponential_base: 指数退避的基数
        jitter: 是否添加随机抖动
        retry_exceptions: 要重试的异常元组
        on_retry: 重试时的可选回调（异常，尝试次数）

    返回:
        装饰后的函数
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        delay = calculate_delay(
                            attempt, base_delay, max_delay, exponential_base, jitter
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        logger.debug(
                            f"重试 {attempt + 1}/{max_attempts} {func.__name__} "
                            f"延迟 {delay:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            f"{func.__name__} 的所有 {max_attempts} 次尝试均失败: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


class RetryExecutor:
    """
    带重试逻辑的函数执行器。
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        初始化重试执行器。

        参数:
            config: 重试配置
        """
        self.config = config or RetryConfig()

    async def execute(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        **kwargs,
    ):
        """
        使用重试逻辑执行函数。

        参数:
            func: 要执行的异步函数
            *args: 函数参数
            config: 可选的覆盖配置
            **kwargs: 函数关键字参数

        返回:
            函数结果

        异常:
            Exception: 如果所有重试都失败
        """
        cfg = config or self.config
        last_exception = None

        for attempt in range(cfg.max_attempts):
            try:
                return await func(*args, **kwargs)
            except cfg.retry_exceptions as e:
                last_exception = e

                if attempt < cfg.max_attempts - 1:
                    delay = calculate_delay(
                        attempt,
                        cfg.base_delay,
                        cfg.max_delay,
                        cfg.exponential_base,
                        cfg.jitter,
                    )
                    logger.debug(
                        f"重试 {attempt + 1}/{cfg.max_attempts} 延迟 {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise last_exception
