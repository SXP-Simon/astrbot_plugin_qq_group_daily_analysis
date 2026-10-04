import asyncio
from types import SimpleNamespace

import pytest

from src.application.services.message_processing_service import (
    MessageProcessingService,
)


class FakeHistoryManager:
    def __init__(self):
        self.insert_calls = 0

    async def insert(self, **kwargs):
        self.insert_calls += 1
        if self.insert_calls == 1:
            raise RuntimeError("temporary database failure")


class RecordingHistoryManager:
    def __init__(self):
        self.calls = []

    async def insert(self, **kwargs):
        self.calls.append(kwargs)


class LegacyRecordingHistoryManager:
    """模拟 AstrBot 4.26.x 不支持 max_messages 的历史管理器。"""

    def __init__(self):
        self.calls = []

    async def insert(
        self,
        platform_id,
        user_id,
        content,
        sender_id=None,
        sender_name=None,
    ):
        self.calls.append(
            {
                "platform_id": platform_id,
                "user_id": user_id,
                "content": content,
                "sender_id": sender_id,
                "sender_name": sender_name,
            }
        )


class FakeGroupRegistry:
    def __init__(self):
        self.upsert_calls = 0

    async def upsert(self, **kwargs):
        self.upsert_calls += 1


class FakeOfficialEvent:
    def __init__(
        self,
        text="hello",
        mentions=None,
        platform_name="qq_official",
        at_target=None,
    ):
        self.platform_name = platform_name
        message = []
        if at_target:
            message.append(SimpleNamespace(type="At", qq=at_target, name=""))
        message.append(SimpleNamespace(type="Plain", text=text))
        self.message_obj = SimpleNamespace(
            message_id="OFFICIAL-MSG-1",
            raw_message=SimpleNamespace(
                timestamp=1710000000,
                mentions=list(mentions or []),
            ),
            sender=SimpleNamespace(nickname=""),
            message=message,
        )
        self.message_str = text

    def get_group_id(self):
        return "GROUP_OPENID"

    def get_sender_id(self):
        return "MEMBER_OPENID"

    def get_sender_name(self):
        return ""

    def get_platform_id(self):
        return "official-main"

    def get_platform_name(self):
        return self.platform_name


def test_failed_history_insert_releases_official_message_id():
    history_manager = FakeHistoryManager()
    registry = FakeGroupRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), registry
    )
    event = FakeOfficialEvent()

    with pytest.raises(RuntimeError, match="temporary database failure"):
        asyncio.run(service.process_message(event))

    asyncio.run(service.process_message(event))
    asyncio.run(service.process_message(event))

    assert history_manager.insert_calls == 2
    assert registry.upsert_calls == 1


def test_new_qq_official_message_replaces_mentions_before_storage():
    history_manager = RecordingHistoryManager()
    registry = FakeGroupRegistry()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), registry
    )
    event = FakeOfficialEvent(
        text="请问 <@KNOWN_OPENID> 和 <@!UNKNOWN_OPENID> 怎么看",
        mentions=[
            SimpleNamespace(
                id="KNOWN_OPENID",
                username="随风潜入夜",
                is_you=False,
            )
        ],
    )

    assert asyncio.run(service.process_message(event)) is True

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [
        {"type": "plain", "text": "请问 @随风潜入夜 和 @群友 怎么看"}
    ]
    assert "KNOWN_OPENID" not in stored_parts[0]["text"]
    assert "UNKNOWN_OPENID" not in stored_parts[0]["text"]
    assert history_manager.calls[0]["max_messages"] == 10000


def test_legacy_history_manager_retries_without_max_messages():
    """旧版 AstrBot 历史接口不支持上限参数时应自动降级写入。"""
    history_manager = LegacyRecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )

    first_event = FakeOfficialEvent()
    second_event = FakeOfficialEvent(text="second")
    second_event.message_obj.message_id = "OFFICIAL-MSG-2"

    assert asyncio.run(service.process_message(first_event)) is True
    assert asyncio.run(service.process_message(second_event)) is True

    assert len(history_manager.calls) == 2
    assert all("max_messages" not in call for call in history_manager.calls)


