"""验证 QQ 原生表情从入库、历史清洗到群统计与增量合并的完整链路。"""

import base64
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from test_message_processing_service import (
    FakeGroupRegistry,
    FakeOfficialEvent,
    RecordingHistoryManager,
)

from src.application.services.message_processing_service import MessageProcessingService
from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.domain.services.incremental_merge_service import IncrementalMergeService
from src.domain.services.message_cleaner_service import MessageCleanerService
from src.domain.services.statistics_service import StatisticsService
from src.domain.value_objects import ActivityVisualization, GroupStatistics
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.platform.qq_official_faces import (
    restore_qq_face_features,
)


def face_tag(name):
    encoded = base64.b64encode(
        json.dumps({"text": name}, ensure_ascii=False).encode()
    ).decode()
    return f'<faceType=4,faceId="",ext="{encoded}">'


def statistics_for(messages):
    visualizer = SimpleNamespace(
        generate_activity_visualization=lambda _: ActivityVisualization()
    )
    return StatisticsService(visualizer).calculate_group_statistics(messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["qq_official", "qq_official_webhook"])
async def test_faces_survive_storage_fetch_clean_statistics_and_incremental_merge(
    tmp_path, platform
):
    raw_text = f'正文 <faceType=1,faceId="14"> <faceType=1,faceId="14"> {face_tag("😂")} 😂 👍🏽'
    readable_text = "正文 [表情] [表情] [表情:😂] 😂 👍🏽"
    event = FakeOfficialEvent(text=readable_text, platform_name=platform)
    event.message_obj.raw_message.content = raw_text
    event.message_obj.raw_message.timestamp = int(datetime.now().timestamp())
    event.message_obj.message.extend(
        [
            SimpleNamespace(type="Face", id=14),
            SimpleNamespace(
                type="Image", url="https://example.test/表情包.gif", sub_type=1
            ),
        ]
    )
    history = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history), FakeGroupRegistry()
    )
    assert await service.process_message(event)
    assert not await service.process_message(event)
    assert len(history.calls) == 1
    saved = history.calls[0]
    file = tmp_path / "history.json"
    file.write_text(json.dumps(saved["content"], ensure_ascii=False), encoding="utf-8")
    content = json.loads(file.read_text(encoding="utf-8"))
    assert len(content["_qq_official"]["faces"]) == 3
    assert content["message"][-1] == {
        "type": "image",
        "url": "https://example.test/表情包.gif",
    }
    assert "ext=" not in file.read_text(encoding="utf-8")
    record = SimpleNamespace(
        id=1,
        content=content,
        sender_id="MEMBER_OPENID",
        sender_name="群友",
        created_at=datetime.now(),
    )

    async def get_history(**kwargs):
        assert kwargs["platform_id"] == "official-main"
        return [record, record]

    adapter = QQOfficialAdapter(
        SimpleNamespace(platform=None), {"platform_id": "official-main"}
    )
    adapter.set_context(
        SimpleNamespace(message_history_manager=SimpleNamespace(get=get_history))
    )
    messages = MessageCleanerService().clean_messages(
        await adapter.fetch_messages("GROUP_OPENID")
    )
    assert len(messages) == 1
    assert messages[0].text_content == readable_text
    raw_message = adapter.convert_to_raw_format(messages)[0]["message"]
    assert raw_message[0]["data"]["text"] == readable_text
    assert len(raw_message) == 2
    stats = statistics_for(messages)
    assert stats.emoji_count == 3
    assert stats.emoji_statistics.face_count == 3
    assert stats.emoji_statistics.face_details["emoji_qq:1:14"] == 2
    assert stats.emoji_statistics.other_emoji_count == 0
    assert stats.emoji_statistics.mface_count == 0
    assert stats.total_characters == len(readable_text)
    users = AnalysisDomainService().analyze_user_activity(messages)
    assert users["MEMBER_OPENID"]["emoji_count"] == 3
    assert users["MEMBER_OPENID"]["char_count"] == stats.total_characters
    restored_stats = GroupStatistics.from_dict(json.loads(json.dumps(stats.to_dict())))
    assert restored_stats.emoji_count == 3
    batch = IncrementalBatch(
        group_id="GROUP_OPENID",
        messages_count=1,
        emoji_stats=stats.emoji_statistics.to_dict(),
    )
    restored_batch = IncrementalBatch.from_dict(json.loads(json.dumps(batch.to_dict())))
    state = IncrementalMergeService().merge_batches(
        [restored_batch], 0, datetime.now().timestamp()
    )
    assert state.emoji_counts["face_count"] == 3
    assert state.emoji_counts["other_emoji_count"] == 0


@pytest.mark.asyncio
async def test_face_only_component_is_stored_without_plain_text():
    event = FakeOfficialEvent(text="")
    event.message_obj.message = [SimpleNamespace(type="Face", id=0)]
    history = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history), FakeGroupRegistry()
    )
    assert await service.process_message(event)
    content = history.calls[0]["content"]
    assert content["message"] == [{"type": "plain", "text": "[表情:0]"}]
    restored = restore_qq_face_features(content["_qq_official"])
    assert len(restored) == 1
    assert restored[0].emoji_id == "qq:component:0"


@pytest.mark.asyncio
async def test_other_platform_storage_is_unchanged():
    event = FakeOfficialEvent(text="😂", platform_name="satori")
    history = RecordingHistoryManager()
    service = MessageProcessingService(
        SimpleNamespace(message_history_manager=history), FakeGroupRegistry()
    )
    assert await service.process_message(event)
    assert "_qq_official" not in history.calls[0]["content"]
