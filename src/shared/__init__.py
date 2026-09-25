"""
共享模块 - 通用工具和常量
"""

from .constants import AnalysisStage, ContentType, Platform, ReportFormat, TaskStatus
from .trace_context import (
    ActiveTaskSnapshot,
    AnalyzerTokenUsage,
    SpanPayload,
    SpanRecord,
    TraceContext,
    TraceContextMetrics,
    TraceContextSnapshot,
    TracePerformanceMetrics,
    TraceTokenUsage,
)

__all__ = [
    "ActiveTaskSnapshot",
    "AnalysisStage",
    "AnalyzerTokenUsage",
    "ContentType",
    "Platform",
    "ReportFormat",
    "SpanPayload",
    "SpanRecord",
    "TaskStatus",
    "TraceContext",
    "TraceContextMetrics",
    "TraceContextSnapshot",
    "TracePerformanceMetrics",
    "TraceTokenUsage",
]
