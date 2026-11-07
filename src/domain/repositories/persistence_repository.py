"""
持久化仓储接口与存储契约 - 领域层
定义增量存储、阶段检查点快照与配置访问的抽象接口，实现领域层与基础设施层的彻底解耦。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.incremental_state import IncrementalBatch, IncrementalBatchPage
    from ..value_objects.analysis_results import (
        CheckpointDetailPayload,
        CheckpointGroupPayload,
        CheckpointSummaryPayload,
    )


class IIncrementalStore(ABC):
    """增量批次持久化仓储接口"""

    @abstractmethod
    async def save_batch(self, batch: IncrementalBatch) -> bool:
        """保存单个增量批次数据"""

    @abstractmethod
    async def query_batches(
        self,
        group_id: str,
        window_start: float,
        window_end: float,
    ) -> list[IncrementalBatch]:
        """按时间窗口范围查询增量批次列表"""

    @abstractmethod
    async def get_last_analyzed_cursor(self, group_id: str) -> tuple[int, set[str]]:
        """获取最后一次分析的消息游标 (时间戳, 消息ID集合)"""

    @abstractmethod
    async def update_last_analyzed_cursor(
        self,
        group_id: str,
        timestamp: int,
        message_ids: set[str],
    ) -> None:
        """更新最后一次分析的消息游标"""

    @abstractmethod
    async def cleanup_old_batches(self, group_id: str, before_timestamp: float) -> int:
        """清理指定群组过期的增量批次"""

    @abstractmethod
    async def get_batch_count(self, group_id: str) -> int:
        """获取指定群组当前存储的批次总数"""

    @abstractmethod
    async def reset_group(self, group_id: str) -> int:
        """清空指定群组的所有增量批次与游标"""

    @abstractmethod
    async def get_tracked_groups(self) -> list[str]:
        """获取所有已记录增量批次的群组列表"""

    @abstractmethod
    async def list_batch_page(
        self, group_id: str, page: int = 1, page_size: int = 20
    ) -> IncrementalBatchPage:
        """读取一页批次；分页总数与排序使用同一份索引。

        Args:
            group_id: 群组 ID。
            page: 从 1 开始的页码。
            page_size: 每页数量。

        Returns:
            分页概览及全部索引可确认的最新消息时间。
        """

    @abstractmethod
    async def get_batch_detail(
        self, group_id: str, batch_id: str
    ) -> IncrementalBatch | None:
        """获取单个增量批次的完整结构化详情"""

    @abstractmethod
    async def delete_batch(self, group_id: str, batch_id: str) -> bool:
        """删除指定群组的单个增量批次"""


class ICheckpointStore(ABC):
    """阶段快照检查点仓储接口"""

    def replace_checkpoint_data(
        self, checkpoint_id: str, expected_data: object, data: object
    ) -> bool:
        """仅替换指定快照的产物，保留身份、创建时间和过期时间。

        Args:
            checkpoint_id: 精确快照主键，不进行旧版本回退匹配。
            expected_data: 编辑前读取的产物，用于并发比较。
            data: 经过编辑的新产物。

        Returns:
            产物一致且替换成功时为真。

        Raises:
            NotImplementedError: 仓储尚不支持快照修订。
        """
        raise NotImplementedError

    @abstractmethod
    def save_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        data: object,
        trace_id: str = "",
        ttl_seconds: int = 86400 * 30,
    ) -> None:
        """保存阶段产物快照"""

    @abstractmethod
    def get_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        trace_id: str = "",
    ) -> object | None:
        """读取有效的阶段产物快照"""

    @abstractmethod
    def clear_checkpoints(self, group_id: str, date_str: str) -> None:
        """清理指定群组在指定日期的阶段快照"""

    @abstractmethod
    def get_checkpoints_by_group_date(
        self, group_id: str, date_str: str
    ) -> list[CheckpointSummaryPayload]:
        """获取指定群在指定日期的所有有效 Checkpoint 快照摘要列表"""

    @abstractmethod
    def get_checkpoints_by_date_range(
        self,
        group_id: str,
        start_date: str,
        end_date: str,
        stage_name: str = "LLM_ANALYSIS",
    ) -> list[dict[str, object]]:
        """按日期范围查询指定群在各自然日最新有效的一份阶段 Checkpoint 详情列表（同日取 MAX(created_at)）"""

    @abstractmethod
    def delete_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        trace_id: str = "",
    ) -> bool:
        """单点删除指定阶段 Checkpoint"""

    @abstractmethod
    def list_all_checkpoints(
        self,
        limit: int = 50,
        offset: int = 0,
        group_id: str | None = None,
        date_str: str | None = None,
        stage_name: str | None = None,
        trace_id: str | None = None,
        platform: str | None = None,
    ) -> tuple[list[CheckpointSummaryPayload], int]:
        """分页获取所有 Checkpoint 快照元数据列表"""

    @abstractmethod
    def get_distinct_checkpoint_groups(self) -> list[str]:
        """获取所有存在 Checkpoint 快照的唯一群号列表"""

    @abstractmethod
    def get_checkpoint_group_sessions(self) -> list[CheckpointGroupPayload]:
        """获取有效快照关联的群聊身份，未关联任务的记录保留空平台。"""

    @abstractmethod
    def get_checkpoint_detail(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        trace_id: str = "",
    ) -> CheckpointDetailPayload | None:
        """读取指定 Checkpoint 的完整详情与反序列化产物"""
