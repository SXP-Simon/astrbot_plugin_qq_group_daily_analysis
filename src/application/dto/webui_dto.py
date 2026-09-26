"""
Web 控制台请求与响应数据传输对象 (Rest DTOs)

为 WebUI 控制台接口提供标准强类型契约与字段定义，作为应用层与表现层之间的通信模型。
"""

from __future__ import annotations

from typing import TypedDict


class TaskTriggerRequestDTO(TypedDict, total=False):
    """触发分析任务请求数据传输对象。

    Attributes:
        group_id: 目标群聊唯一标识符（支持纯群号或 UMO）。
        date: 分析目标日期（格式：YYYY-MM-DD）。
        task_type: 触发任务类型（例如：full、incremental、comic）。
        template_theme: 报告指定渲染主题名称。
    """

    group_id: str
    date: str
    task_type: str
    template_theme: str


class TaskCancelRequestDTO(TypedDict):
    """取消分析任务请求数据传输对象。

    Attributes:
        group_id: 目标群聊唯一标识符。
    """

    group_id: str


class TaskResponseDTO(TypedDict, total=False):
    """通用任务响应数据传输对象。

    Attributes:
        status: 任务处理状态（success、duplicate、failed 等）。
        message: 面向用户的提示文本或错误详情。
        trace_id: 任务唯一链路追踪标识符。
        group_id: 关联的群聊唯一标识符。
    """

    status: str
    message: str
    trace_id: str
    group_id: str


class MetricsSummaryDTO(TypedDict):
    """KPI 与指标概览响应数据传输对象。

    Attributes:
        total_analyses: 历史总分析次数。
        success_rate: 分析成功率（0.0 - 1.0）。
        total_tokens: 累计消耗的 Token 总量。
        avg_duration: 任务平均执行耗时（秒）。
        active_groups: 活跃群组总数。
    """

    total_analyses: int
    success_rate: float
    total_tokens: int
    avg_duration: float
    active_groups: int


class RerenderReportRequestDTO(TypedDict, total=False):
    """重渲染历史报告请求数据传输对象。

    Attributes:
        group_id: 目标群聊唯一标识符。
        date: 报告归属日期（格式：YYYY-MM-DD）。
        template_name: 选用的报告渲染模板名称。
        render_format: 目标输出格式（image 或 html）。
        trace_id: 关联的历史追踪标识符。
    """

    group_id: str
    date: str
    template_name: str
    render_format: str
    trace_id: str


class ApiResponseDTO(TypedDict, total=False):
    """统一 Web API 响应封装数据传输对象。

    Attributes:
        code: 业务状态码（200 为成功，非 200 为异常）。
        message: 响应消息说明。
        data: 业务数据载荷。
    """

    code: int
    message: str
    data: object
