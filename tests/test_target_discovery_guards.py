"""单个平台失败后仍应扫描后续平台，并逐群过滤插件启用状态。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.scheduler.target_resolver import ScheduledTargetResolver


@pytest.mark.asyncio
async def test_discovery_continues_after_failure_and_filters_groups():
    adapters = {
        "failed": SimpleNamespace(platform_id="failed", get_group_list=AsyncMock(side_effect=OSError("离线"))),
        "registered": SimpleNamespace(platform_id="actual", get_group_list=AsyncMock(return_value=[" 1 ", "2", ""]), get_platform_name=lambda: "telegram"),
    }
    manager = SimpleNamespace(
        get_all_bot_instances=lambda: {key: object() for key in adapters},
        get_adapter=lambda key: adapters[key],
        get_adapter_platform_id=lambda adapter: adapter.platform_id,
        is_plugin_enabled=lambda _platform, _plugin, group_id: group_id == "1",
    )
    resolver = ScheduledTargetResolver(None, manager)
    assert await resolver.get_all_groups() == [("actual", "1")]
    adapters["registered"].get_group_list.assert_awaited_once()
