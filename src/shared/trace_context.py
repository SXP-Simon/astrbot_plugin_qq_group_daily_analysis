"""
Trace Context - Request tracing and correlation

Provides context for tracking requests across the plugin.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class TraceContext:
    """
    Context for tracing requests through the plugin.

    Provides correlation IDs and timing information for debugging
    and monitoring.
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    platform: str = ""
    operation: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timing data
    _checkpoints: Dict[str, datetime] = field(default_factory=dict, init=False)

    def checkpoint(self, name: str) -> None:
        """
        Record a timing checkpoint.

        Args:
            name: Checkpoint name
        """
        self._checkpoints[name] = datetime.now()

    def elapsed_ms(self, from_checkpoint: Optional[str] = None) -> float:
        """
        Get elapsed time in milliseconds.

        Args:
            from_checkpoint: Optional checkpoint to measure from

        Returns:
            Elapsed time in milliseconds
        """
        start = self.start_time
        if from_checkpoint and from_checkpoint in self._checkpoints:
            start = self._checkpoints[from_checkpoint]

        delta = datetime.now() - start
        return delta.total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace context to dictionary."""
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
        """Enter context manager."""
        _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        _current_trace.set(None)

    @classmethod
    def current(cls) -> Optional["TraceContext"]:
        """Get the current trace context."""
        return _current_trace.get()

    @classmethod
    def get_or_create(
        cls,
        group_id: str = "",
        platform: str = "",
        operation: str = "",
    ) -> "TraceContext":
        """
        Get current trace or create a new one.

        Args:
            group_id: Group identifier
            platform: Platform name
            operation: Operation name

        Returns:
            TraceContext instance
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
    Get current trace ID or generate a new one.

    Returns:
        Trace ID string
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
    Decorator to add trace context to a function.

    Args:
        group_id: Group identifier
        platform: Platform name
        operation: Operation name

    Returns:
        Decorated function
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
