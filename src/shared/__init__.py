"""
共享模块 - 通用工具和常量
"""

from .constants import *
from .trace_context import TraceContext

__all__ = [
    "TraceContext",
    # 常量通过 * 导出
]
