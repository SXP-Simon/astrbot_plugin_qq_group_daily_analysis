import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.infrastructure.platform.adapters.telegram_adapter import TelegramAdapter
from src.infrastructure.scheduler.target_resolver import ScheduledTargetResolver


class FakeRegistry:
    def __init__(self, groups: list[str] | None = None):
        self._groups = groups or []

    async def get_all_group_ids(self, platform_id: str) -> list[str]:
        assert platform_id == "tg-main"
        return list(self._groups)


def test_telegram_adapter_get_group_list_reads_from_registry():
    plugin_inst = Mock()
    plugin_inst.platform_group_registry = FakeRegistry(["-100123456", "-100789012"])

    adapter = TelegramAdapter(
        bot_instance=Mock(),
        config={"platform_id": "tg-main", "plugin_instance": plugin_inst},
    )

    groups = asyncio.run(adapter.get_group_list())
    assert set(groups) == {"-100123456", "-100789012"}


def test_telegram_adapter_get_group_list_handles_missing_registry_gracefully():
    # 当插件实例没有 platform_group_registry 时，应返回空列表且不抛错
    plugin_inst = Mock(spec=[])

    adapter = TelegramAdapter(
        bot_instance=Mock(),
        config={"platform_id": "tg-main", "plugin_instance": plugin_inst},
    )

    groups = asyncio.run(adapter.get_group_list())
    assert groups == []


def test_scheduled_target_resolver_passes_plugin_instance_to_fallback_adapter():
    config_manager = Mock()
    config_manager.get_scheduled_target_mode.return_value = "all"
    config_manager.get_bot_self_ids.return_value = []

    bot_manager = Mock()
    bot_manager.get_all_bot_instances.return_value = {"tg-main": Mock()}
    bot_manager.is_plugin_enabled.return_value = True
    bot_manager.get_adapter.return_value = None  # 模拟未注册 adapter，触发 fallback 构造
    bot_manager._detect_platform_name.return_value = "telegram"
    bot_manager.get_adapter_platform_id.return_value = "tg-main"

    bot_manager.auto_discover_bot_instances = AsyncMock()
    fake_plugin = Mock()
    fake_plugin.platform_group_registry = FakeRegistry(["-100111222"])
    bot_manager.plugin_instance = fake_plugin

    resolver = ScheduledTargetResolver(config_manager, bot_manager)

    created_configs = []

    class DummyAdapter:
        def __init__(self, bot, cfg):
            created_configs.append(cfg)

        async def get_group_list(self):
            return await created_configs[0]["plugin_instance"].platform_group_registry.get_all_group_ids(
                created_configs[0]["platform_id"]
            )

        def get_platform_name(self):
            return "telegram"

    from src.infrastructure.platform.factory import PlatformAdapterFactory

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            PlatformAdapterFactory,
            "create",
            lambda ptype, bot, config=None: DummyAdapter(bot, config),
        )

        groups = asyncio.run(resolver.get_all_groups())
        assert groups == [("tg-main", "-100111222")]
        assert len(created_configs) == 1
        assert created_configs[0]["plugin_instance"] is fake_plugin
