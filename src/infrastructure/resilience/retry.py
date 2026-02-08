"""
Retry - Retry utilities with exponential backoff

Provides retry decorators and utilities for handling transient failures.
"""

import asyncio
import random
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional, Tuple, Type, Union

from astrbot.api import logger


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

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
    Calculate delay for a retry attempt.

    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
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
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        retry_exceptions: Tuple of exceptions to retry on
        on_retry: Optional callback on retry (exception, attempt)

    Returns:
        Decorated function
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
                            f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


class RetryExecutor:
    """
    Executor for running functions with retry logic.
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize the retry executor.

        Args:
            config: Retry configuration
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
        Execute a function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            config: Optional override config
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
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
                        f"Retry {attempt + 1}/{cfg.max_attempts} after {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise last_exception
