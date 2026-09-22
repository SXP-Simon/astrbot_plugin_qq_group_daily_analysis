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

    # QQ 头像服务 URL 模板与可用尺寸
    USER_AVATAR_TEMPLATE = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
    USER_AVATAR_HD_TEMPLATE = (
        "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec={size}&img_type=jpg"
    )
    GROUP_AVATAR_TEMPLATE = "https://p.qlogo.cn/gh/{group_id}/{group_id}/{size}/"
    AVAILABLE_SIZES = (40, 100, 140, 160, 640)

    @classmethod
    def get_nearest_size(cls, target_size: int) -> int:
        """从支持的尺寸中找到最接近的值。

        Args:
            target_size: 目标尺寸

        Returns:
            int: 最接近的支持尺寸
        """
        return min(cls.AVAILABLE_SIZES, key=lambda s: abs(s - target_size))

    def build_user_avatar_cdn_url(self, user_id: str, size: int) -> str:
        """根据 QQ 号和期望尺寸构建 QQ 官方 CDN 头像回退 URL。

        Args:
            user_id: QQ 号
            size: 期望像素大小

        Returns:
            str: 格式化的 QQ 头像 CDN URL
        """
        actual_size = self.get_nearest_size(size)
        if actual_size >= 640:
            return self.USER_AVATAR_HD_TEMPLATE.format(user_id=user_id, size=640)
        return self.USER_AVATAR_TEMPLATE.format(user_id=user_id, size=actual_size)

    def build_group_avatar_cdn_url(self, group_id: str, size: int) -> str:
        """根据群号和期望尺寸构建 QQ 官方 CDN 群头像 URL。

        Args:
            group_id: QQ 群号
            size: 期望像素大小

        Returns:
            str: 格式化的 QQ 群头像 CDN URL
        """
        actual_size = self.get_nearest_size(size)
        return self.GROUP_AVATAR_TEMPLATE.format(group_id=group_id, size=actual_size)

    async def get_group_album_list(
        self,
        bot: Any,
        group_id: str,
    ) -> list[dict[str, Any]]:
        """获取群相册列表（兼容多种 OneBot 扩展实现及返回结构）。

        Args:
            bot: 机器人实例
            group_id: 目标群号

        Returns:
            list[dict[str, Any]]: 提取出的相册列表
        """

        def extract_list(payload: Any) -> list[dict[str, Any]]:
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
            if not isinstance(payload, dict):
                logger.debug(
                    f"[OneBot:{self.name}] 提取相册列表失败: payload 非字典/列表类型 ({type(payload)})"
                )
                return []

            data = payload.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                album_list = (
                    data.get("album_list")
                    or data.get("albumList")
                    or data.get("list")
                    or data.get("albums")
                    or data.get("album")
                )
                if isinstance(album_list, list):
                    return [item for item in album_list if isinstance(item, dict)]
                logger.debug(
                    f"[OneBot:{self.name}] 在 data 字段中未找到列表: data={data}"
                )

            album_list = (
                payload.get("album_list")
                or payload.get("albumList")
                or payload.get("list")
                or payload.get("albums")
                or payload.get("album")
            )
            if isinstance(album_list, list):
                return [item for item in album_list if isinstance(item, dict)]

            logger.debug(
                f"[OneBot:{self.name}] 无法从响应中提取相册列表: payload={payload}"
            )
            return []

        actions = [
            "get_qun_album_list",
            "get_group_album_list",
            "get_group_albums",
            "get_group_root_album_list",
        ]

        for action in actions:
            try:
                logger.debug(
                    f"[OneBot:{self.name}] 正在通过 {action} 获取列表 (群: {group_id})..."
                )
                result = await bot.call_action(
                    action,
                    group_id=int(group_id),
                )
                logger.debug(
                    f"[OneBot:{self.name}] 接口 {action} 原始响应内容: {result}"
                )
                if result:
                    albums = extract_list(result)
                    if albums:
                        logger.debug(
                            f"[OneBot:{self.name}] {action} 成功获取并提取到 {len(albums)} 个相册对象"
                        )
                        return albums
            except Exception as e:
                logger.debug(f"[OneBot:{self.name}] 接口 {action} 尝试失败: {e}")

        return []

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

        # 检查常见错误码与模式（兼容标准与各类方言如 SnowLuma 的 result=120）
        if any(rc in err_str for rc in ("1200", "retcode=100", "result=120")):
            if (
                any(kw in err_str for kw in self.MUTE_KEYWORDS)
                or "result=120" in err_str
            ):
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
