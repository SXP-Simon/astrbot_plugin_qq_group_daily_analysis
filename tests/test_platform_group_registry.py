import asyncio

from src.infrastructure.persistence.platform_group_registry import PlatformGroupRegistry


class FakePlugin:
    async def get_kv_data(self, key, default):
        registries = {
            "platform_seen_groups_v1": {
                "platforms": {"telegram-main": {"new-group": {}}}
            },
            "telegram_seen_groups_v1": {
                "platforms": {"telegram-main": {"legacy-group": {}}}
            },
        }
        return registries.get(key, default)


def test_new_and_legacy_group_registries_are_merged():
    registry = PlatformGroupRegistry(FakePlugin())

    group_ids = asyncio.run(registry.get_all_group_ids("telegram-main"))

    assert group_ids == ["legacy-group", "new-group"]
