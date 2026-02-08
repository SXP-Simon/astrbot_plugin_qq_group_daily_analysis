"""
断路器 - 防止级联故障

实现断路器模式，防止对失败服务的重复调用。
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from ...utils.logger import logger


class CircuitState(Enum):
    """断路器状态。"""

    CLOSED = "closed"  # 正常运行
    OPEN = "open"  # 故障中，拒绝调用
    HALF_OPEN = "half_open"  # 测试服务是否恢复


@dataclass
class CircuitBreaker:
    """
    断路器实现。

    通过跟踪故障率并临时阻止对故障服务的调用
    来防止级联故障。
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    # 内部状态
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """获取当前断路器状态，检查是否恢复。"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """转换到新状态。"""
        old_state = self._state
        self._state = new_state

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        logger.debug(f"断路器 {self.name}: {old_state.value} -> {new_state.value}")

    def record_success(self) -> None:
        """记录成功调用。"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            # 成功时重置故障计数
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败调用。"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def can_execute(self) -> bool:
        """检查是否可以执行调用。"""
        state = self.state  # 这可能触发状态转换

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            return False
        elif state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            return self._half_open_calls <= self.half_open_max_calls

        return False

    def reset(self) -> None:
        """重置断路器到关闭状态。"""
        self._transition_to(CircuitState.CLOSED)

    async def execute(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ):
        """
        使用断路器保护执行函数。

        参数:
            func: 要执行的异步函数
            *args: 函数参数
            fallback: 断路器打开时的可选降级函数
            **kwargs: 函数关键字参数

        返回:
            函数结果或降级结果

        异常:
            Exception: 如果断路器打开且没有提供降级函数
        """
        if not self.can_execute():
            if fallback:
                return await fallback(*args, **kwargs)
            raise Exception(f"断路器 {self.name} 已打开")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
