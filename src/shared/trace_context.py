"""
追踪上下文 - 请求追踪和关联

提供用于在插件中跟踪请求的上下文。
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# 当前追踪的上下文变量
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class TraceContext:
    """
    用于在插件中追踪请求的上下文。

    提供用于调试和监控的关联 ID 和计时信息。
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    platform: str = ""
    operation: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 计时数据
    _checkpoints: dict[str, datetime] = field(default_factory=dict, init=False)

    def checkpoint(self, name: str) -> None:
        """
        记录计时检查点。

        参数:
            name: 检查点名称
        """
        self._checkpoints[name] = datetime.now()

    def elapsed_ms(self, from_checkpoint: str | None = None) -> float:
        """
        获取经过的时间（毫秒）。

        参数:
            from_checkpoint: 可选的起始检查点

        返回:
            经过的时间（毫秒）
        """
        start = self.start_time
        if from_checkpoint and from_checkpoint in self._checkpoints:
            start = self._checkpoints[from_checkpoint]

        delta = datetime.now() - start
        return delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """将追踪上下文转换为字典。"""
        return {
            "trace_id": self.trace_id,
            "group_id": self.group_id,
            "platform": self.platform,
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "elapsed_ms": self.elapsed_ms(),
            "metadata": self.metadata,
            "checkpoints": {k: v.isoformat() for k, v in self._checkpoints.items()},
        }

    def __enter__(self) -> "TraceContext":
        """进入上下文管理器。"""
        _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器。"""
        _current_trace.set(None)

    @classmethod
    def current(cls) -> Optional["TraceContext"]:
        """获取当前追踪上下文。"""
        return _current_trace.get()

    @classmethod
    def get_or_create(
        cls,
        group_id: str = "",
        platform: str = "",
        operation: str = "",
    ) -> "TraceContext":
        """
        获取当前追踪或创建新追踪。

        参数:
            group_id: 群组标识符
            platform: 平台名称
            operation: 操作名称

        返回:
            TraceContext 实例
        """
        current = cls.current()
        if current:
            return current

        return cls(
            group_id=group_id,
            platform=platform,
            operation=operation,
        )


def get_trace_id() -> str:
    """
    获取当前追踪 ID 或生成新的。

    返回:
        追踪 ID 字符串
    """
    trace = TraceContext.current()
    if trace:
        return trace.trace_id
    return str(uuid.uuid4())[:8]


def with_trace(
    group_id: str = "",
    platform: str = "",
    operation: str = "",
):
    """
    为函数添加追踪上下文的装饰器。

    参数:
        group_id: 群组标识符
        platform: 平台名称
        operation: 操作名称

    返回:
        装饰后的函数
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            with TraceContext(
                group_id=group_id,
                platform=platform,
                operation=operation or func.__name__,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
