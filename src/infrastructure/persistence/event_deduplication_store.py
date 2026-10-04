"""基于 SQLite WAL 模式的事件持久化去重仓储。

在机器人重启跨度内提供轻量可靠的消息事件去重能力，杜绝 Webhook 重放重复入库。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ...utils.logger import logger


class EventDeduplicationStore:
    """基于 SQLite WAL 模式的消息事件去重仓储。

    维护已处理事件标识符的本地持久化记录，在进程重启与崩溃恢复后
    提供历史记忆预热，防止 Webhook 或网关断线重放造成消息重复持久化。
    """

    def __init__(self, db_path: Path) -> None:
        """初始化事件去重持久化仓储。

        Args:
            db_path: SQLite 数据库文件的存储路径。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取启用了 WAL 模式的 SQLite 数据库连接。

        Returns:
            sqlite3.Connection: 配置好的数据库连接对象。
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        """初始化去重数据表与时间戳索引。"""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_dedup (
                    dedup_key TEXT PRIMARY KEY,
                    created_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_event_dedup_created_at
                ON event_dedup(created_at);
                """
            )

    def try_claim(self, dedup_key: str) -> bool:
        """原子尝试预占去重键（基于 SQLite 唯一主键冲突拦截）。

        提供进程级与并发原子预占，杜绝查询与写入间隙导致的重复入库。

        Args:
            dedup_key: 包含平台 ID、群组 ID 与事件消息 ID 的唯一标识键。

        Returns:
            bool: 若预占成功（新记录成功写入）返回 True；若已存在则返回 False。
        """
        if not dedup_key:
            return False
        now_ts = time.time()
        for attempt in range(2):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO event_dedup (dedup_key, created_at)
                        VALUES (?, ?)
                        ON CONFLICT(dedup_key) DO NOTHING;
                        """,
                        (dedup_key, now_ts),
                    )
                    return cursor.rowcount > 0
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt == 0:
                    time.sleep(0.05)
                    continue
                logger.warning(
                    "[事件去重] 尝试原子预占去重键锁超时 %s: %s", dedup_key, exc
                )
                return False
            except Exception as exc:
                logger.warning("[事件去重] 原子预占去重键失败 %s: %s", dedup_key, exc)
                return False
        return False

    def release(self, dedup_key: str) -> None:
        """释放已预占的去重键（持久化失败时回滚释放）。

        Args:
            dedup_key: 包含平台 ID、群组 ID 与事件消息 ID 的唯一标识键。
        """
        if not dedup_key:
            return
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM event_dedup WHERE dedup_key = ?;",
                    (dedup_key,),
                )
        except Exception as exc:
            logger.warning("[事件去重] 释放去重键失败 %s: %s", dedup_key, exc)

    def is_seen(self, dedup_key: str) -> bool:
        """检查指定的去重键是否已被记录。

        Args:
            dedup_key: 包含平台 ID、群组 ID 与事件消息 ID 的唯一标识键。

        Returns:
            bool: 若已存在记录返回 True，否则返回 False。
        """
        if not dedup_key:
            return False
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM event_dedup WHERE dedup_key = ? LIMIT 1;",
                    (dedup_key,),
                )
                return cursor.fetchone() is not None
        except Exception as exc:
            logger.warning("[事件去重] 查询去重键失败 %s: %s", dedup_key, exc)
            return False

    def record(self, dedup_key: str) -> None:
        """记录已处理的去重键。

        Args:
            dedup_key: 包含平台 ID、群组 ID 与事件消息 ID 的唯一标识键。
        """
        if not dedup_key:
            return
        now_ts = time.time()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_dedup (dedup_key, created_at)
                    VALUES (?, ?);
                    """,
                    (dedup_key, now_ts),
                )
        except Exception as exc:
            logger.warning("[事件去重] 写入去重键失败 %s: %s", dedup_key, exc)

    def load_recent_keys(self, limit: int = 4096) -> list[str]:
        """按时间倒序加载最近记录的去重键，用于启动时预热内存缓存。

        Args:
            limit: 允许加载的最大记录条数。

        Returns:
            list[str]: 最近记录的去重键列表。
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT dedup_key FROM event_dedup
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
                return [str(row["dedup_key"]) for row in cursor.fetchall()]
        except Exception as exc:
            logger.warning("[事件去重] 加载最近历史去重键失败: %s", exc)
            return []

    def prune_older_than(self, days: int = 7) -> int:
        """清理早于指定保留天数的历史过期去重记录。

        Args:
            days: 数据保留窗口天数。

        Returns:
            int: 成功清理的过期记录数量。
        """
        cutoff_ts = time.time() - (days * 86400)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM event_dedup WHERE created_at < ?;",
                    (cutoff_ts,),
                )
                deleted = cursor.rowcount
                if deleted > 0:
                    logger.info(
                        "[事件去重] 已清理 %d 条过期去重记录",
                        deleted,
                    )
                return deleted
        except Exception as exc:
            logger.warning("[事件去重] 清理过期记录异常: %s", exc)
            return 0

    def close(self) -> None:
        """释放存储资源。"""
        # SQLite 连接通过上下文管理器按需创建与释放。
