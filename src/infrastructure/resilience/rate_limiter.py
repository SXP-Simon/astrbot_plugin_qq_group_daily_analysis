"""
Rate Limiter - Controls request rates

Implements token bucket rate limiting to prevent overwhelming services.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from astrbot.api import logger


@dataclass
class RateLimiter:
    """
    Token bucket rate limiter.

    Controls the rate of operations by using a token bucket algorithm.
    """

    name: str
    rate: float  # Tokens per second
    burst: int  # Maximum burst size (bucket capacity)

    # Internal state
    _tokens: float = field(default=0, init=False)
    _last_update: float = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self):
        """Initialize the token bucket."""
        self._tokens = float(self.burst)
        self._last_update = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now

    async def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if tokens acquired, False if timeout
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

                # Calculate wait time for enough tokens
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

                if timeout is not None:
                    remaining = timeout - (time.time() - start_time)
                    wait_time = min(wait_time, remaining)

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self._tokens

    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        self._tokens = float(self.burst)
        self._last_update = time.time()


class RateLimiterGroup:
    """
    Group of rate limiters for different operations.
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
        Get or create a rate limiter.

        Args:
            name: Limiter name
            rate: Tokens per second
            burst: Maximum burst size

        Returns:
            RateLimiter instance
        """
        if name not in self._limiters:
            self._limiters[name] = RateLimiter(name=name, rate=rate, burst=burst)
        return self._limiters[name]

    def reset_all(self) -> None:
        """Reset all rate limiters."""
        for limiter in self._limiters.values():
            limiter.reset()
