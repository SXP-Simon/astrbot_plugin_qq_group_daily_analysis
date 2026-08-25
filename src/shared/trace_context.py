"""
追踪上下文 - 全链路请求追踪、Span 耗时打点与 dsh-context 风格指标审计
"""

from __future__ import annotations

import functools
import logging
import re
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Trace ID 中群名的最大长度（平衡可读性和日志宽度）
_MAX_GROUP_NAME_LEN = 10

# 用于匹配报告 Caption 中去重 Token 的正则模式
REPORT_CAPTION_PATTERN = re.compile(r"\| (\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

# 当前追踪的上下文变量
_current_trace: ContextVar[TraceContext | None] = ContextVar(
    "current_trace", default=None
)

# 全局持有的 Trace 仓储引用（用于链路自动持久化）
_global_trace_store: Any | None = None


@dataclass
class TraceContext:
    """
    核心组件：全链路追踪上下文 (Tracing Context)

    集成 TraceId 传递、Span 级细粒度耗时打点、dsh-context 风格的上下文演进与 Token 审计。
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    group_name: str = ""
    platform: str = ""
    operation: str = ""
    trigger_type: str = "manual"
    status: str = "running"
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_ms: float | None = None

    # 错误归因
    error_stage: str | None = None
    error_message: str | None = None
    stack_trace: str | None = None

    # 扩展元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    # 细粒度 Span 列表
    _spans: list[dict[str, Any]] = field(default_factory=list, init=False)

    # dsh-context 上下文演进指标
    _context_metrics: dict[str, Any] | None = field(default=None, init=False)

    # Token 消耗与成本审计
    _token_usage: dict[str, Any] = field(
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
    def set_global_store(cls, store: Any) -> None:
        """设置全局持久化仓储实例"""
        global _global_trace_store
        _global_trace_store = store

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
        self, stage_name: str, payload: dict[str, Any] | None = None
    ) -> Generator[dict[str, Any], None, None]:
        """
        创建一个细粒度 Span 上下文，自动记录该步骤耗时与执行状态。

        Args:
            stage_name: 阶段名称，如 'FETCH_MESSAGES', 'LLM_TOPICS', 'RENDER_REPORT'
            payload: 随 Span 记录的参数或快照字典
        """
        start_ts = time.time()
        span_id = f"{self.trace_id}_{stage_name}_{len(self._spans) + 1}"
        span_record: dict[str, Any] = {
            "span_id": span_id,
            "trace_id": self.trace_id,
            "stage_name": stage_name,
            "status": "running",
            "started_at": start_ts,
            "duration_ms": None,
            "payload": payload or {},
        }
        self._spans.append(span_record)

        try:
            yield span_record
            span_record["status"] = "success"
        except Exception as exc:
            span_record["status"] = "failed"
            span_record["payload"]["error"] = str(exc)
            raise
        finally:
            span_record["duration_ms"] = round((time.time() - start_ts) * 1000, 2)

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
        self._token_usage["prompt_tokens"] += prompt_tokens
        self._token_usage["completion_tokens"] += completion_tokens
        self._token_usage["total_tokens"] += total
        self._token_usage["estimated_cost"] += cost_est

        if analyzer_name:
            cur = self._token_usage["per_analyzer"].get(
                analyzer_name,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            cur["prompt_tokens"] += prompt_tokens
            cur["completion_tokens"] += completion_tokens
            cur["total_tokens"] += total
            self._token_usage["per_analyzer"][analyzer_name] = cur

    def finish(
        self,
        status: str = "succeeded",
        error_stage: str | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """
        标记任务完成，计算总耗时并自动持久化到 SQLite
        """
        self.status = status
        self.completed_at = time.time()
        self.duration_ms = round((self.completed_at - self.started_at) * 1000, 2)
        if error_stage:
            self.error_stage = error_stage
        if error_message:
            self.error_message = error_message
        if stack_trace:
            self.stack_trace = stack_trace

        # 自动落盘
        if _global_trace_store is not None:
            try:
                _global_trace_store.save_trace(self.to_dict())
            except Exception as e:
                logging.getLogger(__name__).warning(f"Trace 持久化保存失败: {e}")

    def to_dict(self) -> dict[str, Any]:
        """将完整链路快照序列化为字典"""
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
            "token_usage": self._token_usage,
            "checkpoints": {k: v.isoformat() for k, v in self._checkpoints.items()},
        }

    def __enter__(self) -> TraceContext:
        self._token = _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and self.status == "running":
            self.finish(
                status="failed",
                error_stage=self._spans[-1]["stage_name"]
                if self._spans
                else "PIPELINE",
                error_message=str(exc_val),
            )
        elif self.status == "running":
            self.finish(status="succeeded")

        if self._token:
            _current_trace.reset(self._token)
            self._token = None

    @classmethod
    def current(cls) -> TraceContext | None:
        return _current_trace.get()

    @classmethod
    def get_or_create(
        cls,
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
            group_id=group_id,
            group_name=group_name,
            platform=platform,
            operation=operation,
            trigger_type=trigger_type,
        )
        if auto_bind:
            new_ctx._token = _current_trace.set(new_ctx)
        return new_ctx

    @staticmethod
    def generate(prefix: str = "", group_name: str = "") -> str:
        timestamp = datetime.now().strftime("%H%M")
        parts: list[str] = []
        if prefix:
            parts.append(prefix)
        if group_name:
            safe_name = re.sub(r'[\s\n\r\t/\\:*?"<>|\[\]{}]', "", group_name)
            safe_name = safe_name[:_MAX_GROUP_NAME_LEN]
            if safe_name:
                parts.append(safe_name)
        parts.append(timestamp)
        return "_".join(parts)

    @staticmethod
    def make_report_caption() -> str:
        ts = datetime.now().strftime("%m-%d %H:%M:%S")
        return f"📊 每日群聊分析报告已生成 | {ts}"

    @classmethod
    def set(cls, trace_id: str) -> None:
        ctx = cls(trace_id=trace_id)
        _current_trace.set(ctx)

    @classmethod
    def get(cls) -> str:
        return get_trace_id()


class TraceLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def get_trace_id() -> str:
    trace = TraceContext.current()
    if trace:
        return trace.trace_id
    return str(uuid.uuid4())[:8]


def with_trace(
    group_id: str = "",
    platform: str = "",
    operation: str = "",
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            with TraceContext(
                group_id=group_id,
                platform=platform,
                operation=op_name,
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
