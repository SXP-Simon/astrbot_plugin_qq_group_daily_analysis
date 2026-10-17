"""与日报快照隔离的词云统计及发送记录。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...domain.value_objects.wordcloud import WordCloudData

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class WordCloudSnapshot:
    """供预览读取的持久化统计，不改变发送状态。"""

    id: str
    umo: str
    updated_at: float
    data: WordCloudData


class WordCloudStore:
    """保存完整词频和发送状态，支持仅重试词云。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS wordcloud_delivery (
                umo TEXT NOT NULL, fingerprint TEXT NOT NULL, data_json TEXT NOT NULL,
                status TEXT NOT NULL, error TEXT NOT NULL, updated_at REAL NOT NULL,
                PRIMARY KEY (umo, fingerprint))""")
            conn.execute(
                "DELETE FROM wordcloud_delivery WHERE updated_at < ?",
                (time.time() - 30 * 86400,),
            )

    def save(
        self,
        umo: str,
        fingerprint: str,
        data: WordCloudData,
        status: str,
        error: str = "",
    ) -> None:
        """独立记录统计及发送结果，不触碰日报游标。"""
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO wordcloud_delivery VALUES (?, ?, ?, ?, ?, ?)",
                (
                    umo,
                    fingerprint,
                    json.dumps(data.to_dict(), ensure_ascii=False),
                    status,
                    error,
                    time.time(),
                ),
            )

    def is_sent(self, umo: str, fingerprint: str) -> bool:
        """判断当前统计快照是否已成功发送。"""
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT status FROM wordcloud_delivery WHERE umo=? AND fingerprint=?",
                (umo, fingerprint),
            ).fetchone()
        return row is not None and row[0] == "sent"

    def latest(self, umo: str) -> WordCloudData | None:
        """恢复最近一次词频，用当前外观重绘而无需重新拉取消息。"""
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT data_json FROM wordcloud_delivery WHERE umo=? ORDER BY updated_at DESC LIMIT 1",
                (umo,),
            ).fetchone()
        return WordCloudData.from_dict(json.loads(row[0])) if row else None

    @staticmethod
    def _snapshot(row: tuple[int, str, str, float]) -> WordCloudSnapshot:
        """从查询结果恢复快照，标识绑定行号和内容以识别过期选择。"""
        row_id, umo, serialized, updated_at = row
        raw: object = json.loads(serialized)
        if not isinstance(raw, dict):
            raise ValueError("词云缓存格式无效")
        digest = hashlib.sha256(
            f"{umo}\0{updated_at}\0{serialized}".encode()
        ).hexdigest()[:16]
        return WordCloudSnapshot(
            id=f"{row_id:x}.{digest}",
            umo=umo,
            updated_at=updated_at,
            data=WordCloudData.from_dict(raw),
        )

    def list_snapshots(self) -> list[WordCloudSnapshot]:
        """只读列出每个群最近一次统计，保留原始完整词频。

        Returns:
            三十天内的最近群快照；损坏的单条缓存不影响其他群。
        """
        with sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=ro", uri=True
        ) as conn:
            rows = conn.execute(
                """SELECT rowid, umo, data_json, updated_at
                FROM wordcloud_delivery AS current
                WHERE updated_at >= ? AND rowid = (
                    SELECT rowid FROM wordcloud_delivery AS candidate
                    WHERE candidate.umo = current.umo
                    ORDER BY candidate.updated_at DESC, candidate.rowid DESC LIMIT 1
                ) ORDER BY updated_at DESC, rowid DESC""",
                (time.time() - 30 * 86400,),
            ).fetchall()
        snapshots: list[WordCloudSnapshot] = []
        for row in rows:
            try:
                snapshots.append(self._snapshot(row))
            except (ValueError, TypeError):
                continue
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> WordCloudSnapshot | None:
        """按版本标识只读恢复缓存，已替换或超过保留期时不返回旧数据。

        Args:
            snapshot_id: 列表接口返回的快照标识。

        Returns:
            仍然存在且版本一致的缓存，或空值。

        Raises:
            ValueError: 快照标识格式无效。
        """
        if not re.fullmatch(r"[a-f0-9]{1,16}\.[a-f0-9]{16}", snapshot_id):
            raise ValueError("词云快照标识无效")
        row_id = int(snapshot_id.partition(".")[0], 16)
        if row_id > 2**63 - 1:
            raise ValueError("词云快照标识无效")
        with sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=ro", uri=True
        ) as conn:
            row = conn.execute(
                """SELECT rowid, umo, data_json, updated_at FROM wordcloud_delivery
                WHERE rowid = ? AND updated_at >= ?""",
                (row_id, time.time() - 30 * 86400),
            ).fetchone()
        if row is None:
            return None
        try:
            snapshot = self._snapshot(row)
        except (ValueError, TypeError):
            return None
        return snapshot if snapshot.id == snapshot_id else None
