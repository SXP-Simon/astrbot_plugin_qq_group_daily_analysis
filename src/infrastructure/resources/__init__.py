"""静态资源与字体持久化缓存及拦截层基础设施模块。"""

from .html_resource_localizer import HTMLResourceLocalizer
from .resource_cache_repository import FileSystemResourceCacheRepository

__all__ = [
    "FileSystemResourceCacheRepository",
    "HTMLResourceLocalizer",
]
