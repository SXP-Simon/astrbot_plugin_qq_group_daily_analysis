import asyncio
from datetime import datetime, timezone

from astrbot.api.star import Star


class TelegramGroupRegistry:
    """
    Telegram 群组/话题注册表

    负责管理 Telegram 的已见群组和话题列表，用于在无法通过 API 获取群列表时提供回退支持。
    数据存储在 AstrBot 的 KV 存储中。
    """

    _KV_KEY = "telegram_seen_groups_v1"

    def __init__(self, plugin_instance: Star):
        self.plugin = plugin_instance
        self._lock = asyncio.Lock()

    async def upsert(
        self,
        platform_id: str,
        group_id: str,
        sender_id: str,
        sender_name: str,
        event_message_id: str,
    ) -> None:
        """更新 Telegram 已见群/话题注册表（KV）。"""
        async with self._lock:
            registry = await self.plugin.get_kv_data(self._KV_KEY, {})
            if not isinstance(registry, dict):
                registry = {}

            platforms = registry.get("platforms")
            if not isinstance(platforms, dict):
                platforms = {}
                registry["platforms"] = platforms

            platform_key = str(platform_id).strip()
            group_key = str(group_id).strip()

            platform_map = platforms.get(platform_key)
            if not isinstance(platform_map, dict):
                platform_map = {}
                platforms[platform_key] = platform_map

            now_iso = datetime.now(timezone.utc).isoformat()

            entry = platform_map.get(group_key)
            if not isinstance(entry, dict):
                entry = {}

            first_seen = entry.get("first_seen")
            if not isinstance(first_seen, str) or not first_seen:
                first_seen = now_iso

            entry.update(
                {
                    "first_seen": first_seen,
                    "last_seen": now_iso,
                    "last_sender_id": str(sender_id),
                    "last_sender_name": str(sender_name),
                    "last_event_message_id": str(event_message_id),
                }
            )
            platform_map[group_key] = entry

            registry["updated_at"] = now_iso
            await self.plugin.put_kv_data(self._KV_KEY, registry)

    async def get_all_group_ids(self, platform_id: str | None = None) -> list[str]:
        """读取 Telegram 已见群/话题列表。"""
        async with self._lock:
            registry = await self.plugin.get_kv_data(self._KV_KEY, {})
            if not isinstance(registry, dict):
                return []

            platforms = registry.get("platforms")
            if not isinstance(platforms, dict):
                return []

            groups: set[str] = set()
            if platform_id:
                platform_map = platforms.get(str(platform_id).strip(), {})
                if isinstance(platform_map, dict):
                    groups.update(
                        str(gid).strip()
                        for gid in platform_map.keys()
                        if str(gid).strip()
                    )
            else:
                for platform_map in platforms.values():
                    if not isinstance(platform_map, dict):
                        continue
                    groups.update(
                        str(gid).strip()
                        for gid in platform_map.keys()
                        if str(gid).strip()
                    )

            return sorted(groups)
