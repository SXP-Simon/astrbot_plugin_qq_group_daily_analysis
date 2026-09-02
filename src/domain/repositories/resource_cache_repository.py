"""静态资源持久化缓存仓储领域接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class IResourceCacheRepository(ABC):
    """用于缓存与读取静态资源（字体、CSS、图片、脚本）的抽象仓储接口。"""

    @abstractmethod
    async def get(self, url: str) -> bytes | None:
        """根据 URL 获取本地缓存的资源二进制数据。

        Args:
            url: 远程资源链接。

        Returns:
            若已缓存返回二进制字节流，未命中则返回 None。
        """
        pass

    @abstractmethod
    async def set(self, url: str, data: bytes, mime_type: str | None = None) -> Path:
        """将资源二进制数据存入本地持久化缓存。

        Args:
            url: 远程资源链接。
            data: 资源二进制数据。
            mime_type: 可选的 MIME 类型。

        Returns:
            保存后的本地文件路径。
        """
        pass

    @abstractmethod
    async def get_path(self, url: str) -> Path | None:
        """获取已缓存资源的本地文件路径。

        Args:
            url: 远程资源链接。

        Returns:
            若存在返回本地文件 Path，否则返回 None。
        """
        pass

    @abstractmethod
    async def has(self, url: str) -> bool:
        """检查指定资源是否已在本地缓存。

        Args:
            url: 远程资源链接。

        Returns:
            已缓存且文件有效返回 True，否则返回 False。
        """
        pass

    @abstractmethod
    async def get_or_download(
        self,
        url: str,
        custom_headers: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> tuple[bytes | None, str | None]:
        """优先从缓存获取，若未命中则异步下载并持久化缓存。

        Args:
            url: 远程资源链接。
            custom_headers: 可选的 HTTP 请求头。
            timeout: 下载超时时间（秒）。

        Returns:
            (二进制字节流, MIME 类型) 元组，下载失败时二进制数据为 None。
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息（文件数量、总大小等）。

        Returns:
            包含统计指标的字典。
        """
        pass
