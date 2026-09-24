"""
Web 控制台请求与响应数据传输对象 (Rest DTOs)
为 React WebUI 控制台接口提供标准强类型契约与字段定义。
"""

from typing import Any, TypedDict


class TaskTriggerRequestDTO(TypedDict, total=False):
    """触发分析任务请求 DTO"""

    group_id: str
    date: str
    task_type: str
    template_theme: str


class TaskCancelRequestDTO(TypedDict):
    """取消分析任务请求 DTO"""

    group_id: str


class TaskResponseDTO(TypedDict, total=False):
    """通用任务响应 DTO"""

    status: str
    message: str
    trace_id: str
    group_id: str


class MetricsSummaryDTO(TypedDict):
    """KPI 与指标概览响应 DTO"""

    total_analyses: int
    success_rate: float
    total_tokens: int
    avg_duration: float
    active_groups: int


class RerenderReportRequestDTO(TypedDict, total=False):
    """重渲染报告请求 DTO"""

    group_id: str
    date: str
    template_name: str
    render_format: str
    trace_id: str


class ApiResponseDTO(TypedDict, total=False):
    """统一 Web API 响应封装 DTO"""

    code: int
    message: str
    data: Any
