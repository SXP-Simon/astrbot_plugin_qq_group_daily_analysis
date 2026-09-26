"""
Web 控制台请求与响应数据传输对象 (Rest DTOs)

为 WebUI 控制台接口提供标准强类型契约与字段定义，作为应用层与表现层之间的通信模型。
严格遵守 DDD 分层架构契约，消灭无类型字典与散装参数乱飞。
"""

from __future__ import annotations

from typing import TypedDict

# ============================================================================
# 1. 任务控制与调度 DTO (Task Control & Scheduling)
# ============================================================================


class TaskTriggerRequestDTO(TypedDict, total=False):
    """触发分析任务请求数据传输对象。

    Attributes:
        group_id: 目标群聊唯一标识符（支持纯群号或 UMO）。
        group_name: 群聊显示名称。
        platform: 所属通信平台标识（如 qq、onebot、telegram、discord 等）。
        provider_id: 指定覆盖的 LLM 服务商 ID（可选）。
        template_name: 指定覆盖的报告渲染模板名称（可选）。
    """

    group_id: str
    group_name: str
    platform: str
    provider_id: str | None
    template_name: str | None


class TaskResumeRequestDTO(TypedDict, total=False):
    """断点续跑任务请求数据传输对象。

    Attributes:
        trace_id: 待续跑的历史追踪标识符。
        provider_id: 指定覆盖的 LLM 服务商 ID（可选）。
        template_name: 指定覆盖的报告渲染模板名称（可选）。
    """

    trace_id: str
    provider_id: str | None
    template_name: str | None


class TaskCancelRequestDTO(TypedDict):
    """取消分析任务请求数据传输对象。

    Attributes:
        task_id: 目标活跃任务的唯一链路标识符。
    """

    task_id: str


class TaskResponseDTO(TypedDict, total=False):
    """通用任务响应数据传输对象。

    Attributes:
        status: 任务处理状态（ok、error、failed 等）。
        message: 面向用户的提示文本或错误详情。
        trace_id: 任务唯一链路追踪标识符。
        group_id: 关联的群聊唯一标识符。
    """

    status: str
    message: str
    trace_id: str
    group_id: str


# ============================================================================
# 2. 链路追踪与观测指标 DTO (Tracing & Metrics)
# ============================================================================


class TraceListQueryDTO(TypedDict, total=False):
    """链路追踪列表分页与条件查询数据传输对象。

    Attributes:
        limit: 单页最大返回条数。
        offset: 分页偏移量。
        group_id: 群号过滤条件（None 表示不限）。
        status: 执行状态过滤条件（success、failed、running 等）。
        trigger_type: 触发方式过滤条件（web_ui、cron、manual 等）。
        search: 关键词模糊搜索。
        start_time: 起始时间戳（秒）。
        end_time: 截止时间戳（秒）。
        sort_by: 排序字段（默认 started_at）。
        sort_order: 排序方向（desc 或 asc）。
    """

    limit: int
    offset: int
    group_id: str | None
    status: str | None
    trigger_type: str | None
    search: str | None
    start_time: float | None
    end_time: float | None
    sort_by: str
    sort_order: str


class TrendsQueryDTO(TypedDict, total=False):
    """趋势图表指标查询数据传输对象。

    Attributes:
        granularity: 时间聚合粒度（day 或 hour）。
        range_count: 回溯时间桶点数。
    """

    granularity: str
    range_count: int


class MetricsSummaryDTO(TypedDict, total=False):
    """KPI 与指标概览响应数据传输对象。

    Attributes:
        total_traces: 历史总执行次数。
        succeeded_count: 成功执行次数。
        failed_count: 失败执行次数。
        success_rate: 分析成功率（0.0 - 1.0）。
        avg_duration_ms: 平均执行耗时（毫秒）。
        today_traces: 今日分析次数。
        today_active_groups: 今日活跃群数。
        total_tokens_spent: 累计消耗 Token。
        total_cost_spent: 累计预估成本（美元）。
        today_tokens_spent: 今日消耗 Token。
        today_cost_spent: 今日预估成本（美元）。
    """

    total_traces: int
    succeeded_count: int
    failed_count: int
    success_rate: float
    avg_duration_ms: float
    today_traces: int
    today_active_groups: int
    total_tokens_spent: int
    total_cost_spent: float
    today_tokens_spent: int
    today_cost_spent: float


# ============================================================================
# 3. 增量分析与 Checkpoint 产物管理 DTO (Incremental & Checkpoints)
# ============================================================================


class CheckpointListQueryDTO(TypedDict, total=False):
    """阶段产物快照分页与条件查询数据传输对象。

    Attributes:
        limit: 单页最大返回条数。
        offset: 分页偏移量。
        group_id: 群号过滤条件。
        date_str: 日期过滤条件（YYYY-MM-DD）。
        stage_name: 阶段名称过滤条件。
        trace_id: 关联链路追踪标识符。
    """

    limit: int
    offset: int
    group_id: str | None
    date_str: str | None
    stage_name: str | None
    trace_id: str | None


class CheckpointDetailQueryDTO(TypedDict):
    """阶段产物快照详情查询数据传输对象。

    Attributes:
        group_id: 目标群号。
        date_str: 分析日期（YYYY-MM-DD）。
        stage_name: 阶段名称（如 FETCH_MESSAGES、CLEAN_MESSAGES、LLM_ANALYSIS 等）。
        trace_id: 关联链路追踪标识符（可选）。
    """

    group_id: str
    date_str: str
    stage_name: str
    trace_id: str


