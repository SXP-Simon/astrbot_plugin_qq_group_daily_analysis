"""
平台能力值对象 - 运行时决策支持

每个平台适配器声明其能力，
应用层根据能力决定操作。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapabilities:
    """
    值对象：平台能力描述

    用于在运行时判断当前平台支持哪些具体操作，实现防御性编程和多平台兼容。

    Attributes:
        platform_name (str): 平台标识（如 discord, onebot）
        platform_version (str): 版本号
        supports_message_history (bool): 是否支持拉取历史消息
        max_message_history_days (int): 最大历史穿透天数
        max_message_count (int): 单次拉取最大消息数
        supports_message_search (bool): 是否支持消息搜索（扩展用）
        supports_group_list (bool): 是否支持列出所有群组
        supports_group_info (bool): 是否支持获取群元数据
        supports_member_list (bool): 是否支持获取成员列表
        supports_member_info (bool): 是否支持获取单成员详情
        supports_text_message (bool): 是否能发送文本
        supports_image_message (bool): 是否能发送图片
        supports_file_message (bool): 是否能发送文件/PDF
        supports_forward_message (bool): 是否支持转发链（合并转发）
        supports_reply_message (bool): 是否支持回复引用
        max_text_length (int): 单条回复最大文本长度
        max_image_size_mb (float): 最大图片上传限制 (MB)
        supports_at_all (bool): 是否能 @全员
        supports_recall (bool): 是否支持撤回
        supports_edit (bool): 是否支持编辑已发消息
        supports_user_avatar (bool): 是否有用户头像 API
        supports_group_avatar (bool): 是否有群头像 API
        avatar_needs_api_call (bool): 获取头像是否需要额外异步请求
        avatar_sizes (tuple[int, ...]): 平台支持的头像尺寸像素值
    """

    # 平台标识
    platform_name: str
    platform_version: str = "unknown"

    # 消息获取能力
    supports_message_history: bool = False
    max_message_history_days: int = 0
    max_message_count: int = 0
    supports_message_search: bool = False

    # 群组信息能力
    supports_group_list: bool = False
    supports_group_info: bool = False
    supports_member_list: bool = False
    supports_member_info: bool = False

    # 消息发送能力
    supports_text_message: bool = True
    supports_image_message: bool = False
    supports_file_message: bool = False
    supports_forward_message: bool = False
    supports_reply_message: bool = False
    max_text_length: int = 4096
    max_image_size_mb: float = 10.0

    # 特殊能力
    supports_at_all: bool = False
    supports_recall: bool = False
    supports_edit: bool = False

    # 头像能力
    supports_user_avatar: bool = True
    supports_group_avatar: bool = False
    avatar_needs_api_call: bool = False
    avatar_sizes: tuple[int, ...] = (100,)

    # 检查方法
    def can_analyze(self) -> bool:
        """
        判断是否具备进行群聊分析的核心能力。

        Returns:
            bool: 核心能力齐全则返回 True
        """
        return (
            self.supports_message_history
            and self.max_message_history_days > 0
            and self.max_message_count > 0
        )

    def can_send_report(self, format: str = "image") -> bool:
        """
        判断是否能以指定格式发送报告。

        Args:
            format (str): 报告格式 ('text', 'image', 'pdf')

        Returns:
            bool: 支持该格式则返回 True
        """
        if format == "text":
            return self.supports_text_message
        elif format == "image":
            return self.supports_image_message
        elif format == "pdf":
            return self.supports_file_message
        return False

    def get_effective_days(self, requested_days: int) -> int:
        """
        获取实际生效的历史拉取天数。

        Args:
            requested_days (int): 请求的天数

        Returns:
            int: 平台受限后的实际天数
        """
        return min(requested_days, self.max_message_history_days)

    def get_effective_count(self, requested_count: int) -> int:
        """
        获取实际生效的历史消息拉取条数。

        Args:
            requested_count (int): 请求的消息条数

        Returns:
            int: 平台受限后的实际条数
        """
        return min(requested_count, self.max_message_count)


# 预定义的平台能力
# OneBot v11 (如 NapCat, LLOneBot 等)
ONEBOT_V11_CAPABILITIES = PlatformCapabilities(
    platform_name="onebot",
    platform_version="v11",
    supports_message_history=True,
    max_message_history_days=7,
    max_message_count=10000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_member_info=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_forward_message=True,
    supports_reply_message=True,
    max_text_length=4500,
    supports_at_all=True,
    supports_recall=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(40, 100, 140, 160, 640),
)

# Telegram Bot API
TELEGRAM_CAPABILITIES = PlatformCapabilities(
    platform_name="telegram",
    platform_version="bot_api_7.x",
    # 通过 PlatformMessageHistoryManager + 消息拦截器支持历史读取
    supports_message_history=True,
    max_message_history_days=7,
    max_message_count=1000,
    supports_group_list=False,
    supports_group_info=True,
    supports_member_list=True,
    supports_member_info=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=4096,
    max_image_size_mb=50.0,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=True,
    avatar_sizes=(160, 320, 640),
)

# Discord API
DISCORD_CAPABILITIES = PlatformCapabilities(
    platform_name="discord",
    platform_version="api_v10",
    supports_message_history=True,
    max_message_history_days=30,
    max_message_count=10000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=2000,
    max_image_size_mb=8.0,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(16, 32, 64, 128, 256, 512, 1024, 2048, 4096),
)

# Slack Web API
SLACK_CAPABILITIES = PlatformCapabilities(
    platform_name="slack",
    platform_version="web_api",
    supports_message_history=True,
    max_message_history_days=90,
    max_message_count=1000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=40000,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=False,
    avatar_needs_api_call=True,
    avatar_sizes=(24, 32, 48, 72, 192, 512, 1024),
)

# 能力查找表（映射平台标识到能力对象）
PLATFORM_CAPABILITIES: dict[str, PlatformCapabilities] = {
    "aiocqhttp": ONEBOT_V11_CAPABILITIES,
    "onebot": ONEBOT_V11_CAPABILITIES,
    "telegram": TELEGRAM_CAPABILITIES,
    "discord": DISCORD_CAPABILITIES,
    "slack": SLACK_CAPABILITIES,
}


def get_capabilities(platform_name: str) -> PlatformCapabilities | None:
    """
    根据平台名称查找其支持的能力。

    Args:
        platform_name (str): 平台名称

    Returns:
        Optional[PlatformCapabilities]: 对应的能力对象或 None
    """
    return PLATFORM_CAPABILITIES.get(platform_name.lower())
