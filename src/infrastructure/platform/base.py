"""
平台适配器基类
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from ...domain.repositories.avatar_repository import IAvatarRepository
from ...domain.repositories.message_repository import (
    IGroupInfoRepository,
    IMessageRepository,
    IMessageSender,
)
from ...domain.value_objects.platform_capabilities import PlatformCapabilities
from ...domain.value_objects.unified_message import UnifiedMessage


class PlatformAdapter(
    IMessageRepository, IMessageSender, IGroupInfoRepository, IAvatarRepository, ABC
):
    """
    基础设施：平台适配器基类

    继承自多个领域接口（仓储、发送器、群组信息、头像），
    充当领域层与具体聊天平台（如 OneBot, Discord）之间的中转站。

    Attributes:
        bot (Any): 平台对应的机器人 SDK 实例，显式标注为 Any 以支持动态属性调用
        config (dict): 针对该平台的特定配置
    """

    bot: Any

    def __init__(
        self,
        bot_instance: Any,
        config: Mapping[str, Any] | None = None,
    ):
        """
        初始化平台适配器。

        Args:
            bot_instance (Any): 后端机器人实例
            config (dict, optional): 平台特定配置项
        """
        self.bot = bot_instance
        self.config: dict[str, object] = dict(config) if config is not None else {}
        self.bot_self_ids: list[str] = []
        self._capabilities: PlatformCapabilities | None = None

    def set_context(self, context: Any):
        """
        设置上下文对象（用于部分需要 ctx 的平台如 Telegram）。

        Args:
            context (Any): 上下文对象
        """
        pass

    @property
    def capabilities(self) -> PlatformCapabilities:
        """
        获取当前平台的能力描述对象。

        采用延迟加载机制，在首次访问时调用 `_init_capabilities`。

        Returns:
            PlatformCapabilities: 平台能力对象
        """
        if self._capabilities is None:
            self._capabilities = self._init_capabilities()
        return self._capabilities

    @abstractmethod
    def _init_capabilities(self) -> PlatformCapabilities:
        """
        初始化并返回当前平台的能力定义。

        子类必须实现此方法以声明其对历史记录、图片发送等功能的支持情况。

        Returns:
            PlatformCapabilities: 初始化后的能力对象
        """
        raise NotImplementedError

    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力的便捷入口。"""
        return self.capabilities

    def get_platform_name(self) -> str:
        """获取当前适配器的平台标识名称。"""
        return self.capabilities.platform_name

    @abstractmethod
    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """
        将平台无关的统一消息列表转换回当前平台的原生字典格式。

        此方法主要用于向后兼容，使新的统一接口能与依赖原生数据结构的旧版分析逻辑协同工作。

        Args:
            messages (list[UnifiedMessage]): 待转换的统一消息列表

        Returns:
            list[dict]: 转换后的平台原生消息字典列表
        """
        raise NotImplementedError

    async def send_forward_msg(
        self,
        group_id: str,
        nodes: list[dict],
    ) -> bool:
        """
        发送合并转发消息（基类默认实现：转换为格式化文本分段发送）。
        各适配器可覆盖此方法实现原生合并转发。
        """
        if not nodes:
            return True

        # 万能回退：将节点重新组合成易读的长文本
        lines = []
        for node in nodes:
            data = node.get("data", node)
            name = data.get("name", "Daily Analysis")
            content = data.get("content", "")
            if content:
                lines.append(f"【{name}】\n{content}")

        full_text = "\n\n".join(lines)

        # 处理超长文本分段（取大部分平台的安全阈值 1800 字符）
        max_chunk_size = 1800
        if len(full_text) > max_chunk_size:
            # 尝试在换行处拆分
            chunks = []
            curr = full_text
            while len(curr) > max_chunk_size:
                # 寻找最近的换行符
                split_idx = curr.rfind("\n", 0, max_chunk_size)
                if split_idx == -1:
                    split_idx = max_chunk_size
                chunks.append(curr[:split_idx].strip())
                curr = curr[split_idx:].strip()
            if curr:
                chunks.append(curr)

            for chunk in chunks:
                if not await self.send_text(group_id, chunk):
                    return False
            return True
        else:
            return await self.send_text(group_id, full_text)

    async def set_reaction(
        self, group_id: str, message_id: str, emoji: str | int, is_add: bool = True
    ) -> bool:
        """
        对消息添加/移除表情回应。

        Args:
            group_id (str): 群组/频道 ID
            message_id (str): 消息 ID
            emoji (str | int): 表情代码或字符
            is_add (bool): True 为添加，False 为移除

        Returns:
            bool: 平台是否支持并成功执行
        """
        return False

    async def send_text_report(self, group_id: str, content: str) -> bool:
        """
        以最适合当前平台的方式发送长文本报告。
        默认逻辑：将长文本切分为多个节点，然后调用 send_forward_msg。
        各平台适配器通过实现 send_forward_msg 来决定最终呈现形式（合并转发、分段发送等）。
        """
        import re

        try:
            # 1. 准备节点基础信息
            self_id = self.bot_self_ids[0] if self.bot_self_ids else "bot"
            self_name = "分析报告"
            # 2. 切分文本为逻辑段落（按标题、空行切分）
            raw_content = str(content)
            sections = re.split(r"\n+(?=[🎯📊💬🏆])|\n{2,}", raw_content.strip())
            nodes = []

            for sec in sections:
                if not sec.strip():
                    continue
                nodes.append(
                    {
                        "type": "node",
                        "data": {
                            "name": self_name,
                            "uin": self_id,
                            "content": sec.strip(),
                        },
                    }
                )

            if not nodes:
                return await self.send_text(group_id, raw_content)

            # 3. 尝试发送转发消息/长消息链
            return await self.send_forward_msg(group_id, nodes)
        except Exception:
            # 兜底：直接发送
            return await self.send_text(group_id, str(content))
