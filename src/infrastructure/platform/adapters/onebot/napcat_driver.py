"""
NapCatQQ 专属驱动实现 (NapCat Driver)

适配 NapCat.Onebot，支持 NapCat 独有的 stream 流式分块上传及特有 API 行为。
"""

from pathlib import Path
from typing import Any

from .....utils.logger import logger
from ...napcat_stream import upload_file_stream
from .standard_driver import StandardOneBotDriver


class NapCatDriver(StandardOneBotDriver):
    """NapCat 协议端方言驱动。"""

    name: str = "napcat"

    async def get_group_album_list(
        self,
        bot: Any,
        group_id: str,
    ) -> list[dict[str, Any]]:
        """调用 NapCat 特有的 get_qun_album_list 获取群相册列表。

        Args:
            bot: 机器人实例
            group_id: 目标群号

        Returns:
            list[dict[str, Any]]: 相册列表
        """
        try:
            logger.debug(
                f"[OneBot:{self.name}] 正在通过 get_qun_album_list 获取列表 (群: {group_id})..."
            )
            res = await bot.call_action("get_qun_album_list", group_id=str(group_id))
            logger.debug(
                f"[OneBot:{self.name}] 接口 get_qun_album_list 原始响应内容: {res}"
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
                        or data.get("album")
                        or data.get("albumList")
                        or data.get("list")
                        or data.get("albums")
                    )
                    if isinstance(album_list, list):
                        albums = [item for item in album_list if isinstance(item, dict)]
                if not albums:
                    album_list = (
                        res.get("album_list")
                        or res.get("album")
                        or res.get("albumList")
                        or res.get("list")
                        or res.get("albums")
                    )
                    if isinstance(album_list, list):
                        albums = [item for item in album_list if isinstance(item, dict)]
            if albums:
                logger.debug(
                    f"[OneBot:{self.name}] get_qun_album_list 成功获取并提取到 {len(albums)} 个相册对象"
                )
                return albums
            logger.debug(
                f"[OneBot:{self.name}] get_qun_album_list 无法从响应中提取到相册列表: payload={res}"
            )
        except Exception as exc:
            logger.debug(
                f"[OneBot:{self.name}] get_qun_album_list 尝试失败: {exc}，尝试通用回退..."
            )
        return await super().get_group_album_list(bot, group_id)

    async def upload_stream_file(
        self,
        bot: Any,
        file_path: Path,
    ) -> str | None:
        """调用 NapCat 特有的 upload_file_stream 分块上传文件。

        Args:
            bot: 机器人实例
            file_path: 本地文件 Path 对象

        Returns:
            str | None: 上传成功返回远程路径/标识，失败返回 None
        """
        try:
            return await upload_file_stream(bot, file_path)
        except Exception as exc:
            logger.warning(f"[NapCatDriver] 流式上传图片异常: {exc}")
            return None
