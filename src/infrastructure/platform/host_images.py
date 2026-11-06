"""AstrBot 图片组件工厂的类型边界，保留宿主的 URL 与路径处理。"""

from typing import Protocol

from astrbot.api.message_components import Image


class ImageFactory(Protocol):
    """插件只使用图片工厂的单参数入口。"""

    def fromURL(self, url: str) -> Image: ...
    def fromFileSystem(self, path: str) -> Image: ...
