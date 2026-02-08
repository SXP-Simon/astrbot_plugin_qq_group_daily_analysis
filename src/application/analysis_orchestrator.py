"""
分析编排器 - 应用层协调器

此编排器连接新的 DDD 架构与现有的分析逻辑，提供渐进式迁移路径。

架构决策：
- 编排器使用 PlatformAdapter 获取消息（新的 DDD 方式）
- 但将 LLM 分析委托给现有分析器（保留已工作的代码）
- MessageConverter 提供双向转换以保持兼容性
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..utils.logger import logger

from ..domain.value_objects.unified_message import UnifiedMessage
from ..domain.value_objects.platform_capabilities import PlatformCapabilities
from ..infrastructure.platform import PlatformAdapter, PlatformAdapterFactory
from .message_converter import MessageConverter


@dataclass
class AnalysisConfig:
    """分析操作配置"""

    days: int = 1
    max_messages: int = 1000
    min_messages_threshold: int = 10
    output_format: str = "image"


class AnalysisOrchestrator:
    """
    分析编排器 - 协调分析工作流。

    职责：
    1. 使用 PlatformAdapter 获取消息（DDD 方式）
    2. 转换消息以兼容现有分析器
    3. 协调分析流程
    4. 提供平台能力检查

    此类作为以下组件之间的桥梁：
    - 新的 DDD 基础设施（PlatformAdapter, UnifiedMessage）
    - 现有分析逻辑（MessageHandler, LLMAnalyzer 等）
    """

    def __init__(
        self,
        adapter: PlatformAdapter,
        config: AnalysisConfig = None,
    ):
        """
        初始化编排器。

        参数：
            adapter: 用于消息操作的平台适配器
            config: 分析配置
        """
        self.adapter = adapter
        self.config = config or AnalysisConfig()

    @classmethod
    def create_for_platform(
        cls,
        platform_name: str,
        bot_instance: Any,
        config: dict = None,
        analysis_config: AnalysisConfig = None,
    ) -> Optional["AnalysisOrchestrator"]:
        """
        工厂方法 - 为特定平台创建编排器。

        参数：
            platform_name: 平台名称（如 "aiocqhttp", "telegram"）
            bot_instance: 来自 AstrBot 的 bot 实例
            config: 平台特定配置
            analysis_config: 分析配置

        返回：
            AnalysisOrchestrator 或 None（如果平台不支持）
        """
        adapter = PlatformAdapterFactory.create(platform_name, bot_instance, config)
        if adapter is None:
            logger.warning(f"平台 '{platform_name}' 不支持分析功能")
            return None

        return cls(adapter, analysis_config)

    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力。"""
        return self.adapter.get_capabilities()

    def can_analyze(self) -> bool:
        """检查平台是否支持分析。"""
        return self.adapter.get_capabilities().can_analyze()

    def can_send_report(self, format: str = "image") -> bool:
        """检查平台是否能发送指定格式的报告。"""
        return self.adapter.get_capabilities().can_send_report(format)

    async def fetch_messages(
        self,
        group_id: str,
        days: int = None,
        max_count: int = None,
    ) -> List[UnifiedMessage]:
        """
        使用平台适配器获取消息。

        参数：
            group_id: 要获取消息的群组 ID
            days: 天数（默认使用配置值）
            max_count: 最大消息数量（默认使用配置值）

        返回：
            UnifiedMessage 列表
        """
        days = days or self.config.days
        max_count = max_count or self.config.max_messages

        # 应用平台能力限制
        caps = self.adapter.get_capabilities()
        effective_days = caps.get_effective_days(days)
        effective_count = caps.get_effective_count(max_count)

        if effective_days < days:
            logger.info(f"平台限制：请求 {days} 天，实际使用 {effective_days} 天")

        return await self.adapter.fetch_messages(
            group_id=group_id,
            days=effective_days,
            max_count=effective_count,
        )

    async def fetch_messages_as_raw(
        self,
        group_id: str,
        days: int = None,
        max_count: int = None,
    ) -> List[dict]:
        """
        获取消息并转换为原始字典格式。

        此方法提供与现有分析器的向后兼容性，
        这些分析器期望原始字典格式的消息。

        参数：
            group_id: 要获取消息的群组 ID
            days: 天数
            max_count: 最大消息数量

        返回：
            原始消息字典列表（通用格式，由适配器决定具体格式）
        """
        # unified_messages = await self.fetch_messages(group_id, days, max_count)
        #
        # # 如果适配器实现了 convert_to_raw_format，则使用它
        # if hasattr(self.adapter, "convert_to_raw_format"):
        #     return self.adapter.convert_to_raw_format(unified_messages)
        #
        # # 默认回退逻辑：手动转换
        # # 这可能不完美，但能保证基本的向后兼容性
        # return [
        #     {
        #         "message_id": msg.message_id,
        #         "group_id": msg.group_id,
        #         "sender": {
        #             "user_id": msg.sender_id,
        #             "nickname": msg.sender_name,
        #             "card": msg.sender_card
        #         },
        #         "time": msg.timestamp,
        #         "message": msg.text_content, # 简化处理
        #         "raw_message": msg.text_content
        #     }
        #     for msg in unified_messages
        # ]

        # 暂时直接使用适配器获取 raw 格式，如果适配器支持
        # 这是为了确保现有逻辑完全兼容，因为 convert_to_raw_format 可能有损
        # 但我们希望尽可能使用新的 fetch_messages

        unified_messages = await self.fetch_messages(group_id, days, max_count)
        return self.adapter.convert_to_raw_format(unified_messages)

    async def get_group_info(self, group_id: str):
        """获取群组信息。"""
        return await self.adapter.get_group_info(group_id)

    async def get_member_avatars(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """
        批量获取用户头像 URL。

        参数：
            user_ids: 用户 ID 列表
            size: 头像尺寸

        返回：
            用户 ID 到头像 URL 的映射字典（URL 可能为 None）
        """
        return await self.adapter.batch_get_avatar_urls(user_ids, size)

    async def send_text(self, group_id: str, text: str) -> bool:
        """发送文本消息到群组。"""
        return await self.adapter.send_text(group_id, text)

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片到群组。"""
        return await self.adapter.send_image(group_id, image_path, caption)

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str = None,
    ) -> bool:
        """发送文件到群组。"""
        return await self.adapter.send_file(group_id, file_path, filename)

    def validate_message_count(self, messages: List[UnifiedMessage]) -> bool:
        """
        检查消息数量是否达到最小阈值。

        参数：
            messages: 消息列表

        返回：
            如果数量足够返回 True
        """
        return len(messages) >= self.config.min_messages_threshold

    def get_analysis_text(self, messages: List[UnifiedMessage]) -> str:
        """
        将消息转换为 LLM 分析文本格式。

        参数：
            messages: UnifiedMessage 列表

        返回：
            格式化的 LLM 分析文本
        """
        return MessageConverter.unified_to_analysis_text(messages)
