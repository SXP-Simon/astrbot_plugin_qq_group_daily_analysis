# 仓储接口与协议
from .analysis_repository import IAnalysisProvider
from .avatar_repository import IAvatarRepository
from .bot_client_protocol import (
    DiscordChannelProtocol,
    DiscordClientProtocol,
    DiscordMessageProtocol,
    DiscordUserProtocol,
    OneBotClientProtocol,
    TelegramClientProtocol,
    TelegramUserProtocol,
)
from .config_repository import IConfigProvider
from .message_repository import (
    IGroupInfoRepository,
    IMessageRepository,
    IMessageSender,
)
from .persistence_repository import ICheckpointStore, IIncrementalStore
from .platform_adapter_repository import (
    GroupAlbumSupportProtocol,
    GroupFileSupportProtocol,
    PlatformAdapterProtocol,
)
from .plugin_host_repository import PluginHostProtocol
from .report_repository import IReportGenerator
from .visualization_repository import IActivityVisualizer

__all__ = [
    "DiscordChannelProtocol",
    "DiscordClientProtocol",
    "DiscordMessageProtocol",
    "DiscordUserProtocol",
    "GroupAlbumSupportProtocol",
    "GroupFileSupportProtocol",
    "IActivityVisualizer",
    "IAnalysisProvider",
    "IAvatarRepository",
    "ICheckpointStore",
    "IConfigProvider",
    "IGroupInfoRepository",
    "IIncrementalStore",
    "IMessageRepository",
    "IMessageSender",
    "IReportGenerator",
    "OneBotClientProtocol",
    "PlatformAdapterProtocol",
    "PluginHostProtocol",
    "TelegramClientProtocol",
    "TelegramUserProtocol",
]
