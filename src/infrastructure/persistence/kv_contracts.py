"""AstrBot KV 存储边界契约。"""

from typing import Protocol


class KeyValueWriter(Protocol):
    """宿主 KV 写入边界，传入值由仓储生成并交由宿主序列化。"""

    async def put_kv_data(self, key: str, value: object) -> None: ...


class CacheAccess(Protocol):
    """缓存边界只接收字符串键，读出的内容交由调用方校验。"""

    def get(self, key: str, default: object = None) -> object: ...
    def set(self, key: str, value: object, *, expire: float) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def __contains__(self, key: str) -> bool: ...
    def __getitem__(self, key: str) -> object: ...
    def close(self) -> None: ...


class StoredPreference(Protocol):
    """宿主偏好记录的原始值，不假定嵌套 JSON 的结构。"""

    @property
    def value(self) -> object: ...