class CheckpointDeleteDTO(TypedDict, total=False):
    """删除 Checkpoint 请求数据传输对象。

    Attributes:
        group_id: 目标群号。
        date_str: 分析日期（YYYY-MM-DD）。
        stage_name: 待删除的阶段名称（可选，若未指定则清空该群该日期全部阶段）。
        trace_id: 关联链路追踪标识符（可选）。
    """

    group_id: str
    date_str: str
    stage_name: str
    trace_id: str


class IncrementalBatchesQueryDTO(TypedDict):
    """查询指定群增量批次与游标请求数据传输对象。

    Attributes:
        group_id: 目标群号。
    """

    group_id: str


class IncrementalBatchDetailQueryDTO(TypedDict):
    """查询单条增量批次详情请求数据传输对象。

    Attributes:
        group_id: 目标群号。
        batch_id: 增量批次唯一标识符。
    """

    group_id: str
    batch_id: str


class IncrementalBatchDeleteDTO(TypedDict):
    """删除单条增量批次请求数据传输对象。

    Attributes:
        group_id: 目标群号。
        batch_id: 增量批次唯一标识符。
    """

    group_id: str
    batch_id: str


class IncrementalResetDTO(TypedDict):
    """重置群增量批次与游标请求数据传输对象。

    Attributes:
        group_id: 目标群号。
    """

    group_id: str


# ============================================================================
# 4. 日志检索 DTO (Log Query)
# ============================================================================


class LogQueryDTO(TypedDict, total=False):
    """日志列表查询与过滤数据传输对象。

    Attributes:
        limit: 单页最大返回条数。
        offset: 分页偏移量。
        level: 日志等级过滤（DEBUG、INFO、WARNING、ERROR 等）。
        trace_id: 链路追踪标识符过滤。
        tag: 日志分类标签过滤。
        search: 关键词模糊搜索。
    """

    limit: int
    offset: int
    level: str | None
    trace_id: str | None
    tag: str | None
    search: str | None


# ============================================================================
# 5. 历史报告与重渲染 DTO (Report & Rerender)
# ============================================================================


class ReportContentQueryDTO(TypedDict):
    """获取历史报告内容请求数据传输对象。

    Attributes:
        filename: 报告文件名（图片或 HTML 文件名）。
    """

    filename: str


class RerenderReportRequestDTO(TypedDict, total=False):
    """重渲染历史报告请求数据传输对象。

    Attributes:
        group_id: 目标群聊唯一标识符。
        date_str: 报告归属日期（格式：YYYY-MM-DD）。
        template_name: 选用的报告渲染模板名称。
        render_format: 目标输出格式（image 或 html）。
        platform_id: 目标通信平台标识。
        trace_id: 关联的历史追踪标识符。
    """

    group_id: str
    date_str: str
    template_name: str
    render_format: str
    platform_id: str | None
    trace_id: str


# ============================================================================
# 6. 模板管理 DTO (Template Management)
# ============================================================================


class TemplatePreviewQueryDTO(TypedDict):
    """获取模板预览图请求数据传输对象。

    Attributes:
        template_name: 视觉模板名称。
    """

    template_name: str


class TemplateInstallUrlDTO(TypedDict, total=False):
    """从 Git URL 安装模板请求数据传输对象。

    Attributes:
        repo_url: GitHub 仓库链接。
        name: 自定义安装后的模板目录名（可选）。
    """

    repo_url: str
    name: str | None


class TemplateInstallFileDTO(TypedDict, total=False):
    """从 Zip 压缩包安装模板请求数据传输对象。

    Attributes:
        file_data: Base64 编码的 Zip 压缩包内容。
        filename: 上传的文件名。
        name: 自定义安装后的模板目录名（可选）。
    """

    file_data: str
    filename: str
    name: str | None


class TemplateUninstallDTO(TypedDict):
    """卸载自定义模板请求数据传输对象。

    Attributes:
        name: 待卸载的自定义模板名称。
    """

    name: str


# ============================================================================
# 7. 配置管理 DTO (Config Management)
# ============================================================================


class ConfigSaveDTO(TypedDict):
    """保存插件配置请求数据传输对象。

    Attributes:
        config: 全量配置项字典。
    """

    config: dict[str, object]


class ConfigFileUploadDTO(TypedDict, total=False):
    """上传配置附件请求数据传输对象。

    Attributes:
        filename: 文件原始名称。
        file_data: Base64 编码的文件内容。
        config_key: 目标配置项路径标识。
    """

    filename: str
    file_data: str
    config_key: str | None


class ConfigFileContentQueryDTO(TypedDict):
    """获取配置文件内容请求数据传输对象。

    Attributes:
        path: 文件相对存储路径。
    """

    path: str


# ============================================================================
# 8. 通用 Web API 响应封装 DTO (Web API Response)
# ============================================================================


class ApiResponseDTO(TypedDict, total=False):
    """统一 Web API 响应封装数据传输对象。

    Attributes:
        code: 业务状态码（200 为成功，非 200 为异常）。
        status: 业务状态描述（ok、error 等）。
        message: 响应消息说明。
        data: 业务数据载荷。
    """

    code: int
    status: str
    message: str
    data: object
