import contextvars
import logging
import time
import uuid
from typing import Any

# 定义 ContextVar
_trace_id_ctx = contextvars.ContextVar("trace_id", default="")


class TraceContext:
    """
    链路追踪：追踪上下文管理者

    利用 `contextvars` 在异步任务流中传递全局唯一的 `trace_id`，
    实现对单一请求/分析任务的全流程日志记录追踪。
    """

    @staticmethod
    def set(trace_id: str) -> Any:
        """
        设置当前异步上下文的 TraceID。

        Args:
            trace_id (str): 追踪 ID 字符串

        Returns:
            Token: contextvars 令牌，用于后续重置
        """
        return _trace_id_ctx.set(trace_id)

    @staticmethod
    def get() -> str:
        """
        获取当前异步上下文中的 TraceID。

        Returns:
            str: 当前任务的追踪 ID，若无则返回空字符串
        """
        return _trace_id_ctx.get()

    @staticmethod
    def generate(prefix: str = "") -> str:
        """
        构建生成一个新的高辨识度 TraceID。

        格式：[prefix-]时间戳-UUID前8位

        Args:
            prefix (str, optional): ID 前缀 (如 'ANALYSIS')

        Returns:
            str: 生成的追踪 ID
        """
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        if prefix:
            return f"{prefix}-{timestamp}-{unique_id}"
        return f"{timestamp}-{unique_id}"

    @staticmethod
    def clear() -> None:
        """
        重置/清除当前上下文的 TraceID 记录。
        """
        _trace_id_ctx.set("")


class TraceLogFilter(logging.Filter):
    """
    日志治理：TraceID 注入过滤器

    该过滤器被挂载到日志系统后，会自动从流水上下文中提取 `trace_id`
    并注入到每一条日志记录中，便于日后通过 ID 检索完整的任务执行链路。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        拦截日志记录进行 TraceID 动态修饰。

        Args:
            record (logging.LogRecord): 日志记录对象

        Returns:
            bool: 始终返回 True (仅修改不拦截)
        """
        trace_id = _trace_id_ctx.get()
        if trace_id:
            # 同时注入属性和修饰消息文本，保证在简易日志格式下也能直接可见
            record.trace_id = trace_id
            record.msg = f"[{trace_id}] {record.msg}"
        else:
            record.trace_id = ""
        return True
