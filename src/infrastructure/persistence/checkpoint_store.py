"""
阶段 Checkpoint 缓存仓储 - 支持分析子阶段产物缓存与局部断点续跑 (Partial Resume)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class CheckpointStore:
    """阶段 Checkpoint 存储器，用于在子阶段失败时实现秒级局部重试并节省 Token"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stage_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    date_str TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expire_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chk_group_date ON stage_checkpoints(group_id, date_str);"
            )

    def save_checkpoint(
        self,
        group_id: str,
        date_str: str,
        stage_name: str,
        data: Any,
        ttl_seconds: int = 86400 * 30,
    ) -> None:
        """保存阶段产物快照（默认与 Trace 保留期对齐，保留 30 天）"""
        checkpoint_id = f"{group_id}_{date_str}_{stage_name}"
        now = time.time()
        expire_at = now + ttl_seconds

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO stage_checkpoints (
                    checkpoint_id, group_id, date_str, stage_name, data_json, created_at, expire_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(checkpoint_id) DO UPDATE SET
                    data_json=excluded.data_json,
                    created_at=excluded.created_at,
                    expire_at=excluded.expire_at;
                """,
                (
                    checkpoint_id,
                    str(group_id),
                    str(date_str),
                    stage_name,
                    json.dumps(data, ensure_ascii=False),
                    now,
                    expire_at,
                ),
            )

    def get_checkpoint(
        self, group_id: str, date_str: str, stage_name: str
    ) -> Any | None:
        """读取有效的阶段产物快照（若已过期则返回 None 并删除）"""
        checkpoint_id = f"{group_id}_{date_str}_{stage_name}"
        now = time.time()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM stage_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
            if not row:
                return None

            if row["expire_at"] < now:
                conn.execute(
                    "DELETE FROM stage_checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                return None

            try:
                return json.loads(row["data_json"])
            except Exception:
                return None

    def clear_checkpoints(self, group_id: str, date_str: str) -> None:
        """任务全部成功后清理该群当天的临时 Checkpoint。

        Args:
            group_id: 群号。
            date_str: 日期字符串。
        """
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM stage_checkpoints WHERE group_id = ? AND date_str = ?",
                (str(group_id), str(date_str)),
            )

    def get_checkpoints_by_group_date(
        self, group_id: str, date_str: str
    ) -> list[dict[str, Any]]:
        """获取指定群在指定日期的所有有效 Checkpoint 快照摘要列表。

        Args:
            group_id: 群号。
            date_str: 日期字符串（YYYY-MM-DD）。

        Returns:
            list[dict[str, Any]]: Checkpoint 摘要元数据列表。
        """
        now = time.time()
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT checkpoint_id, group_id, date_str, stage_name, created_at, expire_at, LENGTH(data_json) as data_size
                FROM stage_checkpoints
                WHERE group_id = ? AND date_str = ? AND expire_at >= ?
                ORDER BY created_at ASC
                """,
                (str(group_id), str(date_str), now),
            ).fetchall()
            return [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "group_id": row["group_id"],
                    "date_str": row["date_str"],
                    "stage_name": row["stage_name"],
                    "created_at": row["created_at"],
                    "expire_at": row["expire_at"],
                    "data_size": row["data_size"],
                }
                for row in rows
            ]

    def delete_checkpoint(self, group_id: str, date_str: str, stage_name: str) -> bool:
        """单点删除指定群在指定日期的特定阶段 Checkpoint。

        Args:
            group_id: 群号。
            date_str: 日期字符串（YYYY-MM-DD）。
            stage_name: 阶段名称。

        Returns:
            bool: 是否成功删除。
        """
        checkpoint_id = f"{group_id}_{date_str}_{stage_name}"
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM stage_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            return cursor.rowcount > 0

    def list_all_checkpoints(
        self,
        limit: int = 50,
        offset: int = 0,
        group_id: str | None = None,
        date_str: str | None = None,
        stage_name: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """多维条件分页查询有效 Checkpoint 列表。

        Args:
            limit: 分页数量限制。
            offset: 偏移量。
            group_id: 可选群号筛选。
            date_str: 可选日期筛选。
            stage_name: 可选阶段筛选。

        Returns:
            tuple[list[dict[str, Any]], int]: Checkpoint 列表与总数。
        """
        now = time.time()
        conditions = ["expire_at >= ?"]
        params: list[Any] = [now]

        if group_id:
            conditions.append("group_id = ?")
            params.append(str(group_id))
        if date_str:
            conditions.append("date_str = ?")
            params.append(str(date_str))
        if stage_name:
            conditions.append("stage_name = ?")
            params.append(str(stage_name))

        where_clause = " AND ".join(conditions)

        with self._get_connection() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) as total FROM stage_checkpoints WHERE {where_clause}",
                params,
            ).fetchone()
            total = count_row["total"] if count_row else 0

            query_sql = f"""
                SELECT checkpoint_id, group_id, date_str, stage_name, created_at, expire_at, LENGTH(data_json) as data_size
                FROM stage_checkpoints
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, params + [limit, offset]).fetchall()
            items = [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "group_id": row["group_id"],
                    "date_str": row["date_str"],
                    "stage_name": row["stage_name"],
                    "created_at": row["created_at"],
                    "created_at_formatted": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(row["created_at"])
                    ),
                    "expire_at": row["expire_at"],
                    "data_size": row["data_size"],
                    "data_size_bytes": row["data_size"],
                }
                for row in rows
            ]
            return items, total

    def get_checkpoint_detail(
        self, group_id: str, date_str: str, stage_name: str
    ) -> dict[str, Any] | None:
        """获取单个 Checkpoint 的元数据及反序列化后的产物 JSON。

        Args:
            group_id: 群号。
            date_str: 日期字符串。
            stage_name: 阶段名称。

        Returns:
            dict[str, Any] | None: 包含 metadata 和 data 的字典，不存在或过期返回 None。
        """
        checkpoint_id = f"{group_id}_{date_str}_{stage_name}"
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM stage_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
            if not row or row["expire_at"] < now:
                return None
            try:
                data = json.loads(row["data_json"])
            except Exception:
                data = row["data_json"]

            return {
                "checkpoint_id": row["checkpoint_id"],
                "group_id": row["group_id"],
                "date_str": row["date_str"],
                "stage_name": row["stage_name"],
                "created_at": row["created_at"],
                "created_at_formatted": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row["created_at"])
                ),
                "expire_at": row["expire_at"],
                "checkpoint_data": data,
                "data": data,
                "data_size": len(row["data_json"]),
                "data_size_bytes": len(row["data_json"]),
            }

    def get_distinct_checkpoint_groups(self) -> list[str]:
        """获取所有拥有有效 Checkpoint 记录的群号列表。

        Returns:
            list[str]: 去重群号列表。
        """
        now = time.time()
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT group_id FROM stage_checkpoints WHERE expire_at >= ? ORDER BY group_id ASC",
                (now,),
            ).fetchall()
            return [str(row["group_id"]) for row in rows if row["group_id"]]

    def cleanup_expired(self) -> int:
        """清理所有已过期的 Checkpoint。

        Returns:
            int: 清理的过期记录数。
        """
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM stage_checkpoints WHERE expire_at < ?", (now,)
            )
            return cursor.rowcount
