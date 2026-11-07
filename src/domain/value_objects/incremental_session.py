"""增量存储的会话身份，不使用平台显示名作为隔离键。"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class IncrementalSession:
    """平台实例与群号共同定位一份增量状态。"""

    platform_id: str
    group_id: str
