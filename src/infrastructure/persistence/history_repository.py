"""
History Repository - Implementation for storing analysis history

This module provides persistent storage for analysis results and history.
It wraps the existing history_manager functionality.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger


class HistoryRepository:
    """
    Repository for storing and retrieving analysis history.

    This implementation stores history as JSON files, maintaining
    backward compatibility with the existing history_manager.
    """

    def __init__(self, data_dir: str):
        """
        Initialize the history repository.

        Args:
            data_dir: Base directory for storing history data
        """
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_group_history_path(self, group_id: str) -> Path:
        """Get the history file path for a group."""
        return self.history_dir / f"group_{group_id}.json"

    def save_analysis_result(
        self,
        group_id: str,
        result: Dict[str, Any],
        date_str: Optional[str] = None,
    ) -> bool:
        """
        Save an analysis result to history.

        Args:
            group_id: The group identifier
            result: Analysis result dictionary
            date_str: Date string (defaults to today)

        Returns:
            True if saved successfully
        """
        try:
            date_str = date_str or datetime.now().strftime("%Y-%m-%d")
            history = self.load_group_history(group_id)

            # Add timestamp if not present
            if "timestamp" not in result:
                result["timestamp"] = datetime.now().isoformat()

            # Store by date
            if "daily" not in history:
                history["daily"] = {}

            history["daily"][date_str] = result
            history["last_updated"] = datetime.now().isoformat()

            # Write to file
            history_path = self._get_group_history_path(group_id)
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved analysis result for group {group_id} on {date_str}")
            return True

        except Exception as e:
            logger.error(f"Failed to save analysis result: {e}")
            return False

    def load_group_history(self, group_id: str) -> Dict[str, Any]:
        """
        Load history for a group.

        Args:
            group_id: The group identifier

        Returns:
            History dictionary
        """
        try:
            history_path = self._get_group_history_path(group_id)
            if history_path.exists():
                with open(history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"daily": {}, "group_id": group_id}
        except Exception as e:
            logger.error(f"Failed to load group history: {e}")
            return {"daily": {}, "group_id": group_id}

    def get_analysis_result(
        self, group_id: str, date_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get analysis result for a specific date.

        Args:
            group_id: The group identifier
            date_str: Date string (YYYY-MM-DD format)

        Returns:
            Analysis result or None if not found
        """
        history = self.load_group_history(group_id)
        return history.get("daily", {}).get(date_str)

    def get_recent_results(
        self, group_id: str, limit: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get recent analysis results.

        Args:
            group_id: The group identifier
            limit: Maximum number of results to return

        Returns:
            List of recent analysis results
        """
        history = self.load_group_history(group_id)
        daily = history.get("daily", {})

        # Sort by date descending
        sorted_dates = sorted(daily.keys(), reverse=True)[:limit]
        return [daily[date] for date in sorted_dates]

    def has_analysis_for_date(self, group_id: str, date_str: str) -> bool:
        """
        Check if analysis exists for a specific date.

        Args:
            group_id: The group identifier
            date_str: Date string (YYYY-MM-DD format)

        Returns:
            True if analysis exists
        """
        result = self.get_analysis_result(group_id, date_str)
        return result is not None

    def delete_old_history(self, group_id: str, keep_days: int = 30) -> int:
        """
        Delete history older than specified days.

        Args:
            group_id: The group identifier
            keep_days: Number of days of history to keep

        Returns:
            Number of entries deleted
        """
        try:
            history = self.load_group_history(group_id)
            daily = history.get("daily", {})

            cutoff_date = datetime.now().strftime("%Y-%m-%d")
            # Calculate cutoff (simple string comparison works for YYYY-MM-DD format)
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")

            # Find dates to delete
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
            logger.error(f"Failed to delete old history: {e}")
            return 0

    def list_groups_with_history(self) -> List[str]:
        """
        List all groups that have history.

        Returns:
            List of group IDs
        """
        try:
            groups = []
            for file_path in self.history_dir.glob("group_*.json"):
                group_id = file_path.stem.replace("group_", "")
                groups.append(group_id)
            return groups
        except Exception as e:
            logger.error(f"Failed to list groups: {e}")
            return []
