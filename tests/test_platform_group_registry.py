import asyncio

from src.infrastructure.persistence.platform_group_registry import PlatformGroupRegistry


class FakePlugin:
    def __init__(self):
        self.get_calls = 0
        self.put_calls = 0
        self.registry = {"platforms": {}}

    async def get_kv_data(self, key, default):
        self.get_calls += 1
        registries = {
            "platform_seen_groups_v1": self.registry,
            "telegram_seen_groups_v1": {
                "platforms": {"telegram-main": {"legacy-group": {}}}
            },
        }
        return registries.get(key, default)

    async def put_kv_data(self, key, value):
        self.put_calls += 1
        self.registry = value


def test_new_and_legacy_group_registries_are_merged():
    plugin = FakePlugin()
    plugin.registry = {"platforms": {"telegram-main": {"new-group": {}}}}
    registry = PlatformGroupRegistry(plugin)

    group_ids = asyncio.run(registry.get_all_group_ids("telegram-main"))

    assert group_ids == ["legacy-group", "new-group"]


def test_repeated_messages_only_persist_a_new_group_once():
    plugin = FakePlugin()
    registry = PlatformGroupRegistry(plugin)

    asyncio.run(registry.upsert("official-main", "GROUP_OPENID"))
    first_get_calls = plugin.get_calls
    asyncio.run(registry.upsert("official-main", "GROUP_OPENID"))

    assert plugin.put_calls == 1
    assert plugin.get_calls == first_get_calls
