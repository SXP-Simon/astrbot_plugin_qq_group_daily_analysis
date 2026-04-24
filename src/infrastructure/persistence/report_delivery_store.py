"""HTML 报告分发状态存储（KV）。"""

import time
from typing import Any

from ...utils.logger import logger


class ReportDeliveryStore:
    """基于插件 KV 的报告分发状态存储。"""

    KEY_PREFIX = "report_delivery_v1"

    def __init__(self, star_instance: Any):
        self.plugin = star_instance

    def _key(self, dispatch_key: str) -> str:
        return f"{self.KEY_PREFIX}_{dispatch_key}"

    async def get_record(self, dispatch_key: str) -> dict[str, Any] | None:
        """读取指定 dispatch_key 的状态记录。"""
        key = self._key(dispatch_key)
        try:
            data = await self.plugin.get_kv_data(key, None)
            if isinstance(data, dict):
                return data
            return None
        except Exception as e:
            logger.warning(f"读取分发状态失败 (Key: {key}): {e}")
            return None

    async def get_recent_success(
        self,
        dispatch_key: str,
        within_seconds: int,
    ) -> dict[str, Any] | None:
        """若该报告在窗口内已成功发送（或假定成功），返回记录。"""
        rec = await self.get_record(dispatch_key)
        if not rec:
            return None

        status = str(rec.get("status", ""))
        if status not in {"sent", "assumed_sent", "skipped_duplicate"}:
            return None

        ts = float(rec.get("timestamp", 0.0) or 0.0)
        if within_seconds <= 0:
            return rec

        if time.time() - ts <= within_seconds:
            return rec
        return None

    async def mark(
        self,
        dispatch_key: str,
        group_id: str,
        platform_id: str | None,
        status: str,
        success: bool,
        message_id: str | None = None,
        error: str = "",
    ) -> bool:
        """写入分发状态记录。"""
        key = self._key(dispatch_key)
        payload = {
            "dispatch_key": dispatch_key,
            "group_id": group_id,
            "platform_id": platform_id or "",
            "status": status,
            "success": bool(success),
            "message_id": message_id,
            "error": error,
            "timestamp": time.time(),
        }

        try:
            await self.plugin.put_kv_data(key, payload)
            return True
        except Exception as e:
            logger.warning(f"写入分发状态失败 (Key: {key}): {e}")
            return False
