"""
LuckyLilliaBot (LLOneBot) 专属驱动实现 (LLOneBot Driver)

适配 LLOneBot，支持其 upload_group_album 接收 files: list 数组等接口规范。
"""

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
