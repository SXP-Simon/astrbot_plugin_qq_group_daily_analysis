"""清洗快照的 JSON 与内存消息还原边界。"""

from copy import deepcopy

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.domain.value_objects import UnifiedMessage


@pytest.mark.parametrize("serialized", [True, False])
def test_clean_checkpoint_restores_domain_data_without_mutating_snapshot(serialized):
    fields = {"message_id": "m", "sender_id": "u", "sender_name": "成员", "text_content": "恢复正文", "timestamp": 123, "sender_card": "名片"}
    message = fields if serialized else UnifiedMessage(group_id="123", **fields)
    checkpoint = {
        "statistics": {"message_count": 1},
        "user_activity": {"u": {"message_count": 1}},
        "top_users": [{"user_id": "u"}],
        "unified_messages": [None, message, 7],
    }
    before = deepcopy(checkpoint)
    result, messages, top_users = AnalysisRecoveryService._restore_clean_checkpoint(checkpoint, "123")
    assert result["statistics"].message_count == 1
    assert result["user_analysis"] == {"u": {"message_count": 1}}
    assert top_users == [{"user_id": "u"}]
    assert len(messages) == 1
    assert messages[0].text_content == "恢复正文"
    assert messages[0].group_id == "123"
    assert messages[0].sender_card == "名片"
    assert checkpoint == before
    if not serialized:
        assert messages[0] is message
