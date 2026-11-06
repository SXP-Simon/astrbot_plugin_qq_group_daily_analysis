"""保存事件驱动平台中已见群组的注册表。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from ...shared.type_guards import is_string_mapping

if TYPE_CHECKING:
    from astrbot.api.star import Star

    from .kv_contracts import KeyValueWriter


class PlatformGroupRegistry:
    """按平台保存收到过消息的群组，用于群列表发现。"""

    _KV_KEY = "platform_seen_groups_v1"
    _LEGACY_TELEGRAM_KEY = "telegram_seen_groups_v1"

    plugin: Star
    _lock: asyncio.Lock
    _known_groups: set[tuple[str, str]]

    def __init__(self, plugin_instance: Star) -> None:
        self.plugin = plugin_instance
        self._lock = asyncio.Lock()
        self._known_groups = set()

    async def upsert(
        self,
        platform_id: str,
        group_id: str,
        sender_id: str = "",
        sender_name: str = "",
        event_message_id: str = "",
    ) -> None:
        platform_key = str(platform_id or "").strip()
        group_key = str(group_id or "").strip()
        if not platform_key or not group_key:
            return

        async with self._lock:
            identity = (platform_key, group_key)
            if identity in self._known_groups:
                return

            registry = await self.plugin.get_kv_data(self._KV_KEY, None)
            if not is_string_mapping(registry):
                registry = {}
            platforms = registry.setdefault("platforms", {})
            if not is_string_mapping(platforms):
                platforms = {}
                registry["platforms"] = platforms
            platform_map = platforms.setdefault(platform_key, {})
            if not is_string_mapping(platform_map):
                platform_map = {}
                platforms[platform_key] = platform_map

            # 已登记的群只需记入内存，避免每条消息都重写完整注册表。
            if group_key in platform_map:
                self._known_groups.add(identity)
                return

            now_iso = datetime.now(UTC).isoformat()
            platform_map[group_key] = {
                "first_seen": now_iso,
                "last_seen": now_iso,
                "last_sender_id": str(sender_id or ""),
                "last_sender_name": str(sender_name or ""),
                "last_event_message_id": str(event_message_id or ""),
            }
            registry["updated_at"] = now_iso
            await cast("KeyValueWriter", self.plugin).put_kv_data(
                self._KV_KEY, registry
            )
            self._known_groups.add(identity)

    async def get_all_group_ids(self, platform_id: str | None = None) -> list[str]:
        async with self._lock:
            registry = await self.plugin.get_kv_data(self._KV_KEY, None)
            groups = self._extract_groups(registry, platform_id)
            platform_key = str(platform_id).strip() if platform_id else None
            if platform_id:
                self._known_groups.update(
                    (str(platform_key), group_id) for group_id in groups
                )

            # 保留旧版本登记的群组。
            legacy = await self.plugin.get_kv_data(self._LEGACY_TELEGRAM_KEY, None)
            legacy_groups = self._extract_groups(legacy, platform_id)
            groups.update(legacy_groups)
            if platform_id:
                self._known_groups.update(
                    (str(platform_key), group_id) for group_id in legacy_groups
                )
            return sorted(groups)

    @staticmethod
    def _extract_groups(registry: object, platform_id: str | None) -> set[str]:
        if not is_string_mapping(registry):
            return set()
        platforms = registry.get("platforms")
        if not is_string_mapping(platforms):
            return set()

        maps: list[object]
        if platform_id:
            maps = [platforms.get(str(platform_id).strip(), {})]
        else:
            maps = list(platforms.values())

        groups: set[str] = set()
        for platform_map in maps:
            if is_string_mapping(platform_map):
                groups.update(
                    str(group_id).strip()
                    for group_id in platform_map
                    if str(group_id).strip()
                )
        return groups
