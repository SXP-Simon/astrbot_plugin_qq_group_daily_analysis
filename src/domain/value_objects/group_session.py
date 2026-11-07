"""群聊会话身份，供分析、任务互斥和持久化共同使用。"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class GroupSession:
    """以真实平台实例 ID 和原始群标识定位会话。

    实例别名由接入边界解析；领域对象不负责选择机器人。
    空平台仅表示尚未归属的旧数据或明确的群级共享保护。
    """

    platform_id: str
    group_id: str
