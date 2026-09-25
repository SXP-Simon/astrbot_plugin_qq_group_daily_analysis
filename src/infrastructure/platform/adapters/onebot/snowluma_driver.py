"""
SnowLuma 专属驱动实现 (SnowLuma Driver)

适配 SnowLuma 的 message_id 分页、result=120 发消息拒绝判定及特有接口行为。
"""

from __future__ import annotations

from typing import Any

from .standard_driver import StandardOneBotDriver


class SnowLumaDriver(StandardOneBotDriver):
    """SnowLuma 协议端方言驱动。"""

    name: str = "snowluma"

    def build_history_params(
        self,
        group_id: str,
        count: int,
        anchor_id: str | int | None,
    ) -> dict[str, Any]:
        """构建 SnowLuma 历史消息拉取参数（使用 message_id，不传 reverseOrder）。

        Args:
            group_id: 目标群号
            count: 拉取条数
            anchor_id: message_id 锚点

        Returns:
            dict[str, Any]: API 参数字典
        """
        params: dict[str, Any] = {
            "group_id": int(group_id),
            "count": count,
        }
        if anchor_id:
            # SnowLuma 使用 message_id 作为回溯锚点
            params["message_id"] = anchor_id
        return params

    def extract_history_anchor(
        self,
        earliest_msg: dict[str, Any],
    ) -> str | int | None:
        """从最旧消息提取 SnowLuma 专用的 message_id 锚点。

        Args:
            earliest_msg: 最旧消息字典

        Returns:
            str | int | None: message_id 锚点
        """
        return earliest_msg.get("message_id")

    def is_mute_exception(self, exc: Exception) -> bool:
        """识别 SnowLuma 特有的 result=120 / rejected 拒绝与禁言错误。

        Args:
            exc: 异常对象

        Returns:
            bool: 是否属于禁言或发送拒绝异常
        """
        if not exc:
            return False
        err_str = str(exc)

        # SnowLuma 特有模式：retcode=100 / result=120
        # "send group message rejected: result=120 err="
        err_lower = err_str.lower()
        if "rejected" in err_lower and (
            "result=120" in err_lower or "muted" in err_lower
        ):
            return True

        if "result=120" in err_str:
            return True

        return super().is_mute_exception(exc)
