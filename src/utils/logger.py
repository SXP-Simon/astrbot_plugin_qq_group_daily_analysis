from __future__ import annotations

import os
import sys

from astrbot.api import logger as astrbot_logger

from ..infrastructure.logging.plugin_log_buffer import global_log_buffer
from ..shared.trace_context import TraceContext


def _extract_caller_location(stacklevel: int = 1) -> str | None:
    """提取调用当前日志记录器的方法所在文件与行号

    Args:
        stacklevel: 额外向上回溯的调用栈层数（默认为 1，表示直接调用方）。

    Returns:
        形如 'filename.py:line' 的代码位置字符串，无法获取时返回 None。
    """
    try:
        frame = sys._getframe(1)
        current_file = os.path.abspath(__file__)
        # 逐层回溯并跳过 logger.py 内部的调用帧
        while frame and os.path.abspath(frame.f_code.co_filename) == current_file:
            frame = frame.f_back

        # 若指定了额外 stacklevel，继续向上回溯
        for _ in range(max(0, stacklevel - 1)):
            if frame and frame.f_back:
                frame = frame.f_back

        if frame:
            basename = os.path.basename(frame.f_code.co_filename)
            lineno = frame.f_lineno
            return f"{basename}:{lineno}"
    except Exception:
        pass
    return None


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
        stacklevel: int = 1,
    ) -> None:
        try:
            rendered = (formatted_msg % args) if args else formatted_msg
        except Exception:
            rendered = formatted_msg
        location = _extract_caller_location(stacklevel=stacklevel)
        try:
            global_log_buffer.record_log(
                level=level,
                msg=rendered,
                trace_id=trace_id,
                location=location,
            )
        except Exception:
            pass

    def info(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("INFO", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.info(formatted_msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("ERROR", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.error(formatted_msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("WARNING", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.warning(formatted_msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("DEBUG", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.debug(formatted_msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("CRITICAL", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.critical(formatted_msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        formatted_msg, trace_id = self._format_msg(msg)
        req_stack = kwargs.get("stacklevel", 1)
        self._record("ERROR", formatted_msg, trace_id, args, stacklevel=req_stack)
        kwargs["stacklevel"] = req_stack + 1
        astrbot_logger.exception(formatted_msg, *args, **kwargs)


# 导出带前缀与缓冲支持的插件统一 logger
logger = PluginLogger()
