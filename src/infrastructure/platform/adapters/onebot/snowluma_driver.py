"""
SnowLuma 专属驱动实现 (SnowLuma Driver)

适配 SnowLuma 的 message_id 分页、result=120 发消息拒绝判定及特有接口行为。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .standard_driver import StandardOneBotDriver

if TYPE_CHECKING:
    from .....domain.value_objects import OneBotHistoryFetchParams


class SnowLumaDriver(StandardOneBotDriver):
    """SnowLuma 协议端方言驱动。

    特性与行为：
    1. 历史消息拉取：仅传 group_id, count, message_id，严格排除 reverseOrder 参数（传入会被拒绝）。
    2. 锚点与偏移策略：仅支持提取 message_id 字段作为回溯锚点。
    3. 禁言与拒绝判定：精准识别 result=120 与 retcode=100 rejected: muted 等 SnowLuma 专有错误码。
    """

    name: str = "snowluma"

    def build_history_params(
        self,
        group_id: str,
        count: int,
        anchor_id: str | int | None,
    ) -> OneBotHistoryFetchParams:
        """构建 SnowLuma 历史消息拉取参数（使用 message_id，不传 reverseOrder）。

        注意：SnowLuma 仅支持以 message_id 字段作为历史回溯锚点，且协议端不接受
        reverseOrder 参数（传入将导致请求被拒绝）。

        Args:
            group_id: 目标群号
            count: 拉取条数
            anchor_id: message_id 锚点

        Returns:
            OneBotHistoryFetchParams: API 参数字典
        """
        params: OneBotHistoryFetchParams = {
            "group_id": int(group_id),
            "count": count,
        }
        if anchor_id:
            # SnowLuma 使用 message_id 作为回溯锚点
            params["message_id"] = anchor_id
        return params

    def extract_history_anchor(
        self,
        earliest_msg: dict[str, object],
    ) -> str | int | None:
        """从最旧消息提取 SnowLuma 专用的 message_id 锚点。

        Args:
            earliest_msg: 最旧消息字典

        Returns:
            str | int | None: message_id 锚点
        """
        val = earliest_msg.get("message_id")
        if isinstance(val, (str, int)):
            return val
        return None

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

        # SnowLuma pattern: send group message rejected with result=120 or muted error
        err_lower = err_str.lower()
        if "rejected" in err_lower and (
            "result=120" in err_lower or "muted" in err_lower
        ):
            return True

        if "result=120" in err_str:
            return True

        return super().is_mute_exception(exc)
