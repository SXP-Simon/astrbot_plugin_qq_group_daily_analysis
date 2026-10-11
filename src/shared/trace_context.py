"""
追踪上下文 - 全链路请求追踪、Span 耗时打点与 dsh-context 风格指标审计
"""

from __future__ import annotations

import functools
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, ParamSpec, TypedDict, TypeVar, cast

from ..domain.value_objects.task_event import TaskEvent
from ..domain.value_objects.task_status import TaskStatus
from .constants import PROCESS_BOOT_ID, PROCESS_PID, AnalysisStage

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator, Mapping

    from ..application.services.task_lifecycle_service import TaskLifecycleService
    from ..infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ..infrastructure.webui.active_task_manager import ActiveTaskManager


class SpanPayload(TypedDict, total=False):
    """Span 上下文自定义载荷契约"""

    success: bool
    warning: str | bool
    subtask_errors: list[str] | bool
    error: str
    start_memory_mb: float
    end_memory_mb: float
    delta_memory_mb: float
    raw_message_count: int
    cleaned_message_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class SpanRecord(TypedDict):
    """单次步骤耗时与内存 Span 记录契约"""

    span_id: str
    trace_id: str
    stage_name: str
    status: str
    started_at: float
    duration_ms: float | None
    start_memory_mb: float
    end_memory_mb: float | None
    delta_memory_mb: float | None
    payload: dict[str, object]


class AnalyzerTokenUsage(TypedDict):
    """单个分析器 Token 消耗契约"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TraceTokenUsage(TypedDict):
    """全链路 Token 消耗与成本审计契约"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    per_analyzer: dict[str, AnalyzerTokenUsage]


class TraceContextMetrics(TypedDict):
    """上下文演进与清洗漏斗指标契约"""

    raw_message_count: int
    cleaned_message_count: int
    compression_ratio: float
    incremental_batches: int
    window_size: int


class TracePerformanceMetrics(TypedDict):
    """运行时内存与性能遥测契约"""

    init_memory_mb: float
    peak_memory_mb: float
    final_memory_mb: float
    delta_memory_mb: float


class TraceContextSnapshot(TypedDict, total=False):
    """全链路追踪数据落盘与传输快照契约"""

    trace_id: str
    group_id: str
    group_name: str
    platform: str
    operation: str
    trigger_type: str
    status: str
    current_stage: str
    started_at: float
    completed_at: float | None
    duration_ms: float | None
    error_stage: str | None
    error_message: str | None
    stack_trace: str | None
    extra: dict[str, object]
    spans: list[SpanRecord]
    context_metrics: TraceContextMetrics | None
    performance_metrics: TracePerformanceMetrics
    token_usage: TraceTokenUsage
    checkpoints: dict[str, str]
    pid: int
    boot_id: str


class ActiveTaskSnapshot(TypedDict):
    """活跃任务状态快照契约（供 WebUI 与 SSE 广播）"""

    task_id: str
    group_id: str
    group_name: str
    platform: str
    trigger_type: str
    current_stage: str
    started_at: float
    duration_s: float
    last_heartbeat: float


# Trace ID 中群名的最大长度（平衡可读性和日志宽度）
_MAX_GROUP_NAME_LEN = 10

