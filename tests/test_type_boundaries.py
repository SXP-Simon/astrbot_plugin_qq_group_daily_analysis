"""验证外部数据收窄、增量快照和图表字段的类型边界。"""

import json

import pytest

from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.services.incremental_merge_service import IncrementalMergeService
from src.domain.value_objects.analysis_results import ActivityVisualization
from src.shared.type_guards import is_object_collection, is_object_list, is_string_mapping


@pytest.mark.parametrize(
    ("value", "string_mapping", "object_list", "collection"),
    [
        ({"name": object()}, True, False, False),
        ({1: "value"}, False, False, False),
        ([1, "name", None], False, True, True),
        ((1, 2), False, False, True),
        ({1, 2}, False, False, True),
        ("not a collection of records", False, False, False),
        (None, False, False, False),
    ],
)
def test_container_guards_do_not_claim_field_types(value, string_mapping, object_list, collection):
    assert is_string_mapping(value) is string_mapping
    assert is_object_list(value) is object_list
    assert is_object_collection(value) is collection


def test_incremental_snapshot_survives_json_and_merges():
    original = {
        "group_id": "123", "batch_id": "batch", "timestamp": 100.5,
        "messages_count": 2, "characters_count": 6,
        "hourly_msg_counts": {"1": 2}, "hourly_char_counts": {"1": 6},
        "user_stats": {"u": {"nickname": "群友", "message_count": 2, "char_count": 6, "hours": {1: 2}}},
        "topics": [{"topic": "周末安排", "contributors": ["群友"], "contributor_ids": ["u"], "detail": "一起出游"}],
        "golden_quotes": [{"content": "明天见", "sender": "群友", "reason": "约定", "user_id": "u"}],
        "emoji_stats": {"face_count": 1, "face_details": {"smile": 1}},
        "token_usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        "last_message_timestamp": 100, "participant_ids": ["u"],
    }
    batch = IncrementalBatch.from_dict(json.loads(json.dumps(original)))
    state = IncrementalMergeService().merge_batches([batch], 90, 110)
    assert state.total_message_count == 2
    assert state.user_activities["u"]["hours"] == {1: 2}
    assert state.total_token_usage["total_tokens"] == 14
    assert state.topics == original["topics"]
    assert state.golden_quotes == original["golden_quotes"]
    assert IncrementalBatch.from_dict(batch.to_dict()) == batch


@pytest.mark.parametrize("data", [None, [], {"group_id": 123}, {"timestamp": "invalid"}, {"last_message_timestamp": []}])
def test_incremental_snapshot_rejects_invalid_identity_or_cursor(data):
    with pytest.raises(ValueError):
        IncrementalBatch.from_dict(data)


def test_unknown_nested_values_do_not_enter_domain_statistics():
    batch = IncrementalBatch.from_dict({
        "user_stats": {"u": {"message_count": [], "hours": {"2": 3, "invalid": 4}}, "broken": []},
        "topics": [None, {"topic": "正常", "contributors": ["群友"], "detail": "正文"}],
        "emoji_stats": {"face_details": {"valid": 2, "invalid": []}},
        "participant_ids": ["u", None],
    })
    assert batch.user_stats == {"u": {"hours": {2: 3}}}
    assert len(batch.topics) == 1
    assert batch.emoji_stats == {"face_details": {"valid": 2}}
    assert batch.participant_ids == ["u"]


def test_activity_chart_preserves_integer_and_json_hour_keys():
    chart = ActivityVisualization.from_dict({
        "hourly_activity": {1: 2, "2": 3},
        "daily_activity": {"2026-11-06": "5"},
        "user_activity_ranking": [{"user_id": "u", "nickname": "群友", "message_count": 5}],
        "peak_hours": [1, 2, None],
        "activity_heatmap_data": {"hourly_max": 3, "hourly_normalized": {"2": 100}, "activity_levels": {"2": "high"}},
    })
    assert chart.hourly_activity == {1: 2, 2: 3}
    assert chart.daily_activity == {"2026-11-06": 5}
    assert chart.peak_hours == [1, 2]
    assert chart.activity_heatmap_data["hourly_normalized"] == {2: 100.0}
    assert ActivityVisualization.from_dict(json.loads(json.dumps(chart.to_dict()))) == chart


def test_generated_activity_chart_keeps_peak_counts_after_json_roundtrip():
    from datetime import datetime
    from src.infrastructure.visualization.activity_charts import ActivityVisualizer

    timestamp = int(datetime(2026, 11, 6, 10, 0).timestamp())
    messages = [
        {"time": timestamp, "sender": {"user_id": "u", "nickname": "群友"}, "message": []},
        {"time": timestamp + 60, "sender": {"user_id": "u", "nickname": "群友"}, "message": []},
    ]
    chart = ActivityVisualizer().generate_activity_visualization(messages)
    restored = ActivityVisualization.from_dict(json.loads(json.dumps(chart.to_dict())))
    assert restored.peak_hours == [{"hour": 10, "count": 2}]
    assert restored.hourly_activity == {10: 2}
    assert restored.user_activity_ranking[0]["message_count"] == 2


def test_user_activity_boundary_does_not_mutate_legacy_record():
    from copy import deepcopy
    from src.domain.value_objects.analysis_results import parse_user_activity

    raw = {"u": {"nickname": "群友", "active_hours": [1, "bad"], "hours": {"2": 3}, "extension": {"keep": True}}}
    before = deepcopy(raw)
    assert parse_user_activity(raw) == {"u": {"nickname": "群友", "active_hours": [1], "hours": {2: 3}}}
    assert raw == before
