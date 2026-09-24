"""
持久化仓储接口与存储契约 - 领域层
定义增量存储、阶段检查点快照与配置访问的抽象接口，实现领域层与基础设施层的彻底解耦。
"""

from abc import ABC, abstractmethod
from typing import Any

from ..entities.incremental_state import IncrementalBatch


class IIncrementalStore(ABC):
    """增量批次持久化仓储接口"""

    @abstractmethod
    async def save_batch(self, batch: IncrementalBatch) -> bool:
        """保存单个增量批次数据"""
        pass

    @abstractmethod
    async def query_batches(
        self,
        group_id: str,
        window_start: float,
        window_end: float,
    ) -> list[IncrementalBatch]:
        """按时间窗口范围查询增量批次列表"""
        pass

    @abstractmethod
    async def get_last_analyzed_cursor(self, group_id: str) -> tuple[int, set[str]]:
        """获取最后一次分析的消息游标 (时间戳, 消息ID集合)"""
        pass

    @abstractmethod
    async def update_last_analyzed_cursor(
        self,
        group_id: str,
        timestamp: int,
        message_ids: set[str],
    ) -> None:
        """更新最后一次分析的消息游标"""
        pass

    @abstractmethod
    async def cleanup_old_batches(self, group_id: str, before_timestamp: float) -> int:
        """清理指定群组过期的增量批次"""
        pass

    @abstractmethod
    async def get_batch_count(self, group_id: str) -> int:
        """获取指定群组当前存储的批次总数"""
        pass

    @abstractmethod
    async def reset_group(self, group_id: str) -> int:
        """清空指定群组的所有增量批次与游标"""
        pass


class ICheckpointStore(ABC):
    """阶段快照检查点仓储接口"""

    @abstractmethod
    def save_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        data: Any,
        trace_id: str = "",
        ttl_seconds: int = 86400 * 30,
    ) -> None:
        """保存阶段产物快照"""
        pass

    @abstractmethod
    def get_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        trace_id: str = "",
    ) -> Any | None:
        """读取有效的阶段产物快照"""
        pass

    @abstractmethod
    def clear_checkpoints(self, group_id: str, date_str: str) -> None:
        """清理指定群组在指定日期的阶段快照"""
        pass

    @abstractmethod
    def get_checkpoints_by_group_date(
        self, group_id: str, date_str: str
    ) -> list[dict[str, Any]]:
        """获取指定群在指定日期的所有有效 Checkpoint 快照摘要列表"""
        pass

    @abstractmethod
    def delete_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        trace_id: str = "",
    ) -> bool:
        """单点删除指定阶段 Checkpoint"""
        pass
