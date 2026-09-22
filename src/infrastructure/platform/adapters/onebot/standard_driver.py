"""
标准 OneBot v11 驱动实现 (Standard OneBot Driver)

适用于遵循 OneBot v11 标准扩展（go-cqhttp, onebots 等）及通用默认实现的协议端。
"""

from typing import Any

from .....utils.logger import logger
from .driver_base import OneBotDriver


class StandardOneBotDriver(OneBotDriver):
    """标准 OneBot v11 驱动。"""

    name: str = "standard"

    MUTE_KEYWORDS = ("禁言", "操作失败", "下游群鉴权")

    def build_history_params(
        self,
        group_id: str,
        count: int,
        anchor_id: str | int | None,
    ) -> dict[str, Any]:
        """构建标准 OneBot 历史消息拉取参数。

        Args:
            group_id: 目标群号
            count: 拉取条数
            anchor_id: 消息序号锚点

        Returns:
            dict[str, Any]: API 参数字典
        """
        params: dict[str, Any] = {
            "group_id": int(group_id),
            "count": count,
            "reverseOrder": True,
        }
        if anchor_id:
            params["message_seq"] = anchor_id
        return params

    def extract_history_anchor(
        self,
        earliest_msg: dict[str, Any],
    ) -> str | int | None:
        """从最旧消息提取序号锚点（优先 message_seq）。

        Args:
            earliest_msg: 最旧消息字典

        Returns:
            str | int | None: 提取出的锚点
        """
        seq_val = (
            earliest_msg.get("message_seq")
            or earliest_msg.get("real_id")
            or earliest_msg.get("seq")
        )
        mid_val = earliest_msg.get("message_id")
        return seq_val if seq_val is not None else mid_val

    async def upload_group_album(
        self,
        bot: Any,
        group_id: str,
        album_id: str,
        album_name: str | None,
        file_content: str,
    ) -> None:
        """通过标准轮询调用相册上传 API。

        Args:
            bot: 机器人实例
            group_id: 目标群号
            album_id: 相册 ID
            album_name: 相册名称
            file_content: 图片内容或路径

        Raises:
            RuntimeError: 所有候选 API 均调用失败时抛出
        """
        params: dict[str, Any] = {
            "group_id": int(group_id),
            "file": file_content,
            "album_id": str(album_id),
        }
        if album_name:
            params["album_name"] = album_name

        for action in [
            "upload_image_to_qun_album",
            "upload_group_album",
            "upload_qun_album",
        ]:
            try:
                await bot.call_action(action, **params)
                logger.debug(
                    f"[OneBot:{self.name}] 相册上传成功 ({action}): 群 {group_id}"
                )
                return
            except Exception as exc:
                logger.debug(
                    f"[OneBot:{self.name}] 尝试接口 {action} 上传相册失败 (群 {group_id}): {exc}"
                )
                continue
        raise RuntimeError("所有相册上传 API 均调用失败")

    def is_mute_exception(self, exc: Exception) -> bool:
        """识别常见 OneBot 禁言与操作拒绝异常。

        Args:
            exc: 异常对象

        Returns:
            bool: 是否属于禁言异常
        """
        if not exc:
            return False
        err_str = str(exc)

        # 检查常见错误码
        if any(rc in err_str for rc in ("1200", "retcode=100")):
            if any(kw in err_str for kw in self.MUTE_KEYWORDS):
                return True

        for attr in ("message", "wording"):
            val = getattr(exc, attr, "") or ""
            if any(kw in val for kw in self.MUTE_KEYWORDS):
                return True
            if "shut up" in val.lower():
                return True

        if any(kw in err_str for kw in self.MUTE_KEYWORDS):
            return True

        return False

    def is_whole_ban(self, group_info: dict[str, Any]) -> bool:
        """识别多协议端全群禁言标记。

        Args:
            group_info: 群信息字典

        Returns:
            bool: 是否全群禁言
        """
        if not group_info:
            return False
        return bool(
            group_info.get("group_all_shut")
            or group_info.get("shutup_all")
            or group_info.get("is_whole_ban")
            or group_info.get("whole_ban")
            or group_info.get("shutup")
            or group_info.get("shut_up")
        )
