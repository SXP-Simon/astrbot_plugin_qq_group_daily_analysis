"""个人禁言、角色豁免和全群禁言的优先顺序回归。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize("role,mute,whole,expected,group_check", [
    ("owner", 0, True, False, False),
    ("admin", 10, True, True, False),
    ("member", 10, False, True, False),
    ("member", 0, True, True, True),
    ("member", 0, False, False, True),
    ("member", 1_000_000_001, False, False, True),
    ("member", 9_999_999_999, False, True, False),
])
async def test_mute_checks_preserve_role_and_timestamp_rules(role, mute, whole, expected, group_check):
    calls = []

    async def call_action(action, **_params):
        calls.append(action)
        if action == "get_group_member_info":
            return {"data": {"role": role, "shut_up_time": mute}}
        assert action == "get_group_info"
        return {"data": {"whole_ban": whole}}

    adapter = OneBotAdapter(SimpleNamespace(call_action=call_action), {"bot_self_ids": ["123"]})
    driver = SimpleNamespace(is_whole_ban=lambda info: info["whole_ban"])
    adapter._ensure_driver = AsyncMock(return_value=driver)
    assert await adapter.is_group_muted("456") is expected
    assert ("get_group_info" in calls) is group_check