def test_qq_official_bot_mention_is_removed_before_storage():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(
        text="<@BOT_OPENID> 帮我问问 <@MEMBER_OPENID>",
        mentions=[
            SimpleNamespace(id="BOT_OPENID", username="机器人", is_you=True),
            SimpleNamespace(
                id="MEMBER_OPENID",
                username="群友甲",
                is_you=False,
            ),
        ],
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [{"type": "plain", "text": "帮我问问 @群友甲"}]


def test_qq_official_message_preserves_internal_line_breaks():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(text="第一行\n\n第二行\t\t结尾")

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [{"type": "plain", "text": "第一行\n\n第二行 结尾"}]


def test_qq_official_at_component_preserves_internal_line_breaks():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(
        text="第一行\n\n第二行",
        mentions=[SimpleNamespace(id="BOT_OPENID", username="机器人", is_you=True)],
        at_target="BOT_OPENID",
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [
        {"type": "at", "target_id": "BOT_OPENID", "name": ""},
        {"type": "plain", "text": "第一行\n\n第二行"},
    ]


def test_non_qq_message_keeps_platform_mention_syntax_unchanged():
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )
    event = FakeOfficialEvent(
        text="请问 <@DISCORD_USER_ID> 怎么看",
        mentions=[
            SimpleNamespace(
                id="DISCORD_USER_ID",
                username="Discord 用户",
                is_you=False,
            )
        ],
        platform_name="discord",
    )

    asyncio.run(service.process_message(event))

    stored_parts = history_manager.calls[0]["content"]["message"]
    assert stored_parts == [{"type": "plain", "text": "请问 <@DISCORD_USER_ID> 怎么看"}]


class FakePlatformEvent:
    """可灵活配置的伪事件对象，支持模拟任意平台与群组。"""

    def __init__(
        self,
        platform_id="tg-platform",
        platform_name="telegram",
        group_id="-100123456",
        sender_id="user_1",
        message_id="1001",
        text="hello",
    ):
        self._platform_id = platform_id
        self._platform_name = platform_name
        self._group_id = group_id
        self._sender_id = sender_id
        self.message_str = text
        self.message_obj = SimpleNamespace(
            message_id=message_id,
            raw_message=None,
            sender=SimpleNamespace(nickname="Alice"),
            message=[SimpleNamespace(type="Plain", text=text)],
        )

    def get_group_id(self):
        return self._group_id

    def get_sender_id(self):
        return self._sender_id

    def get_sender_name(self):
        return "Alice"

    def get_platform_id(self):
        return self._platform_id

    def get_platform_name(self):
        return self._platform_name


def test_telegram_and_satori_messages_are_deduplicated_before_insert():
    """验证非 QQ 官方平台（Telegram、Satori）同样受入库前预占与 LRU 幂等保护。"""
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )

    tg_event_1 = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="-100111",
        message_id="5001",
        text="tg message 1",
    )
    tg_event_dup = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="-100111",
        message_id="5001",
        text="tg message 1 duplicate",
    )

    # 首次 Telegram 消息成功入库
    assert asyncio.run(service.process_message(tg_event_1)) is True
    assert len(history_manager.calls) == 1

    # 重复 Telegram 消息在入库前被直接丢弃拦截
    assert asyncio.run(service.process_message(tg_event_dup)) is False
    assert len(history_manager.calls) == 1

    # Satori 平台同样生效
    satori_event = FakePlatformEvent(
        platform_id="satori-bot",
        platform_name="satori",
        group_id="satori-group",
        message_id="satori-msg-99",
        text="satori message",
    )
    satori_dup = FakePlatformEvent(
        platform_id="satori-bot",
        platform_name="satori",
        group_id="satori-group",
        message_id="satori-msg-99",
        text="satori duplicate",
    )
    assert asyncio.run(service.process_message(satori_event)) is True
    assert len(history_manager.calls) == 2
    assert asyncio.run(service.process_message(satori_dup)) is False
    assert len(history_manager.calls) == 2


