"""
LuckyLilliaBot (LLOneBot) 专属驱动实现 (LLOneBot Driver)

适配 LLOneBot，支持其 upload_group_album 接收 files: list 数组等接口规范。
"""

from __future__ import annotations

from typing import Any

from .....utils.logger import logger
from .standard_driver import StandardOneBotDriver


class LLOneBotDriver(StandardOneBotDriver):
    """LLOneBot (LuckyLilliaBot) 协议端方言驱动。"""

    name: str = "llonebot"

    async def upload_group_album(
        self,
        bot: Any,
        group_id: str,
        album_id: str,
        album_name: str | None,
        file_content: str,
    ) -> None:
        """调用 LLOneBot 相册上传接口（使用 files 列表参数）。

        Args:
            bot: 机器人实例
            group_id: 目标群号
            album_id: 相册 ID
            album_name: 相册名称
            file_content: 文件路径或内容
        """
        # LLBot 模式：upload_group_album 接收 files 作为数组
        llbot_params = {
            "group_id": int(group_id),
            "album_id": str(album_id),
            "files": [file_content],
        }
        try:
            await bot.call_action("upload_group_album", **llbot_params)
            logger.debug(f"[OneBot:{self.name}] 相册上传成功: 群 {group_id}")
            return
        except Exception as e:
            logger.warning(
                f"[OneBot:{self.name}] upload_group_album (files数组) 调用失败: {e}，尝试通用回退..."
            )
            # 回退到标准通用相册上传
            await super().upload_group_album(
                bot, group_id, album_id, album_name, file_content
            )

    async def get_group_album_list(
        self,
        bot: Any,
        group_id: str,
    ) -> list[dict[str, Any]]:
        """调用 LLOneBot 特有的 get_group_album_list 获取群相册列表。

        Args:
            bot: 机器人实例
            group_id: 目标群号

        Returns:
            list[dict[str, Any]]: 相册列表
        """
        try:
            logger.debug(
                f"[OneBot:{self.name}] 正在通过 get_group_album_list 获取列表 (群: {group_id})..."
            )
            res = await bot.call_action("get_group_album_list", group_id=int(group_id))
            logger.debug(
                f"[OneBot:{self.name}] 接口 get_group_album_list 原始响应内容: {res}"
            )
            albums: list[dict[str, Any]] = []
            if isinstance(res, list):
                albums = [item for item in res if isinstance(item, dict)]
            elif isinstance(res, dict):
                data = res.get("data")
                if isinstance(data, list):
                    albums = [item for item in data if isinstance(item, dict)]
                elif isinstance(data, dict):
                    album_list = (
                        data.get("album_list")
                        or data.get("albumList")
                        or data.get("list")
                        or data.get("albums")
                    )
                    if isinstance(album_list, list):
                        albums = [item for item in album_list if isinstance(item, dict)]
                if not albums:
                    album_list = (
                        res.get("album_list")
                        or res.get("albumList")
                        or res.get("list")
                        or res.get("albums")
                    )
                    if isinstance(album_list, list):
                        albums = [item for item in album_list if isinstance(item, dict)]
            if albums:
                logger.debug(
                    f"[OneBot:{self.name}] get_group_album_list 成功获取并提取到 {len(albums)} 个相册对象"
                )
                return albums
            logger.debug(
                f"[OneBot:{self.name}] get_group_album_list 无法从响应中提取到相册列表: payload={res}"
            )
        except Exception as exc:
            logger.debug(
                f"[OneBot:{self.name}] get_group_album_list 尝试失败: {exc}，尝试通用回退..."
            )
        return await super().get_group_album_list(bot, group_id)
