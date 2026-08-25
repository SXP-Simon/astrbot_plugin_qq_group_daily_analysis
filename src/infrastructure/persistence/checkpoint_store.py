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
        """任务全部成功后清理该群当天的临时 Checkpoint"""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM stage_checkpoints WHERE group_id = ? AND date_str = ?",
                (str(group_id), str(date_str)),
            )

    def cleanup_expired(self) -> int:
        """清理所有已过期的 Checkpoint"""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM stage_checkpoints WHERE expire_at < ?", (now,)
            )
            return cursor.rowcount
