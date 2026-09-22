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
