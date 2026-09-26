"""
Web 控制台请求与响应数据传输对象 (Rest DTOs)

本模块向后兼容导出应用层 DTO 契约。
"""

from __future__ import annotations

from ...application.dto import (
    ApiResponseDTO,
    MetricsSummaryDTO,
    RerenderReportRequestDTO,
    TaskCancelRequestDTO,
    TaskResponseDTO,
    TaskTriggerRequestDTO,
)

__all__ = [
    "ApiResponseDTO",
    "MetricsSummaryDTO",
    "RerenderReportRequestDTO",
    "TaskCancelRequestDTO",
    "TaskResponseDTO",
    "TaskTriggerRequestDTO",
]