def test_namespace_isolation_allows_same_message_id_across_groups_or_platforms():
    """验证去重键引入 platform_id 与 group_id 命名空间，防止跨群或跨平台 ID 碰撞误杀。"""
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )

    # 群 A 与群 B 均有消息编号为 "42" 的消息
    event_group_a = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="group_A",
        message_id="42",
        text="group A msg 42",
    )
    event_group_b = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="group_B",
        message_id="42",
        text="group B msg 42",
    )

    assert asyncio.run(service.process_message(event_group_a)) is True
    assert asyncio.run(service.process_message(event_group_b)) is True
    assert len(history_manager.calls) == 2

    # 不同平台实例但有相同 message_id="42"
    event_platform_c = FakePlatformEvent(
        platform_id="other-bot",
        platform_name="telegram",
        group_id="group_A",
        message_id="42",
        text="platform C msg 42",
    )
    assert asyncio.run(service.process_message(event_platform_c)) is True
    assert len(history_manager.calls) == 3


def test_universal_message_id_is_stored_in_content_for_all_platforms():
    """验证所有平台的持久化 content 均统一固化原生 message_id 字段。"""
    history_manager = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )

    tg_event = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="-100999",
        message_id="TG-777",
        text="text",
    )
    asyncio.run(service.process_message(tg_event))

    call_content = history_manager.calls[0]["content"]
    assert call_content["message_id"] == "TG-777"


def test_persistent_store_reboot_simulation_blocks_replayed_messages(tmp_path):
    """仿真机器人重启：新服务实例从持久化去重仓储预热 LRU，阻断重启后的 Webhook 重放。"""
    from src.infrastructure.persistence.event_deduplication_store import (
        EventDeduplicationStore,
    )

    db_path = tmp_path / "test_reboot_dedup.db"
    store_before_crash = EventDeduplicationStore(db_path)

    history_1 = RecordingHistoryManager()
    service_before_crash = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_1),
        FakeGroupRegistry(),
        dedup_store=store_before_crash,
    )

    event = FakePlatformEvent(
        platform_id="tg-prod",
        platform_name="telegram",
        group_id="-100555",
        message_id="MSG-9999",
        text="hello before reboot",
    )

    # 崩溃前入库正常消息
    assert asyncio.run(service_before_crash.process_message(event)) is True
    assert len(history_1.calls) == 1
    store_before_crash.close()

    # --- 模拟进程重启与内存清空 ---
    store_after_reboot = EventDeduplicationStore(db_path)
    history_2 = RecordingHistoryManager()
    service_after_reboot = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_2),
        FakeGroupRegistry(),
        dedup_store=store_after_reboot,
    )

    # 重启后到达的相同 Webhook 重放事件必须被拦截阻断
    assert asyncio.run(service_after_reboot.process_message(event)) is False
    assert len(history_2.calls) == 0  # 数据库写入数为 0！

    # 重启后到达的全新正常消息不受影响，正常入库
    new_event = FakePlatformEvent(
        platform_id="tg-prod",
        platform_name="telegram",
        group_id="-100555",
        message_id="MSG-10000",
        text="new message after reboot",
    )
    assert asyncio.run(service_after_reboot.process_message(new_event)) is True
    assert len(history_2.calls) == 1

    store_after_reboot.close()


def test_failed_insert_on_telegram_releases_dedup_lock_for_retry():
    """验证非 QQ 平台遭遇临时数据库异常时自动释放预占锁，下游重试可恢复入库。"""
    history_manager = FakeHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history_manager), FakeGroupRegistry()
    )

    event = FakePlatformEvent(
        platform_id="tg-bot",
        platform_name="telegram",
        group_id="-1001",
        message_id="FAIL-THEN-RETRY",
        text="temporary failure test",
    )

    with pytest.raises(RuntimeError, match="temporary database failure"):
        asyncio.run(service.process_message(event))

    # 预占锁已自动回滚释放，首次重试应当成功入库
    assert asyncio.run(service.process_message(event)) is True
    assert history_manager.insert_calls == 2

    # 第二次重试命中成功提交的去重记录，直接跳过
    assert asyncio.run(service.process_message(event)) is False
    assert history_manager.insert_calls == 2
