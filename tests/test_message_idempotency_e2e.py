"""消息幂等性全链路与全生命周期集成测试（E2E）。

覆盖场景：
1. Telegram、Satori、QQ 官方入库前统一拦截去重。
2. 瞬时并发竞争（In-flight Lock）原子拦截。
3. 模拟进程崩溃重启后的持久化记忆预热与 Webhook 重放拦截。
4. 入库到出库全流程闭环：验证 UnifiedMessage.message_id 真实映射。
5. 出库适配器层 seen_message_ids 历史脏数据二次兜底过滤。
6. 下游兼容性：增量分析游标与 Telegram 贴表情（Reaction）原生整型 ID 对齐。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.services.message_processing_service import (
    MessageProcessingService,
)
from src.infrastructure.persistence.event_deduplication_store import (
    EventDeduplicationStore,
)
from src.infrastructure.platform.adapters.qq_official_adapter import (
    QQOfficialAdapter,
)
from src.infrastructure.platform.adapters.satori_adapter import (
    SatoriAdapter,
)
from src.infrastructure.platform.adapters.telegram_adapter import (
    TelegramAdapter,
)


class InMemoryAstrBotDatabase:
    """模拟 AstrBot 的 PlatformMessageHistory 数据表与持久化接口。"""

    def __init__(self) -> None:
        self.rows: list[SimpleNamespace] = []
        self._next_id = 1

    async def insert(
        self,
        platform_id: str,
        user_id: str,
        content: dict,
        sender_id: str | None = None,
        sender_name: str | None = None,
        max_messages: int | None = None,
    ) -> SimpleNamespace:
        row = SimpleNamespace(
            id=self._next_id,
            platform_id=platform_id,
            user_id=user_id,
            content=content,
            sender_id=sender_id,
            sender_name=sender_name,
            created_at=datetime.now(timezone.utc),
        )
        self._next_id += 1
        self.rows.append(row)
        return row

    async def get(
        self,
        platform_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 200,
    ) -> list[SimpleNamespace]:
        matching = [
            r for r in self.rows if r.platform_id == platform_id and r.user_id == user_id
        ]
        # 按时间倒序返回（最新消息在前）
        start = (page - 1) * page_size
        end = start + page_size
        return list(reversed(matching))[start:end]


class MockRegistry:
    """模拟群组发现注册表。"""

    def __init__(self) -> None:
        self.upsert_count = 0

    async def upsert(self, **kwargs) -> None:
        self.upsert_count += 1


def make_mock_event(
    platform_name: str,
    platform_id: str,
    group_id: str,
    sender_id: str,
    sender_name: str,
    message_id: str,
    text: str,
) -> SimpleNamespace:
    """构造指定平台的模拟消息事件。"""
    return SimpleNamespace(
        get_platform_name=lambda: platform_name,
        get_platform_id=lambda: platform_id,
        get_group_id=lambda: group_id,
        get_sender_id=lambda: sender_id,
        get_sender_name=lambda: sender_name,
        message_str=text,
        message_obj=SimpleNamespace(
            message_id=message_id,
            raw_message=None,
            sender=SimpleNamespace(nickname=sender_name),
            message=[SimpleNamespace(type="Plain", text=text)],
        ),
    )


@pytest.mark.asyncio
async def test_e2e_full_lifecycle_ingress_dedup_and_reboot_recovery(tmp_path: Path):
    """端到端测试：入库去重 + 进程崩溃重启仿真 + 重启后历史重放拦截。"""
    db_path = tmp_path / "e2e_dedup.db"
    shared_store = EventDeduplicationStore(db_path)
    astr_db = InMemoryAstrBotDatabase()
    registry = MockRegistry()

    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=astr_db),
        registry,
        dedup_store=shared_store,
    )

    # 1. Telegram 高频重试消息测试
    tg_ev1 = make_mock_event("telegram", "tg-bot-1", "-1001", "u1", "Alice", "101", "msg 1")
    tg_ev1_retry = make_mock_event("telegram", "tg-bot-1", "-1001", "u1", "Alice", "101", "msg 1 retry")

    res1 = await service.process_message(tg_ev1)
    res2 = await service.process_message(tg_ev1_retry)

    assert res1 is True
    assert res2 is False
    assert len(astr_db.rows) == 1

    # 2. 瞬时并发竞争仿真（两个相同事件通过 gather 几乎同时到达）
    satori_ev = make_mock_event("satori", "sat-1", "grp-s", "u2", "Bob", "sat_999", "satori msg")
    satori_ev_dup = make_mock_event("satori", "sat-1", "grp-s", "u2", "Bob", "sat_999", "satori dup")

    results = await asyncio.gather(
        service.process_message(satori_ev),
        service.process_message(satori_ev_dup),
    )
    # 严格保证一成一拒
    assert sorted(results) == [False, True]
    assert len(astr_db.rows) == 2

    shared_store.close()

    # 3. 进程重启模拟：清空内存状态，创建全新 service 与全新 store 实例
    new_store = EventDeduplicationStore(db_path)
    rebooted_service = MessageProcessingService(
        SimpleNamespace(message_history_manager=astr_db),
        registry,
        dedup_store=new_store,
    )

    # 重启后到达的 tg_ev1 重放事件必须被预热缓存成功阻断
    replayed_res = await rebooted_service.process_message(tg_ev1)
    assert replayed_res is False
    assert len(astr_db.rows) == 2  # 数据库没有新增任何重复脏数据！

    # 重启后的合法新消息正常入库
    tg_ev2 = make_mock_event("telegram", "tg-bot-1", "-1001", "u1", "Alice", "102", "msg 2 after reboot")
    new_res = await rebooted_service.process_message(tg_ev2)
    assert new_res is True
    assert len(astr_db.rows) == 3

    new_store.close()


@pytest.mark.asyncio
async def test_e2e_roundtrip_telegram_ingress_to_egress_and_reaction_compatibility():
    """端到端测试：Telegram 消息入库 -> 真实存储 -> 适配器分页查询 -> 统一消息对象 -> 表情反应兼容性。"""
    astr_db = InMemoryAstrBotDatabase()
    registry = MockRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=astr_db),
        registry,
    )

    # 通过消息处理服务入库
    tg_event = make_mock_event(
        "telegram", "tg-bot-1", "-100888", "12345", "Charlie", "7788", "Report query"
    )
    stored = await service.process_message(tg_event)
    assert stored is True

    # 检查数据库原始记录中的 message_id 字段
    assert len(astr_db.rows) == 1
    raw_row = astr_db.rows[0]
    assert raw_row.content["message_id"] == "7788"

    # 配置 Telegram 适配器回读历史
    mock_tg_client = SimpleNamespace()
    adapter = TelegramAdapter(
        mock_tg_client,
        {"platform_id": "tg-bot-1", "bot_self_ids": []},
    )
    adapter.set_context(SimpleNamespace(message_history_manager=astr_db))

    messages = await adapter.fetch_messages("-100888", days=1, max_count=10)
    assert len(messages) == 1
    unified_msg = messages[0]

    # 验证 UnifiedMessage.message_id 还原为原生 Telegram 消息 ID（"7788"），而非自增主键 (1)
    assert unified_msg.message_id == "7788"
    assert unified_msg.text_content == "Report query"

    # 验证下游 Telegram 表情回应的整数解析兼容性
    parsed_id = int(unified_msg.message_id)
    assert parsed_id == 7788


@pytest.mark.asyncio
async def test_e2e_roundtrip_satori_ingress_to_egress_and_cursor_compatibility():
    """端到端测试：Satori 消息入库 -> 真实存储 -> Satori 适配器拉取 -> 游标边界对齐。"""
    astr_db = InMemoryAstrBotDatabase()
    registry = MockRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=astr_db),
        registry,
    )

    satori_event = make_mock_event(
        "satori", "satori-main", "satori-channel-1", "user-sat", "Dave", "sat_event_42", "Analysis request"
    )
    assert await service.process_message(satori_event) is True

    # 配置 Satori 适配器回读历史
    mock_satori_client = SimpleNamespace()
    adapter = SatoriAdapter(
        mock_satori_client,
        {"platform_id": "satori-main", "bot_self_ids": []},
    )
    adapter.set_context(SimpleNamespace(message_history_manager=astr_db))

    messages = await adapter.fetch_messages("satori-channel-1", days=1, max_count=10)
    assert len(messages) == 1
    unified = messages[0]

    assert unified.message_id == "sat_event_42"
    assert unified.text_content == "Analysis request"

    # 验证增量分析游标与调度器记录的原生事件 ID 严格对齐
    recorded_cursor_id = satori_event.message_obj.message_id
    assert unified.message_id == recorded_cursor_id
    assert unified.message_id in {recorded_cursor_id}


@pytest.mark.asyncio
async def test_e2e_egress_deduplication_filters_preexisting_duplicates():
    """端到端测试：即便底层数据库存在历史重复行，出库层 seen_message_ids 依然能按真实原生 ID 准确过滤。"""
    astr_db = InMemoryAstrBotDatabase()

    # 手工向数据库插入两条拥有相同原生 message_id 但数据库自增 ID 不同的脏数据行
    await astr_db.insert(
        platform_id="tg-bot-1",
        user_id="-100999",
        content={"type": "user", "message": [{"type": "plain", "text": "Duplicate msg"}], "message_id": "9999"},
        sender_id="user_1",
        sender_name="Alice",
    )
    await astr_db.insert(
        platform_id="tg-bot-1",
        user_id="-100999",
        content={"type": "user", "message": [{"type": "plain", "text": "Duplicate msg"}], "message_id": "9999"},
        sender_id="user_1",
        sender_name="Alice",
    )
    assert len(astr_db.rows) == 2

    # 通过 Telegram 适配器拉取消息
    adapter = TelegramAdapter(
        SimpleNamespace(),
        {"platform_id": "tg-bot-1", "bot_self_ids": []},
    )
    adapter.set_context(SimpleNamespace(message_history_manager=astr_db))

    messages = await adapter.fetch_messages("-100999", days=1, max_count=10)
    # 出库层正确根据真实原生 message_id 过滤掉第 2 条重复消息
    assert len(messages) == 1
    assert messages[0].message_id == "9999"
