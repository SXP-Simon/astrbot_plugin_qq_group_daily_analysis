"""
流水线执行上下文与阶段管理 (Pipeline Execution Context & Step Manager)

提供结构化的异步上下文管理器，封装 Span 打点、阶段状态推进、指标 Payload 记录以及 Checkpoint 快照自动持久化。
"""

from __future__ import annotations

import enum
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from ...infrastructure.persistence.checkpoint_store import CheckpointStore
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger


@dataclass
class PipelineStep:
    """流水线单阶段执行状态容器。

    Attributes:
        stage_name: 当前执行阶段名称。
        span_record: 关联的 Trace Span 记录字典。
        payload: 当前阶段的指标与快照元数据。
        output: 当前阶段产出物，用于 Checkpoint 自动持久化。
        status: 当前阶段状态 ('running', 'success', 'warning', 'failed')。
    """

    stage_name: str
    span_record: dict[str, Any]
    payload: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    status: str = "running"

    def set_payload(self, **kwargs: Any) -> None:
        """更新当前阶段的指标与元数据。

        Args:
            **kwargs: 键值对指标数据。
        """
        self.payload.update(kwargs)
        self.span_record.setdefault("payload", {}).update(kwargs)

    def set_output(self, output: Any, **payload_kwargs: Any) -> None:
        """设置当前阶段产出物并同步更新指标。

        Args:
            output: 阶段产出物对象。
            **payload_kwargs: 附带的指标键值对。
        """
        self.output = output
        if payload_kwargs:
            self.set_payload(**payload_kwargs)

    def mark_warning(self, warning_message: str) -> None:
        """标记当前阶段为警告状态。

        Args:
            warning_message: 警告原因说明。
        """
        self.status = "warning"
        self.span_record["status"] = "warning"
        self.set_payload(warning=warning_message)

    def mark_failed(self, error_message: str) -> None:
        """标记当前阶段为失败状态。

        Args:
            error_message: 失败原因说明。
        """
        self.status = "failed"
        self.span_record["status"] = "failed"
        self.set_payload(error=error_message)


class PipelineContext:
    """流水线上下文管理器，协调单次分析或重跑流程。"""

    def __init__(
        self,
        trace: TraceContext | None,
        checkpoint_store: CheckpointStore | None,
        group_id: str,
        date_str: str,
    ) -> None:
        """初始化流水线上下文。

        Args:
            trace: 全链路追踪上下文。
            checkpoint_store: Checkpoint 存储器。
            group_id: 目标群号。
            date_str: 分析日期标识（YYYY-MM-DD）。
        """
        self.trace = trace
        self.checkpoint_store = checkpoint_store
        self.group_id = str(group_id)
        self.date_str = str(date_str)

    @asynccontextmanager
    async def step(
        self,
        stage: AnalysisStage | str,
        initial_payload: dict[str, Any] | None = None,
        save_checkpoint: bool = False,
        serializer: Callable[[Any], dict[str, Any]] | None = None,
        ttl_seconds: int = 86400 * 30,
    ) -> AsyncGenerator[PipelineStep]:
        """开启一个流水线执行阶段，自动管理 Span 耗时与 Checkpoint 持久化。

        Args:
            stage: 阶段名称或枚举。
            initial_payload: 初始指标元数据。
            save_checkpoint: 退出时是否自动保存 Checkpoint。
            serializer: 产出物序列化函数。
            ttl_seconds: Checkpoint 有效期（秒）。

        Yields:
            PipelineStep: 阶段状态控制对象。
        """
        stage_name = stage.value if isinstance(stage, enum.Enum) else str(stage)
        payload_dict = dict(initial_payload or {})

        if self.trace is not None:
            span_cm = self.trace.span(stage_name, payload_dict)
            span_record = span_cm.__enter__()
        else:
            span_cm = None
            span_record = {"stage_name": stage_name, "payload": payload_dict}

        step_obj = PipelineStep(
            stage_name=stage_name,
            span_record=span_record,
            payload=span_record.setdefault("payload", {}),
        )

        try:
            yield step_obj

            if (
                save_checkpoint
                and self.checkpoint_store is not None
                and step_obj.output is not None
            ):
                try:
                    data_to_save = (
                        serializer(step_obj.output)
                        if serializer is not None
                        else step_obj.output
                    )
                    self.checkpoint_store.save_checkpoint(
                        group_id=self.group_id,
                        date_str=self.date_str,
                        stage_name=stage_name,
                        data=data_to_save,
                        ttl_seconds=ttl_seconds,
                    )
                    step_obj.set_payload(checkpoint_saved=True)
                except Exception as cp_err:
                    logger.warning(
                        f"保存阶段 {stage_name} Checkpoint 失败 (群: {self.group_id}): {cp_err}"
                    )

            if span_record.get("status") == "running" or not span_record.get("status"):
                span_record["status"] = (
                    step_obj.status if step_obj.status != "running" else "success"
                )

        except Exception as exc:
            step_obj.mark_failed(str(exc))
            raise
        finally:
            if span_cm is not None:
                span_cm.__exit__(None, None, None)

    def restore_checkpoint_span(
        self,
        stage: AnalysisStage | str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """记录从 Checkpoint 恢复的瞬时 Span。

        Args:
            stage: 恢复的阶段名称。
            payload: 附带元数据。
        """
        if self.trace is None:
            return
        stage_name = stage.value if isinstance(stage, enum.Enum) else str(stage)
        combined_payload = {"stage": stage_name, "restored": True}
        if payload:
            combined_payload.update(payload)
        with self.trace.span(AnalysisStage.CHECKPOINT_RESTORE.value, combined_payload):
            pass
