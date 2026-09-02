"""资源拦截器抽象基类。"""

from __future__ import annotations

import base64
from abc import abstractmethod
from typing import Any

from ....domain.repositories.resource_cache_repository import (
    IResourceCacheRepository,
)
from ....domain.services.resource_interceptor import IResourceInterceptor


class BaseResourceInterceptor(IResourceInterceptor):
    """资源拦截器基类，封装缓存访问与 Base64 Data URI 编码等公共方法。"""

    def __init__(self, cache_repo: IResourceCacheRepository):
        """初始化拦截器。

        Args:
            cache_repo: 资源持久化缓存仓储。
        """
        self.cache_repo = cache_repo

    @staticmethod
    def to_base64_data_uri(data: bytes, mime_type: str) -> str:
        """将二进制数据编码为标准 Base64 Data URI。

        Args:
            data: 二进制字节数据。
            mime_type: MIME 类型字符串。

        Returns:
            Base64 Data URI 字符串（data:<mime_type>;base64,<encoded>）。
        """
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @abstractmethod
    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """处理内容并本地化其中的外部资源。"""
        pass
