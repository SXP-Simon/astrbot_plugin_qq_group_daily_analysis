# Repository Interfaces
from .message_repository import IMessageRepository, IMessageSender, IGroupInfoRepository
from .avatar_repository import IAvatarRepository

__all__ = [
    "IMessageRepository",
    "IMessageSender", 
    "IGroupInfoRepository",
    "IAvatarRepository",
]
