from astrbot.api import logger as astrbot_logger

from ..infrastructure.logging.plugin_log_buffer import global_log_buffer
from ..shared.trace_context import TraceContext


class PluginLogger:
    """
    日志代理类：插件级统一日志装饰器与记录器

    自动向所有通过该实例输出的日志信息前缀添加 `[群分析插件]` 标签，
    同时将日志实时推入插件内存队列，支持 WebUI 专属日志观测与 SSE 实时推流。
    """

    def __init__(self, prefix: str = "[群分析插件]"):
        self.prefix = prefix

    def _format_msg(self, msg: str) -> tuple[str, str | None]:
        trace_id = TraceContext.get()
        if trace_id:
            return f"[{trace_id}] {self.prefix} {msg}", trace_id
        return f"{self.prefix} {msg}", None

    def _record(
        self,
        level: str,
        formatted_msg: str,
        trace_id: str | None,
        args: tuple = (),
    ) -> None:
        try:
            rendered = (formatted_msg % args) if args else formatted_msg
        except Exception:
            rendered = formatted_msg
        try:
            global_log_buffer.record_log(level=level, msg=rendered, trace_id=trace_id)
        except Exception:
            pass

    def info(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("INFO", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.info(formatted_msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("ERROR", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.error(formatted_msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("WARNING", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.warning(formatted_msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("DEBUG", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.debug(formatted_msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("CRITICAL", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.critical(formatted_msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        self._record("ERROR", formatted_msg, trace_id, args)
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        astrbot_logger.exception(formatted_msg, *args, **kwargs)


# 导出带前缀与缓冲支持的插件统一 logger
logger = PluginLogger()
