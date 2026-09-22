"""
OneBot 协议端方言驱动基类 (OneBot Protocol Driver Interface)

遵循开闭原则 (OCP)，将不同 OneBot 实现（如 NapCat, SnowLuma, LLOneBot, onebots, Lagrange 等）
的专有 API 参数、分页机制和错误识别逻辑从核心 Adapter 主干中解耦。
"""

from abc import ABC, abstractmethod
from typing import Any


class OneBotDriver(ABC):
    """OneBot 协议端方言驱动抽象基类。"""

    name: str = "base"

    @abstractmethod
    def build_history_params(
        self,
        group_id: str,
        count: int,
        anchor_id: str | int | None,
    ) -> dict[str, Any]:
        """构建拉取群历史消息 (get_group_msg_history) 的 API 参数。

        Args:
            group_id: 目标群号
            count: 本批次拉取数量
            anchor_id: 分页回溯锚点 ID（可能是 message_seq、message_id 或其他标识）

        Returns:
            dict[str, Any]: 传给 call_action 的参数字典
        """
        raise NotImplementedError

    @abstractmethod
    def extract_history_anchor(
        self,
        earliest_msg: dict[str, Any],
    ) -> str | int | None:
        """从拉取到的最早一条消息中提取用于下一次分页回溯的锚点 ID。

        Args:
            earliest_msg: 本批次中最旧的一条原始消息字典

        Returns:
            str | int | None: 提取出的锚点值
        """
        raise NotImplementedError

    @abstractmethod
    async def upload_group_album(
        self,
        bot: Any,
        group_id: str,
        album_id: str,
        album_name: str | None,
        file_content: str,
    ) -> None:
        """执行群相册上传 API 调用。

        Args:
            bot: 机器人 SDK 实例
            group_id: 目标群号
            album_id: 目标相册 ID
            album_name: 目标相册名称（可选）
            file_content: 文件路径、URL 或 Base64 编码字符串
        """
        raise NotImplementedError

    async def upload_stream_file(
        self,
        bot: Any,
        file_path: Any,
    ) -> str | None:
        """可选扩展：执行分块流式上传（NapCat 特性）。默认返回 None。"""
        return None

    @abstractmethod
    def is_mute_exception(self, exc: Exception) -> bool:
        """判断异常是否属于被禁言/拒绝发言导致的错误。

        Args:
            exc: 捕获的异常对象

        Returns:
            bool: 是否为禁言错误
        """
        raise NotImplementedError

    @abstractmethod
    def is_whole_ban(self, group_info: dict[str, Any]) -> bool:
        """从 get_group_info 响应中判断当前群聊是否开启了全群禁言。

        Args:
            group_info: get_group_info 返回的字典

        Returns:
            bool: 是否处于全群禁言状态
        """
        raise NotImplementedError
