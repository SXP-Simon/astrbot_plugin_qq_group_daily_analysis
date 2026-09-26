"""
历史仓库 - 存储分析历史的实现

该模块提供分析结果和历史记录的持久化存储。
它封装了现有的 history_manager 功能。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ...utils.logger import logger

if TYPE_CHECKING:
    from ...domain.value_objects import AnalysisResultPayload, GroupHistoryPayload


class HistoryRepository:
    """
    基础设施：历史仓库

    负责群聊分析历史记录的持久化存储与检索。目前使用本地 JSON 文件实现，
    保持了与旧版 `history_manager` 的数据格式兼容性。

    Attributes:
        data_dir (Path): 插件数据存储的总根目录
        history_dir (Path): 专门存放历史记录的子目录
    """

    data_dir: Path
    history_dir: Path

    def __init__(self, data_dir: str | Path) -> None:
        """
        初始化历史仓库。

        Args:
            data_dir (str | Path): 存储历史数据的基础目录路径
        """
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """内部方法：确保所需的目录结构已创建。"""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_group_history_path(self, group_id: str) -> Path:
        """内部方法：获取特定群组的历史 JSON 文件路径。"""
        return self.history_dir / f"group_{group_id}.json"

    def save_analysis_result(
        self,
        group_id: str,
        result: AnalysisResultPayload,
        date_str: str | None = None,
    ) -> bool:
        """
        将分析结果保存到持久化存储。

        Args:
            group_id (str): 群组标识符
            result: 包含统计、金句等信息的分析结果字典
            date_str (str, optional): 关联日期 (YYYY-MM-DD)，默认为执行日

        Returns:
            bool: 保存成功返回 True，发生异常返回 False
        """
        try:
            date_str = date_str or datetime.now().strftime("%Y-%m-%d")
            history = self.load_group_history(group_id)

            # 结构化存储：二级映射 {date -> result}
            daily = history.setdefault("daily", {})
            entry_data = dict(result)
            if "timestamp" not in entry_data:
                entry_data["timestamp"] = datetime.now().isoformat()

            daily[date_str] = cast("AnalysisResultPayload", entry_data)
            history["last_updated"] = datetime.now().isoformat()

            # 原子写入（覆盖）
            history_path = self._get_group_history_path(group_id)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.debug(f"已保存群 {group_id} 在 {date_str} 的历史分析记录")
            return True

        except Exception as e:
            logger.error(f"保存群 {group_id} 的历史记录失败: {e}")
            return False

    def load_group_history(self, group_id: str) -> GroupHistoryPayload:
        """
        加载特定群组的完整历史记录字典。

        Args:
            group_id (str): 群组标识符

        Returns:
            GroupHistoryPayload: 历史数据字典，若文件不存在则返回包含空 daily 结构的初始字典
        """
        try:
            history_path = self._get_group_history_path(group_id)
            if history_path.exists():
                with open(history_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return cast("GroupHistoryPayload", data)
            return {"daily": {}, "group_id": group_id}
        except Exception as e:
            logger.error(f"加载群 {group_id} 的历史记录失败: {e}")
            return {"daily": {}, "group_id": group_id}

    def get_analysis_result(
        self, group_id: str, date_str: str
    ) -> AnalysisResultPayload | None:
        """
        获取指定日期已存档的分析结果。

        Args:
            group_id (str): 群组 ID
            date_str (str): 目标日期 (YYYY-MM-DD)

        Returns:
            AnalysisResultPayload | None: 分析结果字典，未找到则返回 None
        """
        history = self.load_group_history(group_id)
        return history.get("daily", {}).get(date_str)

    def get_recent_results(
        self, group_id: str, limit: int = 7
    ) -> list[AnalysisResultPayload]:
        """
        获取指定群组最近 N 次的分析结果列表。

        Args:
            group_id (str): 群组 ID
            limit (int): 最大返回条数

        Returns:
            list[AnalysisResultPayload]: 按日期降序排列的结果列表
        """
        history = self.load_group_history(group_id)
        daily = history.get("daily", {})

        # 按日期字符串字典序降序排列（YYYY-MM-DD 天然有序）
        sorted_dates = sorted(daily.keys(), reverse=True)[:limit]
        return [daily[date] for date in sorted_dates]

    def has_analysis_for_date(self, group_id: str, date_str: str) -> bool:
        """
        检查指定日期是否已经生成过分析。

        Args:
            group_id (str): 群组 ID
            date_str (str): 日期字符串

        Returns:
            bool: 存在记录则返回 True
        """
        return self.get_analysis_result(group_id, date_str) is not None

    def delete_old_history(self, group_id: str, keep_days: int = 30) -> int:
        """
        自动清理超过天数限制的陈旧历史记录。

        Args:
            group_id (str): 群组 ID
            keep_days (int): 保留的天数上限

        Returns:
            int: 实际删除的记录条数
        """
        try:
            history = self.load_group_history(group_id)
            daily = history.get("daily", {})

            # 计算截止日期边界
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")

            # 筛选已过期的日期
            dates_to_delete = [date for date in daily if date < cutoff]

            for date in dates_to_delete:
                del daily[date]

            if dates_to_delete:
                history["daily"] = daily
                history_path = self._get_group_history_path(group_id)
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)

            return len(dates_to_delete)

        except Exception as e:
            logger.error(f"清理群 {group_id} 的陈旧历史记录失败: {e}")
            return 0

    def list_groups_with_history(self) -> list[str]:
        """
        扫描文件系统，列出当前所有具有存档记录的群组 ID。

        Returns:
            list[str]: 群组 ID 字符串列表
        """
        try:
            groups = []
            for file_path in self.history_dir.glob("group_*.json"):
                # 从文件名反推群组 ID (group_123.json -> 123)
                group_id = file_path.stem.replace("group_", "")
                groups.append(group_id)
            return groups
        except Exception as e:
            logger.error(f"列出历史记录群组失败: {e}")
            return []