# 用于匹配报告 Caption 中去重 Token 的正则模式
REPORT_CAPTION_PATTERN = re.compile(r"\| (\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _get_process_rss_mb() -> float:
    """获取当前 Python 进程常驻内存集 (RSS, MB)。"""
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


# 当前追踪的上下文变量
_current_trace: ContextVar[TraceContext | None] = ContextVar(
    "current_trace", default=None
)

# 全局持有的 Trace 仓储引用（用于链路自动持久化）
_global_trace_store: TraceSQLiteStore | None = None
_global_active_task_manager: ActiveTaskManager | None = None
_global_task_lifecycle_service: TaskLifecycleService | None = None
_active_traces: dict[str, TraceContext] = {}

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class TraceContext:
    """
    核心组件：全链路追踪上下文 (Tracing Context)

    集成 TraceId 传递、Span 级细粒度耗时与内存增量打点、dsh-context 风格的上下文演进与 Token 审计。
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    group_name: str = ""
    platform: str = ""
    operation: str = ""
    trigger_type: str = "manual"
    _status: TaskStatus = field(default=TaskStatus.RUNNING, init=False, repr=False)
    current_stage: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_ms: float | None = None

    # 进程与生命周期凭据
    pid: int = field(default_factory=lambda: PROCESS_PID)
    boot_id: str = field(default_factory=lambda: PROCESS_BOOT_ID)

    # 错误归因
    error_stage: str | None = None
    error_message: str | None = None
    stack_trace: str | None = None

    # 扩展元数据
    metadata: dict[str, object] = field(default_factory=dict)

    # 细粒度 Span 列表
    _spans: list[SpanRecord] = field(default_factory=list, init=False)

    # dsh-context 上下文演进指标
    _context_metrics: TraceContextMetrics | None = field(default=None, init=False)

    # 遥测开关 (类级别默认 True)
    _enable_metrics: ClassVar[bool] = True

    # 运行期内存性能监控 (RSS MB)
    _init_memory_mb: float = field(default=0.0, init=False)
    _peak_memory_mb: float = field(default=0.0, init=False)
    _final_memory_mb: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        init_rss = _get_process_rss_mb() if self._enable_metrics else 0.0
        self._init_memory_mb = init_rss
        self._peak_memory_mb = init_rss

    @property
    def status(self) -> str:
        """只读任务状态；外部调用方必须发送生命周期事件。"""
        return self._status.value

    # Token 消耗与成本审计
    _token_usage: TraceTokenUsage = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "per_analyzer": {},
        },
        init=False,
    )

    # 传统锚点兼容
    _checkpoints: dict[str, datetime] = field(default_factory=dict, init=False)
    _token: Token | None = field(default=None, init=False, repr=False)

    @classmethod
    def set_metrics_enabled(cls, enabled: bool) -> None:
        """设置全链路运行时指标遥测开关"""
        cls._enable_metrics = enabled

    @classmethod
    def is_metrics_enabled(cls) -> bool:
        """检查全链路运行时指标遥测是否启用"""
        return cls._enable_metrics

    @classmethod
    def set_global_store(cls, store: TraceSQLiteStore | None) -> None:
        """设置全局持久化仓储实例"""
        global _global_trace_store, _global_task_lifecycle_service
        if store is not _global_trace_store:
            _global_task_lifecycle_service = None
        _global_trace_store = store

    @classmethod
    def set_global_lifecycle_service(cls, service: TaskLifecycleService | None) -> None:
        """设置应用层任务生命周期服务。"""
        global _global_task_lifecycle_service
        _global_task_lifecycle_service = service

    @classmethod
    def set_active_task_manager(cls, manager: ActiveTaskManager | None) -> None:
        """设置全局活跃任务管理器引用"""
        global _global_active_task_manager
        _global_active_task_manager = manager

    @classmethod
    def get_active_trace(cls, trace_id: str) -> TraceContext | None:
        """根据 trace_id 获取内存中活跃运行的 TraceContext 实例"""
        return _active_traces.get(trace_id)

    @property
    def start_time(self) -> datetime:
        """兼容旧版 start_time 属性"""
        return datetime.fromtimestamp(self.started_at)

    def checkpoint(self, name: str) -> None:
        """在当前时间轴上设置命名锚点（兼容旧接口）"""
        self._checkpoints[name] = datetime.now()

    def elapsed_ms(self, from_checkpoint: str | None = None) -> float:
        """计算从开始或指定锚点到当前时刻经过的毫秒数"""
        if from_checkpoint and from_checkpoint in self._checkpoints:
            delta = datetime.now() - self._checkpoints[from_checkpoint]
            return delta.total_seconds() * 1000
        return (time.time() - self.started_at) * 1000

    @contextmanager
    def span(
        self,
        stage_name: AnalysisStage | str,
        payload: Mapping[str, object] | None = None,
    ) -> Generator[SpanRecord]:
        """创建一个细粒度 Span 上下文，自动记录该步骤耗时、内存增量与执行状态。

        Args:
            stage_name: 阶段名称，如 AnalysisStage.FETCH_MESSAGES 或字符串
            payload: 随 Span 记录的参数或快照字典
        """
        stage_str = (
            stage_name.value
            if isinstance(stage_name, AnalysisStage)
            else str(stage_name)
        )
        self.current_stage = stage_str
        _active_traces[self.trace_id] = self
        if _global_active_task_manager is not None:
            try:
                _global_active_task_manager.update_stage_sync(self.trace_id, stage_str)
            except Exception:
                pass

        start_ts = time.time()
        start_mem = _get_process_rss_mb() if self._enable_metrics else 0.0
        if start_mem > self._peak_memory_mb:
            self._peak_memory_mb = start_mem

        span_id = f"{self.trace_id}_{stage_str}_{len(self._spans) + 1}"
        span_record: SpanRecord = {
            "span_id": span_id,
            "trace_id": self.trace_id,
            "stage_name": stage_str,
            "status": "running",
            "started_at": start_ts,
            "duration_ms": None,
            "start_memory_mb": start_mem,
            "end_memory_mb": None,
            "delta_memory_mb": None,
            "payload": dict(payload or {}),
        }
        self._spans.append(span_record)

        try:
            yield span_record
            if span_record.get("status") in ("running", None):
                span_record["status"] = "success"
        except Exception as exc:
            span_record["status"] = "failed"
            span_record["payload"]["error"] = str(exc)
            raise
        finally:
            end_ts = time.time()
            end_mem = _get_process_rss_mb() if self._enable_metrics else 0.0
            if end_mem > self._peak_memory_mb:
                self._peak_memory_mb = end_mem

            span_record["duration_ms"] = round((end_ts - start_ts) * 1000, 2)
            span_record["end_memory_mb"] = end_mem
            span_record["delta_memory_mb"] = round(end_mem - start_mem, 2)

            # 同步填充到 payload 字典供前端组件灵活读取
            p = span_record["payload"]
            if "start_memory_mb" not in p:
                p["start_memory_mb"] = start_mem
            if "end_memory_mb" not in p:
                p["end_memory_mb"] = end_mem
            if "delta_memory_mb" not in p:
                p["delta_memory_mb"] = span_record["delta_memory_mb"]

            if self.status != "running" and _global_trace_store is not None:
                try:
                    _global_trace_store.save_trace(self.to_dict())
                except Exception:
                    pass

    def touch_heartbeat(self) -> None:
        """刷新当前 Trace 关联的活跃任务心跳时间戳（供长耗时阶段保活）。"""
        if _global_active_task_manager is not None and self.trace_id:
            try:
                if hasattr(_global_active_task_manager, "touch_heartbeat"):
                    _global_active_task_manager.touch_heartbeat(self.trace_id)
                elif hasattr(_global_active_task_manager, "update_stage_sync"):
                    _global_active_task_manager.update_stage_sync(
                        self.trace_id, self.current_stage
                    )
            except Exception:
                pass

    def set_context_metrics(
        self,
        raw_message_count: int,
        cleaned_message_count: int,
        incremental_batches: int = 0,
        window_size: int = 0,
    ) -> None:
        """
        记录上下文演进与清洗漏斗指标（dsh-context 核心）。

        Args:
            raw_message_count: 原始拉取消息数
            cleaned_message_count: 规则清洗后保留的消息数
            incremental_batches: 增量处理分批数
            window_size: 采样窗口大小
        """
        compression_ratio = (
            round(cleaned_message_count / max(1, raw_message_count), 4)
            if raw_message_count > 0
            else 1.0
        )
        self._context_metrics = {
            "raw_message_count": raw_message_count,
            "cleaned_message_count": cleaned_message_count,
            "compression_ratio": compression_ratio,
            "incremental_batches": incremental_batches,
            "window_size": window_size,
        }

    def add_token_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        analyzer_name: str = "",
        cost_est: float = 0.0,
    ) -> None:
        """
        累加 Token 消耗与成本。

        Args:
            prompt_tokens: 输入 Token
            completion_tokens: 输出 Token
            analyzer_name: 具体的 Analyzer 名称 (如 'topics', 'user_titles', 'comics')
            cost_est: 估算费用
        """
        total = prompt_tokens + completion_tokens
        self._token_usage["prompt_tokens"] = (
            self._token_usage.get("prompt_tokens", 0) + prompt_tokens
        )
        self._token_usage["completion_tokens"] = (
            self._token_usage.get("completion_tokens", 0) + completion_tokens
        )
        self._token_usage["total_tokens"] = (
            self._token_usage.get("total_tokens", 0) + total
        )
        self._token_usage["estimated_cost"] = (
            self._token_usage.get("estimated_cost", 0.0) + cost_est
        )

        if analyzer_name:
            per_analyzer = self._token_usage.setdefault("per_analyzer", {})
            cur = per_analyzer.get(
                analyzer_name,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            cur["prompt_tokens"] = cur.get("prompt_tokens", 0) + prompt_tokens
            cur["completion_tokens"] = (
                cur.get("completion_tokens", 0) + completion_tokens
            )
            cur["total_tokens"] = cur.get("total_tokens", 0) + total
            per_analyzer[analyzer_name] = cur

    def finish(
        self,
        event: TaskEvent,
        error_stage: str | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """发送生命周期事件，并在跃迁成功后完成本地 Trace。

        Args:
            event: 请求的生命周期事件，由状态机决定目标状态。
            error_stage: 错误或中止发生的阶段名称。
            error_message: 错误或中止原因。
            stack_trace: 错误堆栈文本。

        Raises:
            ValueError: 当前 Trace 状态不允许该事件。
            RuntimeError: 数据库中的任务状态已被其他操作并发改变。
        """
        # 延迟导入，避免 shared 与 domain.services 包初始化时形成循环依赖。
        from ..domain.services.task_state_machine import TaskStateMachine

        effective_event = event
        if event == TaskEvent.SUCCEED:
            if any(s.get("status") == "failed" for s in self._spans):
                effective_event = TaskEvent.FAIL
            elif any(
                s.get("status") == "warning"
                or s["payload"].get("success") is False
                or bool(s["payload"].get("warning"))
                or bool(s["payload"].get("subtask_errors"))
                for s in self._spans
            ) or self.metadata.get("has_warnings"):
                effective_event = TaskEvent.WARN

        current_status = self._status
        target_status = TaskStateMachine.transition(current_status, effective_event)
        if self.status == target_status.value:
            return

        completed_at = time.time()
        duration_ms = round((completed_at - self.started_at) * 1000, 2)
        final_memory_mb = _get_process_rss_mb() if self._enable_metrics else 0.0
        peak_memory_mb = max(self._peak_memory_mb, final_memory_mb)
        terminal_span_status = {
            TaskEvent.SUCCEED: "success",
            TaskEvent.WARN: "warning",
            TaskEvent.FAIL: "failed",
            TaskEvent.ABORT: "aborted",
            TaskEvent.CANCEL: "aborted",
            TaskEvent.SKIP: "skipped",
        }[effective_event]
        finished_spans: list[SpanRecord] = []
        for span in self._spans:
            finished_span = dict(span)
            finished_span["payload"] = dict(span["payload"])
            if finished_span.get("status") == "running":
                finished_span["status"] = terminal_span_status
                started_at = finished_span.get("started_at", self.started_at)
                if finished_span.get("duration_ms") is None and isinstance(
                    started_at, (int, float)
                ):
                    finished_span["duration_ms"] = round(
                        (completed_at - started_at) * 1000, 2
                    )
            finished_spans.append(cast("SpanRecord", finished_span))

        snapshot = self.to_dict()
        snapshot.update(
            {
                "status": target_status.value,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error_stage": error_stage or self.error_stage,
                "error_message": error_message or self.error_message,
                "stack_trace": stack_trace or self.stack_trace,
                "spans": finished_spans,
                "performance_metrics": {
                    "init_memory_mb": self._init_memory_mb,
                    "peak_memory_mb": peak_memory_mb,
                    "final_memory_mb": final_memory_mb,
                    "delta_memory_mb": round(final_memory_mb - self._init_memory_mb, 2),
                },
            }
        )

        if _global_task_lifecycle_service is not None:
            try:
                target_status = _global_task_lifecycle_service.transition(
                    self.trace_id,
                    effective_event,
                    expected_status=current_status,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    error_stage=error_stage,
                    error_message=error_message,
                    stack_trace=stack_trace,
                )
            except RuntimeError:
                latest = (
                    _global_trace_store.get_trace(self.trace_id)
                    if _global_trace_store is not None
                    else None
                )
                if latest is None:
                    raise
                latest_status = str(latest.get("status", ""))
                terminal_statuses = {
                    TaskStatus.SUCCEEDED.value,
                    TaskStatus.WARNING.value,
                    TaskStatus.FAILED.value,
                    TaskStatus.ABORTED.value,
                    TaskStatus.SKIPPED.value,
                    TaskStatus.COMPLETED.value,
                    TaskStatus.CANCELLED.value,
                }
                if latest_status not in terminal_statuses:
                    raise
                self._status = TaskStatus(latest_status)
                self.completed_at = cast("float | None", latest.get("completed_at"))
                self.duration_ms = cast("float | None", latest.get("duration_ms"))
                latest_spans = latest.get("spans")
                if isinstance(latest_spans, list):
                    self._spans = cast("list[SpanRecord]", latest_spans)
                _active_traces.pop(self.trace_id, None)
                return
        elif _global_trace_store is not None:
            transitioned = _global_trace_store.transition_trace_status(
                self.trace_id,
                current_status,
                effective_event,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_stage=error_stage,
                error_message=error_message,
                stack_trace=stack_trace,
            )
            if not transitioned:
                latest = _global_trace_store.get_trace(self.trace_id)
                if not latest or latest.get("status") != target_status.value:
                    raise RuntimeError(
                        f"Trace {self.trace_id} 已被并发改变状态，拒绝覆盖"
                    )

        self._status = target_status
        self.completed_at = completed_at
        self.duration_ms = duration_ms
        self._final_memory_mb = final_memory_mb
        self._peak_memory_mb = peak_memory_mb
        self.error_stage = error_stage or self.error_stage
        self.error_message = error_message or self.error_message
        self.stack_trace = stack_trace or self.stack_trace
        self._spans = finished_spans
        _active_traces.pop(self.trace_id, None)

        if _global_trace_store is not None:
            try:
                _global_trace_store.save_trace(self.to_dict())
            except Exception as e:
                from ..utils.logger import logger

                logger.warning(f"Trace 快照保存失败: {e}")

    def to_dict(self) -> TraceContextSnapshot:
        """将完整链路快照序列化为字典"""
        curr_mem = self._final_memory_mb or (
            _get_process_rss_mb() if self._enable_metrics else 0.0
        )
        return {
            "trace_id": self.trace_id,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "platform": self.platform,
            "operation": self.operation,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "pid": self.pid,
            "boot_id": self.boot_id,
            "duration_ms": (
                self.duration_ms
                if self.duration_ms is not None
                else (time.time() - self.started_at) * 1000
            ),
            "error_stage": self.error_stage,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "extra": self.metadata,
            "spans": list(self._spans),
            "context_metrics": self._context_metrics,
            "performance_metrics": {
                "init_memory_mb": self._init_memory_mb,
                "peak_memory_mb": self._peak_memory_mb,
                "final_memory_mb": curr_mem,
                "delta_memory_mb": round(curr_mem - self._init_memory_mb, 2),
            },
            "token_usage": self._token_usage,
            "checkpoints": {k: v.isoformat() for k, v in self._checkpoints.items()},
        }

    def __enter__(self) -> TraceContext:
        self._token = _current_trace.set(self)
        _active_traces[self.trace_id] = self
        if _global_trace_store is not None and self.status == TaskStatus.RUNNING.value:
            _global_trace_store.save_trace(self.to_dict())
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None and self.status == "running":
            self.finish(
                event=TaskEvent.FAIL,
                error_stage=self._spans[-1]["stage_name"]
                if self._spans
                else "PIPELINE",
                error_message=str(exc_val),
            )
        elif self.status == "running":
            self.finish(event=TaskEvent.SUCCEED)

        if self._token:
            _current_trace.reset(self._token)
            self._token = None

    @classmethod
    def current(cls) -> TraceContext | None:
        return _current_trace.get()

    @classmethod
    def get_or_create(
        cls,
        trace_id: str = "",
        group_id: str = "",
        group_name: str = "",
        platform: str = "",
        operation: str = "",
        trigger_type: str = "manual",
        auto_bind: bool = False,
    ) -> TraceContext:
        current = cls.current()
        if current:
            return current

        new_ctx = cls(
            trace_id=trace_id or str(uuid.uuid4())[:8],
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            operation=operation,
            trigger_type=trigger_type,
        )
        if auto_bind:
            new_ctx._token = _current_trace.set(new_ctx)
            _active_traces[new_ctx.trace_id] = new_ctx
        return new_ctx

    @staticmethod
    def generate(prefix: str = "", group_name: str = "") -> str:
        """生成全局唯一且具备高可读性的 TraceID。

        格式: {prefix}_{group_name}_{YYYYMMDD_HHMMSS}_{entropy}
        包含精确时间与足够强度的随机熵，彻底杜绝同秒或高并发场景下的 ID 碰撞。
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        entropy = uuid.uuid4().hex[:12]
        parts: list[str] = []
        if prefix:
            parts.append(prefix)
        if group_name:
            safe_name = re.sub(r'[\s\n\r\t/\\:*?"<>|\[\]{}]', "", str(group_name))
            safe_name = safe_name[:_MAX_GROUP_NAME_LEN]
            if safe_name:
                parts.append(safe_name)
        parts.append(timestamp)
        parts.append(entropy)
        return "_".join(parts)

    @staticmethod
    def make_report_caption() -> str:
        ts = datetime.now().strftime("%m-%d %H:%M:%S")
        return f"📊 每日群聊分析报告已生成 | {ts}"

    @classmethod
    def set(
        cls,
        trace_id: str,
        group_id: str = "",
        group_name: str = "",
        platform: str = "",
        trigger_type: str = "manual",
    ) -> TraceContext:
        ctx = cls(
            trace_id=trace_id,
            group_id=str(group_id),
            group_name=group_name,
            platform=platform,
            trigger_type=trigger_type,
        )
        ctx._token = _current_trace.set(ctx)
        _active_traces[ctx.trace_id] = ctx
        if _global_trace_store is not None:
            _global_trace_store.save_trace(ctx.to_dict())
        return ctx

    @classmethod
    def get(cls) -> str:
        return get_trace_id()


def get_trace_id() -> str:
    trace = TraceContext.current()
    if trace:
        return trace.trace_id
    return str(uuid.uuid4())[:8]


def with_trace(
    group_id: str = "",
    platform: str = "",
    operation: str = "",
) -> Callable[
    [Callable[P, Coroutine[object, object, R]]],
    Callable[P, Coroutine[object, object, R]],
]:
    def decorator(
        func: Callable[P, Coroutine[object, object, R]],
    ) -> Callable[P, Coroutine[object, object, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            op_name = operation or func.__name__
            with TraceContext(
                group_id=group_id,
                platform=platform,
                operation=op_name,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
