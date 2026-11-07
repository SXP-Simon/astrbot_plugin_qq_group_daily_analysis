"""增量会话隔离及旧数据一次接管的仓储回归。"""

import asyncio
from copy import deepcopy

import pytest

from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.value_objects.incremental_session import IncrementalSession
from src.infrastructure.persistence.incremental_store import IncrementalStore


class MemoryStar:
    def __init__(self):
        self.data = {}
        self.fail_index = False

    async def get_kv_data(self, key, default=None):
        await asyncio.sleep(0)
        return deepcopy(self.data.get(key, default))

    async def put_kv_data(self, key, value):
        await asyncio.sleep(0)
        if self.fail_index and key.startswith("v2_incr_batch_index_"):
            self.fail_index = False
            raise OSError("模拟迁移索引写入失败")
        self.data[key] = deepcopy(value)


@pytest.mark.asyncio
async def test_same_group_and_batch_id_have_independent_batches_cursors_and_reset():
    root = IncrementalStore(MemoryStar())
    first = await root.for_session("123", "telegram-main")
    second = await root.for_session("123", "onebot-main")
    for store, count in [(first, 10), (second, 20)]:
        assert await store.save_batch(IncrementalBatch(group_id="123", batch_id="same", timestamp=100, messages_count=count))
        await store.update_last_analyzed_cursor("123", count, {str(count)})
    assert (await first.list_batch_page("123")).items[0]["messages_count"] == 10
    assert (await second.query_batches("123", 0, 200))[0].messages_count == 20
    assert await first.get_last_analyzed_cursor("123") == (10, {"10"})
    assert await second.get_last_analyzed_cursor("123") == (20, {"20"})
    assert await second.reset_group("123") == 1
    assert await first.get_batch_count("123") == 1
    assert await second.get_last_analyzed_cursor("123") == (0, set())
    assert await first.delete_batch("123", "same") is True
    assert await second.get_batch_count("123") == 0
    assert await first.get_last_analyzed_cursor("123") == (10, {"10"})
    with pytest.raises(ValueError, match="目标群号"):
        await first.save_batch(IncrementalBatch(group_id="other"))


@pytest.mark.asyncio
async def test_legacy_data_is_claimed_once_and_original_keys_remain_as_backup():
    star = MemoryStar()
    root = IncrementalStore(star)
    assert await root.save_batch(IncrementalBatch(group_id="123", batch_id="legacy", messages_count=7))
    await root.update_last_analyzed_cursor("123", 1234, {"old-message"})
    first = await root.for_session("123", "telegram-main")
    assert (await first.get_batch_detail("123", "legacy")).messages_count == 7
    assert await first.get_last_analyzed_cursor("123") == (1234, {"old-message"})
    second = await root.for_session("123", "onebot-main")
    assert await second.get_batch_count("123") == 0
    assert await second.get_last_analyzed_cursor("123") == (0, set())
    assert star.data["incr_batch_123_legacy"]["messages_count"] == 7
    with pytest.raises(ValueError, match="指定平台"):
        await root.get_batch_detail("123", "legacy")
    assert await root.get_tracked_sessions() == [IncrementalSession("onebot-main", "123"), IncrementalSession("telegram-main", "123")]


@pytest.mark.asyncio
async def test_failed_migration_can_retry_without_losing_old_data_or_claiming_owner():
    star = MemoryStar()
    root = IncrementalStore(star)
    await root.save_batch(IncrementalBatch(group_id="123", batch_id="legacy"))
    star.fail_index = True
    with pytest.raises(OSError):
        await root.for_session("123", "telegram-main")
    assert await root.get_batch_count("123") == 1
    assert not star.data.get(root._legacy_owner_key("123"))
    scoped = await root.for_session("123", "telegram-main")
    assert await scoped.get_batch_count("123") == 1
    assert await (await root.for_session("123", "telegram-main")).get_batch_count("123") == 1


@pytest.mark.asyncio
async def test_concurrent_sessions_do_not_lose_registry_entries():
    root = IncrementalStore(MemoryStar())
    await asyncio.gather(*(root.for_session(group, platform) for group in ("123", "456") for platform in ("first", "second")))
    assert set(await root.get_tracked_sessions()) == {IncrementalSession(platform, group) for group in ("123", "456") for platform in ("first", "second")}


@pytest.mark.asyncio
@pytest.mark.parametrize("broken", [[{"timestamp": 1}], "not-an-index"])
async def test_malformed_legacy_index_is_not_claimed_as_empty(broken):
    star = MemoryStar()
    star.data["incr_batch_index_123"] = broken
    root = IncrementalStore(star)
    with pytest.raises(ValueError, match="迁移未完成"):
        await root.for_session("123", "first")
    assert not star.data.get(root._legacy_owner_key("123"))


@pytest.mark.asyncio
async def test_registry_failure_after_copy_does_not_duplicate_legacy_into_second_platform():
    star = MemoryStar()
    root = IncrementalStore(star)
    await root.save_batch(IncrementalBatch(group_id="123", batch_id="legacy"))
    write = star.put_kv_data
    async def failing_write(key, value):
        if key == "incr_tracked_sessions_v2":
            raise OSError("模拟会话目录写入失败")
        await write(key, value)
    star.put_kv_data = failing_write
    with pytest.raises(RuntimeError, match="目录"):
        await root.for_session("123", "first")
    assert await root.get_tracked_sessions() == [IncrementalSession("first", "123")]
    star.put_kv_data = write
    second = await root.for_session("123", "second")
    assert await second.get_batch_count("123") == 0
    first = await root.for_session("123", "first")
    assert await first.get_batch_count("123") == 1
    await first.reset_group("123")
    assert await (await root.for_session("123", "first")).get_batch_count("123") == 0
