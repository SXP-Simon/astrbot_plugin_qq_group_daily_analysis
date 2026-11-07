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
@pytest.mark.asyncio
async def test_same_group_discovery_is_ambiguous_but_explicit_names_are_isolated():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from src.infrastructure.scheduler.target_resolver import ScheduledTargetResolver

    adapters = {
        name: SimpleNamespace(platform_id=name, get_group_info=AsyncMock(return_value=SimpleNamespace(group_name=f"群-{name}")))
        for name in ("first", "second")
    }
    manager = Mock()
    manager.get_all_adapters.return_value = adapters
    manager.is_plugin_enabled.return_value = True
    manager.get_adapter.side_effect = adapters.get
    manager.get_adapter_platform_id.side_effect = lambda adapter: adapter.platform_id
    resolver = ScheduledTargetResolver(Mock(), manager)
    assert await resolver.get_platform_id_for_group("123") is None
    assert await resolver.get_group_name_safe("123", "first") == "群-first"
    assert await resolver.get_group_name_safe("123", "second") == "群-second"
    assert await resolver.get_group_name_safe("123", "first") == "群-first"


