"""
追踪上下文 - 请求追踪和关联

提供用于在插件中跟踪请求的上下文。
"""

import functools
import logging
import re
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# Trace ID 中群名的最大长度（平衡可读性和日志宽度）
_MAX_GROUP_NAME_LEN = 10

# 用于匹配报告 Caption 中去重 Token 的正则模式
# 格式: "| MM-DD HH:MM:SS"
REPORT_CAPTION_PATTERN = re.compile(r"\| (\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

# 当前追踪的上下文变量
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class TraceContext:
    """
    核心组件：全链路追踪上下文 (Tracing Context)

    该组件用于在复杂的异步分析流程中关联日志、耗时统计及元数据。
    它不仅提供了 TraceId 的生成与传递，还集成了毫秒级的性能打点（Checkpoint）功能。

    Attributes:
        trace_id (str): 链路唯一标识码，默认为 UUID 前 8 位
        group_id (str): 当前关联的群组 ID
        platform (str): 当前消息所属平台
        operation (str): 当前执行的操作名称 (如 'DAILY_ANALYSIS')
        start_time (datetime): 追踪开始的具体时刻
        metadata (dict[str, Any]): 随链路传递的额外上下文数据
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    platform: str = ""
    operation: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 内部计时器，用于多阶段耗时分析
    _checkpoints: dict[str, datetime] = field(default_factory=dict, init=False)

    def checkpoint(self, name: str) -> None:
        """
        在当前时间轴上设置一个命名锚点（打点）。

        Args:
            name (str): 锚点标识符，如 'LLM_REPLY_RECEIVED'
        """
        self._checkpoints[name] = datetime.now()

    def elapsed_ms(self, from_checkpoint: str | None = None) -> float:
        """
        计算从开始或指定锚点到当前时刻经过的毫秒数。

        Args:
            from_checkpoint (str, optional): 起始锚点名称。若为 None 则从链路启动时算起。

        Returns:
            float: 经过的毫秒数
        """
        start = self.start_time
        if from_checkpoint and from_checkpoint in self._checkpoints:
            start = self._checkpoints[from_checkpoint]

        delta = datetime.now() - start
        return delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """
        将链路快照序列化为字典格式，便于持久化或 JSON 日志输出。

        Returns:
            dict[str, Any]: 序列化后的追踪状态
        """
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

    _token: Token | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> "TraceContext":
        """进入上下文管理器，将当前实例绑定到当前协程上下文。"""
        self._token = _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文管理器，清理绑定状态。"""
        if self._token:
            _current_trace.reset(self._token)
            self._token = None

    @classmethod
    def current(cls) -> Optional["TraceContext"]:
        """
        静态获取当前协程活跃的追踪上下文。

        Returns:
            Optional[TraceContext]: 若当前处于追踪链路中则返回实例，否则返回 None
        """
        return _current_trace.get()

    @classmethod
    def get_or_create(
        cls,
        group_id: str = "",
        platform: str = "",
        operation: str = "",
        auto_bind: bool = False,
    ) -> "TraceContext":
        """
        尝试获取现有链路，若不存在则按需创建一个。

        Args:
            group_id (str): 群组 ID
            platform (str): 平台名称
            operation (str): 操作描述
            auto_bind (bool): 若新建，是否自动绑定到当前上下文（仅在 non-with 场景有用，谨慎使用）

        Returns:
            TraceContext: 活跃或新生成的实例
        """
        current = cls.current()
        if current:
            return current

        new_ctx = cls(
            group_id=group_id,
            platform=platform,
            operation=operation,
        )
        if auto_bind:
            new_ctx._token = _current_trace.set(new_ctx)
        return new_ctx

    @staticmethod
    def generate(prefix: str = "", group_name: str = "") -> str:
        """
        生成语义化、易读的追踪 ID。

        格式: {来源}_{群名}_{时间点}
        示例: manual_系统交流群_1733

        由于插件存在任务锁 (DuplicateGroupTaskError)，确保了一个群同一时间只有一个分析任务，
        因此 时间点 (HHmm) 已足够提供唯一性，无需 UUID 缀。

        Args:
            prefix (str): 来源标识，如 'manual', 'group', 'incr', 'report'
            group_name (str): 可选群名，用于日志中快速识别

        Returns:
            str: 语义化 TraceID 字符串
        """
        timestamp = datetime.now().strftime("%H%M")

        parts: list[str] = []
        if prefix:
            parts.append(prefix)
        if group_name:
            # 清理：移除空白符和文件系统不安全字符
            safe_name = re.sub(r'[\s\n\r\t/\\:*?"<>|\[\]{}]', "", group_name)
            safe_name = safe_name[:_MAX_GROUP_NAME_LEN]
            if safe_name:
                parts.append(safe_name)
        parts.append(timestamp)

        return "_".join(parts)

    @staticmethod
    def make_report_caption() -> str:
        """
        生成整洁的、面向用户的报告 Caption，包含用于去重的隐式时间戳。

        该时间戳用作图片去重检查的 Token。
        格式: "📊 每日群聊分析报告已生成 | MM-DD HH:MM:SS"

        Returns:
            str: 报告 Caption 字符串
        """
        ts = datetime.now().strftime("%m-%d %H:%M:%S")
        return f"📊 每日群聊分析报告已生成 | {ts}"

    @classmethod
    def set(cls, trace_id: str) -> None:
        """
        [兼容性接口] 直接设置当前上下文的 TraceID。
        这会创建一个新的 TraceContext 实例并将其推入 ContextVar。

        Args:
            trace_id (str): 要设置的追踪 ID 字符串
        """
        ctx = cls(trace_id=trace_id)
        # 注意：此处不手动存储 Token，依靠异步任务结束时 ContextVar 的自动清理。
        _current_trace.set(ctx)

    @classmethod
    def get(cls) -> str:
        """
        [兼容性接口] 获取当前活跃的追踪 ID 字符串。
        """
        return get_trace_id()


class TraceLogFilter(logging.Filter):
    """
    日志过滤器：自动将当前的 TraceID 注入每一条日志记录中。

    配合日志格式化字符串 `[%(trace_id)s]` 使用。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def get_trace_id() -> str:
    """
    便捷接口：快速获取当前活跃的 TraceID 或零时生成一个临时 ID。

    Returns:
        str: 8 位十六进制追踪 ID
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
    装饰器：自动为异步函数包裹追踪上下文。

    Args:
        group_id (str): 设置追踪的群组
        platform (str): 设置追踪的平台
        operation (str): 操作名称，默认为函数名

    Returns:
        Callable: 装饰后的函数
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 优先使用装饰器声明的 operation，否则取函数原始名称
            op_name = operation or func.__name__
            with TraceContext(
                group_id=group_id,
                platform=platform,
                operation=op_name,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
