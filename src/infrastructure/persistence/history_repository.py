"""
历史仓库 - 存储分析历史的实现

该模块提供分析结果和历史记录的持久化存储。
它封装了现有的 history_manager 功能。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...utils.logger import logger


class HistoryRepository:
    """
    用于存储和检索分析历史的仓库。

    此实现将历史记录存储为 JSON 文件，保持
    与现有 history_manager 的向后兼容性。
    """

    def __init__(self, data_dir: str):
        """
        初始化历史仓库。

        Args:
            data_dir: 存储历史数据的基础目录
        """
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """确保所需目录存在。"""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_group_history_path(self, group_id: str) -> Path:
        """获取群组的历史文件路径。"""
        return self.history_dir / f"group_{group_id}.json"

    def save_analysis_result(
        self,
        group_id: str,
        result: Dict[str, Any],
        date_str: Optional[str] = None,
    ) -> bool:
        """
        保存分析结果到历史记录。

        Args:
            group_id: 群组标识符
            result: 分析结果字典
            date_str: 日期字符串（默认为今天）

        Returns:
            如果保存成功则返回 True
        """
        try:
            date_str = date_str or datetime.now().strftime("%Y-%m-%d")
            history = self.load_group_history(group_id)

            # 如果不存在则添加时间戳
            if "timestamp" not in result:
                result["timestamp"] = datetime.now().isoformat()

            # 按日期存储
            if "daily" not in history:
                history["daily"] = {}

            history["daily"][date_str] = result
            history["last_updated"] = datetime.now().isoformat()

            # 写入文件
            history_path = self._get_group_history_path(group_id)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.debug(f"已保存群组 {group_id} 在 {date_str} 的分析结果")
            return True

        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
            return False

    def load_group_history(self, group_id: str) -> Dict[str, Any]:
        """
        加载群组历史记录。

        Args:
            group_id: 群组标识符

        Returns:
            历史记录字典
        """
        try:
            history_path = self._get_group_history_path(group_id)
            if history_path.exists():
                with open(history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"daily": {}, "group_id": group_id}
        except Exception as e:
            logger.error(f"加载群组历史记录失败: {e}")
            return {"daily": {}, "group_id": group_id}

    def get_analysis_result(
        self, group_id: str, date_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取特定日期的分析结果。

        Args:
            group_id: 群组标识符
            date_str: 日期字符串 (YYYY-MM-DD 格式)

        Returns:
            分析结果，如果未找到则返回 None
        """
        history = self.load_group_history(group_id)
        return history.get("daily", {}).get(date_str)

    def get_recent_results(self, group_id: str, limit: int = 7) -> List[Dict[str, Any]]:
        """
        获取最近的分析结果。

        Args:
            group_id: 群组标识符
            limit: 返回的最大结果数

        Returns:
            最近分析结果列表
        """
        history = self.load_group_history(group_id)
        daily = history.get("daily", {})

        # 按日期降序排序
        sorted_dates = sorted(daily.keys(), reverse=True)[:limit]
        return [daily[date] for date in sorted_dates]

    def has_analysis_for_date(self, group_id: str, date_str: str) -> bool:
        """
        检查特定日期是否存在分析结果。

        Args:
            group_id: 群组标识符
            date_str: 日期字符串 (YYYY-MM-DD 格式)

        Returns:
            如果分析结果存在则返回 True
        """
        result = self.get_analysis_result(group_id, date_str)
        return result is not None

    def delete_old_history(self, group_id: str, keep_days: int = 30) -> int:
        """
        删除超过指定天数的历史记录。

        Args:
            group_id: 群组标识符
            keep_days: 保留历史记录的天数

        Returns:
            删除的条目数
        """
        try:
            history = self.load_group_history(group_id)
            daily = history.get("daily", {})

            cutoff_date = datetime.now().strftime("%Y-%m-%d")
            # 计算截止日期（简单的字符串比较适用于 YYYY-MM-DD 格式）
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")

            # 查找要删除的日期
            dates_to_delete = [date for date in daily.keys() if date < cutoff]

            for date in dates_to_delete:
                del daily[date]

            if dates_to_delete:
                history["daily"] = daily
                history_path = self._get_group_history_path(group_id)
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)

            return len(dates_to_delete)

        except Exception as e:
            logger.error(f"删除旧历史记录失败: {e}")
            return 0

    def list_groups_with_history(self) -> List[str]:
        """
        列出所有有历史记录的群组。

        Returns:
            群组 ID 列表
        """
        try:
            groups = []
            for file_path in self.history_dir.glob("group_*.json"):
                group_id = file_path.stem.replace("group_", "")
                groups.append(group_id)
            return groups
        except Exception as e:
            logger.error(f"列出群组失败: {e}")
            return []
