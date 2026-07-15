"""Persistent registry of groups observed by event-driven platforms."""

import asyncio
from datetime import datetime, timezone
from typing import Any


class PlatformGroupRegistry:
    """Keep a small, platform-scoped list of groups seen in incoming events."""

    _KV_KEY = "platform_seen_groups_v1"
    _LEGACY_TELEGRAM_KEY = "telegram_seen_groups_v1"

    def __init__(self, plugin_instance: Any):
        self.plugin = plugin_instance
        self._lock = asyncio.Lock()
        self._known_groups: set[tuple[str, str]] = set()

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

            registry = await self.plugin.get_kv_data(self._KV_KEY, {})
            if not isinstance(registry, dict):
                registry = {}
            platforms = registry.setdefault("platforms", {})
            if not isinstance(platforms, dict):
                platforms = {}
                registry["platforms"] = platforms
            platform_map = platforms.setdefault(platform_key, {})
            if not isinstance(platform_map, dict):
                platform_map = {}
                platforms[platform_key] = platform_map

            # Existing groups only need to be remembered in memory. The
            # registry is used for group discovery, so rewriting last_seen and
            # the full KV document for every message creates unnecessary I/O.
            if group_key in platform_map:
                self._known_groups.add(identity)
                return

            now_iso = datetime.now(timezone.utc).isoformat()
            platform_map[group_key] = {
                "first_seen": now_iso,
                "last_seen": now_iso,
                "last_sender_id": str(sender_id or ""),
                "last_sender_name": str(sender_name or ""),
                "last_event_message_id": str(event_message_id or ""),
            }
            registry["updated_at"] = now_iso
            await self.plugin.put_kv_data(self._KV_KEY, registry)
            self._known_groups.add(identity)

    async def get_all_group_ids(self, platform_id: str | None = None) -> list[str]:
        async with self._lock:
            registry = await self.plugin.get_kv_data(self._KV_KEY, {})
            groups = self._extract_groups(registry, platform_id)
            if platform_id:
                platform_key = str(platform_id).strip()
                self._known_groups.update(
                    (platform_key, group_id) for group_id in groups
                )

            # Preserve groups recorded by older plugin versions.
            legacy = await self.plugin.get_kv_data(self._LEGACY_TELEGRAM_KEY, {})
            legacy_groups = self._extract_groups(legacy, platform_id)
            groups.update(legacy_groups)
            if platform_id:
                self._known_groups.update(
                    (platform_key, group_id) for group_id in legacy_groups
                )
            return sorted(groups)

    @staticmethod
    def _extract_groups(registry: object, platform_id: str | None) -> set[str]:
        if not isinstance(registry, dict):
            return set()
        platforms = registry.get("platforms")
        if not isinstance(platforms, dict):
            return set()

        maps: list[object]
        if platform_id:
            maps = [platforms.get(str(platform_id).strip(), {})]
        else:
            maps = list(platforms.values())

        groups: set[str] = set()
        for platform_map in maps:
            if isinstance(platform_map, dict):
                groups.update(
                    str(group_id).strip()
                    for group_id in platform_map
                    if str(group_id).strip()
                )
        return groups
