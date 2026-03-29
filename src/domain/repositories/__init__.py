# 仓储接口
from .avatar_repository import IAvatarRepository
from .message_repository import IGroupInfoRepository, IMessageRepository, IMessageSender

__all__ = [
    "IAvatarRepository",
    "IGroupInfoRepository",
    "IMessageRepository",
    "IMessageSender",
]
