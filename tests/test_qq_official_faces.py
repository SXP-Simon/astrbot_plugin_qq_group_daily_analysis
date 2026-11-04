"""验证 QQ 原生表情从入库、历史清洗到群统计与增量合并的完整链路。"""

import base64
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from test_message_processing_service import (
    FakeOfficialEvent,
)

from src.domain.services.statistics_service import StatisticsService
from src.domain.value_objects import ActivityVisualization
from src.domain.value_objects.unified_message import MessageContentType
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.platform.qq_official_faces import (
    extract_qq_face_features,
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


@pytest.mark.parametrize(
    "text", ["😂 👍🏽 👨‍👩‍👧‍👦 🇨🇳", "[表情] [表情:笑哭]", "[表情:😂]"]
)
def test_plain_text_is_not_reinterpreted_without_protocol_marker(text):
    event = FakeOfficialEvent(text=text)
    event.message_obj.raw_message.content = text
    assert extract_qq_face_features(event) == []


@pytest.mark.parametrize("raw_kind", ["sdk", "dict", "webhook", "raw_data"])
def test_native_protocol_survives_supported_event_shapes(raw_kind):
    content = f'前文 <faceType=1,faceId="0"> {face_tag("[满头问号]")} 后文'
    readable = "前文 [表情] [表情:[满头问号]] 后文"
    event = FakeOfficialEvent(text=readable)
    payload = {"content": content}
    event.message_obj.raw_message = {
        "sdk": SimpleNamespace(content=content),
        "dict": payload,
        "webhook": {"d": payload},
        "raw_data": SimpleNamespace(raw_data=payload, content=readable),
    }[raw_kind]
    assert extract_qq_face_features(event) == [
        {"face_type": "1", "face_id": "0", "name": ""},
        {"face_type": "4", "face_id": "", "name": "[满头问号]"},
    ]


@pytest.mark.parametrize(
    "raw,face_count",
    [
        ('<faceType=4,faceId="",ext="bad base64">', 1),
        ('<faceType=2,faceId="128514">', 1),
        ("<faceType=1>", 0),
        ('<faceType=no,faceId="14">', 0),
        ('<faceType=1,faceId="14>', 0),
        ("[表情] [表情:笑哭]", 0),
    ],
)
def test_invalid_descriptions_do_not_destroy_proven_faces_or_invent_new_ones(
    raw, face_count
):
    event = FakeOfficialEvent(text="[表情]")
    event.message_obj.raw_message.content = raw
    faces = extract_qq_face_features(event)
    assert len(faces) == face_count


def test_legacy_records_do_not_guess_from_display_placeholders_or_unicode():
    adapter = QQOfficialAdapter(SimpleNamespace(platform=None))
    record = SimpleNamespace(
        id=1,
        sender_id="MEMBER",
        sender_name="群友",
        created_at=datetime.now(),
        content={
            "_qq_official": {"message_id": "OLD", "timestamp": 1710000000},
            "message": [
                {"type": "plain", "text": "[表情] [表情:😂] 😂"},
                {"type": "image", "url": "https://example.test/表情.gif"},
            ],
        },
    )
    message = adapter._convert_history_record(record, "GROUP")
    assert message is not None
    assert message.text_content == "[表情] [表情:😂] 😂"
    assert statistics_for([message]).emoji_count == 0


def test_corrupted_face_features_are_ignored_without_failing_message():
    contents = restore_qq_face_features(
        {
            "faces": [
                None,
                {"face_type": True},
                {"face_type": "bad", "face_id": "14"},
                {"face_type": "component", "face_id": "-1"},
                {"face_type": "1", "face_id": "14", "name": "笑哭"},
            ]
        }
    )
    assert len(contents) == 1
    assert contents[0].type == MessageContentType.EMOJI
    assert contents[0].emoji_name == "笑哭"
    assert contents[0].raw_data == {"face_type": "1", "face_id": "14"}


def test_quoted_faces_are_not_counted_as_new_message_faces():
    event = FakeOfficialEvent(text="只回复正文")
    event.message_obj.raw_message = SimpleNamespace(
        content="只回复正文", msg_elements=[{"content": '<faceType=1,faceId="14">'}]
    )
    assert extract_qq_face_features(event) == []
