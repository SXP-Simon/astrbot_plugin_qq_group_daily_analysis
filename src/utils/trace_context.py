import contextvars
import logging
import time
import uuid

# 定义 ContextVar
_trace_id_ctx = contextvars.ContextVar("trace_id", default="")


class TraceContext:
    """
    链路追踪上下文管理器
    """

    @staticmethod
    def set(trace_id: str):
        """设置当前上下文的 TraceID"""
        return _trace_id_ctx.set(trace_id)

    @staticmethod
    def get() -> str:
        """获取当前上下文的 TraceID"""
        return _trace_id_ctx.get()

    @staticmethod
    def generate(prefix: str = "") -> str:
        """生成一个新的 TraceID (Prefix + Timestamp + UUID前8位)"""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        if prefix:
            return f"{prefix}-{timestamp}-{unique_id}"
        return f"{timestamp}-{unique_id}"

    @staticmethod
    def clear():
        """清除当前上下文的 TraceID"""
        _trace_id_ctx.set("")


class TraceLogFilter(logging.Filter):
    """
    日志过滤器，自动注入 TraceID
    """

    def filter(self, record):
        trace_id = _trace_id_ctx.get()
        if trace_id:
            # 将 trace_id 注入到 record 中，同时也修改 msg 以便在不支持自定义 format 的 logger 中也能看到
            record.trace_id = trace_id
            record.msg = f"[{trace_id}] {record.msg}"
        else:
            record.trace_id = ""
        return True
