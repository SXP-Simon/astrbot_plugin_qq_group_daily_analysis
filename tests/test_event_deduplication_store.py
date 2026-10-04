"""事件去重仓储单元测试。"""

from __future__ import annotations

import time
from pathlib import Path

from src.infrastructure.persistence.event_deduplication_store import (
    EventDeduplicationStore,
)


def test_event_deduplication_store_init_and_table_creation(tmp_path: Path):
    """测试 SQLite WAL 模式数据库与去重数据表的自动创建。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    assert db_file.exists()
    assert store.is_seen("non-existent-key") is False
    store.close()


def test_event_deduplication_store_record_and_is_seen(tmp_path: Path):
    """测试记录并查询去重键的有效性与幂等覆盖。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    key1 = "telegram:group-1:1001"
    key2 = "satori:group-2:msg-xyz"

    assert store.is_seen(key1) is False
    assert store.is_seen(key2) is False

    store.record(key1)
    assert store.is_seen(key1) is True
    assert store.is_seen(key2) is False

    store.record(key2)
    assert store.is_seen(key1) is True
    assert store.is_seen(key2) is True

    # 重复记录已存在的键不应报错（幂等替换）
    store.record(key1)
    assert store.is_seen(key1) is True

    store.close()


def test_event_deduplication_store_load_recent_keys_ordering(tmp_path: Path):
    """测试加载最近历史键时按插入时间倒序排列。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    keys = [f"platform:group:{i}" for i in range(10)]
    for key in keys:
        store.record(key)
        time.sleep(0.002)

    loaded = store.load_recent_keys(limit=5)
    assert len(loaded) == 5
    # 最新插入的记录排在最前
    assert loaded[0] == "platform:group:9"
    assert loaded[1] == "platform:group:8"

    loaded_all = store.load_recent_keys(limit=50)
    assert len(loaded_all) == 10
    assert set(loaded_all) == set(keys)

    store.close()


def test_event_deduplication_store_prune_older_than(tmp_path: Path):
    """测试清理早于保留天数的过期记录。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    store.record("recent-key")

    # 手动插入 8 天前的老数据
    old_time = time.time() - (8 * 86400)
    with store._get_connection() as conn:
        conn.execute(
            "INSERT INTO event_dedup (dedup_key, created_at) VALUES (?, ?);",
            ("old-key", old_time),
        )

    assert store.is_seen("recent-key") is True
    assert store.is_seen("old-key") is True

    deleted = store.prune_older_than(days=7)
    assert deleted == 1

    assert store.is_seen("recent-key") is True
    assert store.is_seen("old-key") is False

    store.close()


def test_event_deduplication_store_handles_empty_and_invalid_keys(tmp_path: Path):
    """测试空键或无效输入的边界容错。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    assert store.is_seen("") is False
    assert store.try_claim("") is False
    store.record("")
    store.release("")
    assert store.is_seen("") is False

    store.close()


def test_event_deduplication_store_try_claim_and_release(tmp_path: Path):
    """测试原子 try_claim 预占拦截与 release 回滚释放。"""
    db_file = tmp_path / "test_dedup.db"
    store = EventDeduplicationStore(db_file)

    key = "tg:group-1:msg-1"

    # 首次预占成功
    assert store.try_claim(key) is True
    assert store.is_seen(key) is True

    # 再次并发预占被原子拦截
    assert store.try_claim(key) is False

    # 回滚释放后可再次预占
    store.release(key)
    assert store.is_seen(key) is False
    assert store.try_claim(key) is True

    store.close()
