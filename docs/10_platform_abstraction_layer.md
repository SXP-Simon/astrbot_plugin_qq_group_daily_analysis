# 10. 平台抽象层详细设计 (Platform Abstraction Layer Design)

> **文档日期**: 2026-02-08
> **版本**: v1.1
> **前置文档**: 09_ddd_cross_platform_complete_guide.md
> **目的**: 详细定义平台上下文的设计、仓储接口、适配器实现示例
> **更新**: v1.1 添加用户头像获取跨平台抽象

---

## 1. 平台限界上下文 (Platform Bounded Context)

### 1.1 上下文定位

平台上下文是整个插件的**反腐败层 (Anti-Corruption Layer)**，负责：

1. **隔离外部平台差异** - 将不同平台的 API 差异封装在适配器内
2. **提供统一抽象** - 向领域层暴露统一的消息、群组、发送接口
3. **声明平台能力** - 让应用层知道当前平台支持哪些功能

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        平台限界上下文 (Platform Context)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         领域模型 (Domain Model)                         │ │
│  │                                                                        │ │
│  │  值对象:                                                               │ │
│  │  - UnifiedMessage: 统一消息格式                                        │ │
│  │  - MessageContent: 消息内容片段                                        │ │
│  │  - PlatformCapabilities: 平台能力描述                                  │ │
│  │  - UnifiedGroup: 统一群组信息                                          │ │
│  │  - UnifiedMember: 统一成员信息                                         │ │
│  │                                                                        │ │
│  │  仓储接口:                                                             │ │
│  │  - IMessageRepository: 消息获取                                        │ │
│  │  - IMessageSender: 消息发送                                            │ │
│  │  - IGroupInfoRepository: 群组信息                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      适配器层 (Adapter Layer)                           │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ OneBotAdapter│  │TelegramAdapter│ │DiscordAdapter│                 │ │
│  │  │              │  │              │  │              │                 │ │
│  │  │ - QQ/OneBot  │  │ - Bot API    │  │ - pycord     │                 │ │
│  │  │ - v11/v12    │  │ - 6.x/7.x    │  │ - 2.x        │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ SlackAdapter │  │ LarkAdapter  │  │DingTalkAdapter│                │ │
│  │  │              │  │   (飞书)     │  │    (钉钉)     │                 │ │
│  │  │ - Bolt API   │  │ - Open API   │  │ - Robot API  │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         工厂 (Factory)                                  │ │
│  │                                                                        │ │
│  │  PlatformAdapterFactory.create(platform_name, bot_instance, config)    │ │
│  │    → 返回 PlatformAdapter 实例                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 上下文边界

| 边界内 (In Context) | 边界外 (Out of Context) |
|---------------------|------------------------|
| 消息格式转换 | 消息分析逻辑 |
| 平台 API 调用 | 报告生成 |
| 能力声明 | 定时调度 |
| 错误转换 | 业务规则 |

---

## 2. 核心值对象设计

### 2.1 UnifiedMessage (统一消息)

```python
# src/domain/value_objects/unified_message.py
from dataclasses import dataclass, field
from typing import Optional, Any, Tuple
from enum import Enum
from datetime import datetime


class MessageContentType(Enum):
    """消息内容类型枚举"""
    TEXT = "text"           # 纯文本
    IMAGE = "image"         # 图片
    FILE = "file"           # 文件
    EMOJI = "emoji"         # 表情/贴纸
    REPLY = "reply"         # 回复引用
    FORWARD = "forward"     # 转发
    AT = "at"               # @提及
    VOICE = "voice"         # 语音
    VIDEO = "video"         # 视频
    LOCATION = "location"   # 位置
    UNKNOWN = "unknown"     # 未知类型


@dataclass(frozen=True)
class MessageContent:
    """
    消息内容片段值对象
    
    不可变，用于组成消息链
    """
    type: MessageContentType
    text: str = ""
    url: str = ""
    emoji_id: str = ""
    emoji_name: str = ""
    at_user_id: str = ""
    raw_data: Any = None  # 保留原始数据用于调试
    
    def is_text(self) -> bool:
        return self.type == MessageContentType.TEXT
    
    def is_emoji(self) -> bool:
        return self.type == MessageContentType.EMOJI


@dataclass(frozen=True)
class UnifiedMessage:
    """
    统一消息格式 - 跨平台核心值对象
    
    设计原则:
    1. 只保留分析需要的字段
    2. 使用平台无关的类型
    3. 不可变 (frozen=True) - 线程安全
    4. 所有 ID 都是字符串 - 避免平台差异
    """
    # 基础标识
    message_id: str
    sender_id: str
    sender_name: str
    group_id: str
    
    # 消息内容
    text_content: str  # 提取的纯文本，用于 LLM 分析
    contents: Tuple[MessageContent, ...] = field(default_factory=tuple)  # 完整消息链
    
    # 时间信息
    timestamp: int = 0  # Unix 时间戳
    
    # 平台信息
    platform: str = "unknown"  # 来源平台标识
    
    # 可选信息
    reply_to_id: Optional[str] = None  # 回复的消息 ID
    sender_card: Optional[str] = None  # 群名片/备注
    
    # 分析辅助方法
    def has_text(self) -> bool:
        """是否有文本内容"""
        return bool(self.text_content.strip())
    
    def get_display_name(self) -> str:
        """获取显示名称，优先群名片"""
        return self.sender_card or self.sender_name or self.sender_id
    
    def get_emoji_count(self) -> int:
        """获取表情数量"""
        return sum(1 for c in self.contents if c.is_emoji())
    
    def get_text_length(self) -> int:
        """获取文本长度"""
        return len(self.text_content)
    
    def get_datetime(self) -> datetime:
        """获取消息时间"""
        return datetime.fromtimestamp(self.timestamp)
    
    def to_analysis_format(self) -> str:
        """转换为分析格式（用于 LLM）"""
        name = self.get_display_name()
        return f"[{name}]: {self.text_content}"


# 消息列表类型别名
MessageList = list[UnifiedMessage]
```

### 2.2 PlatformCapabilities (平台能力)

```python
# src/domain/value_objects/platform_capabilities.py
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformCapabilities:
    """
    平台能力描述 - 用于运行时决策
    
    每个平台适配器必须声明自己的能力，
    应用层根据能力决定是否可以执行某些操作。
    
    设计原则:
    1. 所有字段都有默认值（最保守的假设）
    2. 不可变
    3. 提供便捷的检查方法
    """
    # 平台标识
    platform_name: str
    platform_version: str = "unknown"
    
    # ========== 消息获取能力 ==========
    supports_message_history: bool = False  # 是否支持获取历史消息
    max_message_history_days: int = 0       # 最大历史天数
    max_message_count: int = 0              # 单次最大消息数
    supports_message_search: bool = False   # 是否支持消息搜索
    
    # ========== 群组信息能力 ==========
    supports_group_list: bool = False       # 是否支持获取群列表
    supports_group_info: bool = False       # 是否支持获取群信息
    supports_member_list: bool = False      # 是否支持获取成员列表
    supports_member_info: bool = False      # 是否支持获取成员信息
    
    # ========== 消息发送能力 ==========
    supports_text_message: bool = True      # 发送文本
    supports_image_message: bool = False    # 发送图片
    supports_file_message: bool = False     # 发送文件
    supports_forward_message: bool = False  # 转发消息
    supports_reply_message: bool = False    # 回复消息
    max_text_length: int = 4096             # 最大文本长度
    max_image_size_mb: float = 10.0         # 最大图片大小
    
    # ========== 特殊能力 ==========
    supports_at_all: bool = False           # @全体成员
    supports_recall: bool = False           # 撤回消息
    supports_edit: bool = False             # 编辑消息
    
    # ========== 头像能力 ==========
    supports_user_avatar: bool = True       # 是否支持获取用户头像
    supports_group_avatar: bool = False     # 是否支持获取群组头像
    avatar_needs_api_call: bool = False     # 获取头像是否需要 API 调用
    avatar_sizes: tuple = (100,)            # 可用的头像尺寸
    
    # ========== 检查方法 ==========
    def can_analyze(self) -> bool:
        """是否支持群聊分析（核心能力）"""
        return (
            self.supports_message_history 
            and self.max_message_history_days > 0
            and self.max_message_count > 0
        )
    
    def can_send_report(self, format: str = "image") -> bool:
        """是否可以发送报告"""
        if format == "text":
            return self.supports_text_message
        elif format == "image":
            return self.supports_image_message
        elif format == "pdf":
            return self.supports_file_message
        return False
    
    def get_effective_days(self, requested_days: int) -> int:
        """获取实际可用的天数"""
        return min(requested_days, self.max_message_history_days)
    
    def get_effective_count(self, requested_count: int) -> int:
        """获取实际可用的消息数"""
        return min(requested_count, self.max_message_count)


# ========== 预定义平台能力 ==========

ONEBOT_V11_CAPABILITIES = PlatformCapabilities(
    platform_name="onebot",
    platform_version="v11",
    # 消息历史
    supports_message_history=True,
    max_message_history_days=7,
    max_message_count=10000,
    # 群组
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_member_info=True,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_forward_message=True,
    supports_reply_message=True,
    max_text_length=4500,
    # 特殊
    supports_at_all=True,
    supports_recall=True,
    # 头像 - QQ 通过 URL 模板直接构造，无需 API 调用
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(40, 100, 140, 160, 640),
)

TELEGRAM_CAPABILITIES = PlatformCapabilities(
    platform_name="telegram",
    platform_version="bot_api_7.x",
    # 消息历史 - Telegram Bot API 不支持获取历史消息
    # 需要使用 Telethon (MTProto) 才能获取
    supports_message_history=False,  # Bot API 不支持
    max_message_history_days=0,
    max_message_count=0,
    # 群组
    supports_group_list=False,  # Bot 只能看到自己在的群
    supports_group_info=True,
    supports_member_list=True,  # 需要管理员权限
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=4096,
    max_image_size_mb=50.0,
    # 特殊
    supports_edit=True,
    # 头像 - 需要调用 getUserProfilePhotos + getFile API
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=True,
    avatar_sizes=(160, 320, 640),
)

TELEGRAM_USERBOT_CAPABILITIES = PlatformCapabilities(
    platform_name="telegram_userbot",
    platform_version="telethon",
    # UserBot 可以获取历史消息
    supports_message_history=True,
    max_message_history_days=365,
    max_message_count=10000,
    # 群组
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    # 头像
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=True,
    avatar_sizes=(160, 320, 640),
)

DISCORD_CAPABILITIES = PlatformCapabilities(
    platform_name="discord",
    platform_version="api_v10",
    # Discord 支持获取历史消息
    supports_message_history=True,
    max_message_history_days=30,
    max_message_count=10000,
    # 群组
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=2000,
    max_image_size_mb=8.0,
    # 特殊
    supports_edit=True,
    # 头像 - 通过 CDN URL 模板构造，无需 API 调用
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(16, 32, 64, 128, 256, 512, 1024, 2048, 4096),
)

SLACK_CAPABILITIES = PlatformCapabilities(
    platform_name="slack",
    platform_version="web_api",
    # Slack 支持获取历史消息
    supports_message_history=True,
    max_message_history_days=90,  # 免费版有限制
    max_message_count=1000,
    # 群组
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=40000,
    # 特殊
    supports_edit=True,
    # 头像 - 从 users.info API 的 profile.image_* 字段获取
    supports_user_avatar=True,
    supports_group_avatar=False,  # Slack 频道没有头像
    avatar_needs_api_call=True,
    avatar_sizes=(24, 32, 48, 72, 192, 512, 1024),
)

LARK_CAPABILITIES = PlatformCapabilities(
    platform_name="lark",
    platform_version="open_api",
    # 飞书支持获取历史消息
    supports_message_history=True,
    max_message_history_days=30,
    max_message_count=50,  # 每次请求最多 50 条
    # 群组
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    # 头像 - 从用户信息 API 的 avatar 字段获取
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=True,
    avatar_sizes=(72, 240, 640),
)

DINGTALK_CAPABILITIES = PlatformCapabilities(
    platform_name="dingtalk",
    platform_version="robot_api",
    # 钉钉机器人不支持获取历史消息
    supports_message_history=False,
    max_message_history_days=0,
    max_message_count=0,
    # 群组
    supports_group_list=False,
    supports_group_info=False,
    supports_member_list=False,
    # 发送
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    # 头像 - 钉钉机器人 API 不支持获取头像
    supports_user_avatar=False,
    supports_group_avatar=False,
    avatar_needs_api_call=False,
    avatar_sizes=(),
)


# 能力查找表
PLATFORM_CAPABILITIES = {
    "aiocqhttp": ONEBOT_V11_CAPABILITIES,
    "onebot": ONEBOT_V11_CAPABILITIES,
    "telegram": TELEGRAM_CAPABILITIES,
    "telegram_userbot": TELEGRAM_USERBOT_CAPABILITIES,
    "discord": DISCORD_CAPABILITIES,
    "slack": SLACK_CAPABILITIES,
    "lark": LARK_CAPABILITIES,
    "feishu": LARK_CAPABILITIES,  # 别名
    "dingtalk": DINGTALK_CAPABILITIES,
}


def get_capabilities(platform_name: str) -> Optional[PlatformCapabilities]:
    """根据平台名称获取能力描述"""
    return PLATFORM_CAPABILITIES.get(platform_name.lower())
```

### 2.3 UnifiedGroup (统一群组信息)

```python
# src/domain/value_objects/unified_group.py
from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class UnifiedMember:
    """统一成员信息"""
    user_id: str
    nickname: str
    card: Optional[str] = None  # 群名片
    role: str = "member"  # owner, admin, member
    join_time: Optional[int] = None
    avatar_url: Optional[str] = None  # 头像 URL
    avatar_data: Optional[str] = None  # 头像 Base64 数据 (用于模板渲染)
    
    def get_display_name(self) -> str:
        return self.card or self.nickname or self.user_id


@dataclass(frozen=True)
class UnifiedGroup:
    """统一群组信息"""
    group_id: str
    group_name: str
    member_count: int = 0
    owner_id: Optional[str] = None
    create_time: Optional[int] = None
    description: Optional[str] = None
    platform: str = "unknown"
```

---

## 3. 仓储接口设计

### 3.1 IMessageRepository (消息仓储)

```python
# src/domain/repositories/message_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional
from ..value_objects.unified_message import UnifiedMessage
from ..value_objects.platform_capabilities import PlatformCapabilities


class IMessageRepository(ABC):
    """
    消息仓储接口
    
    每个平台适配器必须实现此接口。
    所有方法都返回统一格式，隐藏平台差异。
    """
    
    @abstractmethod
    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """
        获取群组历史消息
        
        Args:
            group_id: 群组 ID
            days: 获取最近 N 天的消息
            max_count: 最大消息数量
            before_id: 获取此消息之前的消息（用于分页）
            
        Returns:
            统一格式的消息列表，按时间升序排列
            
        Raises:
            PlatformNotSupportedError: 平台不支持此功能
            PlatformAPIError: API 调用失败
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力描述"""
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """获取平台名称"""
        pass


class IMessageSender(ABC):
    """
    消息发送接口
    """
    
    @abstractmethod
    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        发送文本消息
        
        Args:
            group_id: 目标群组
            text: 文本内容
            reply_to: 回复的消息 ID（可选）
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """
        发送图片消息
        
        Args:
            group_id: 目标群组
            image_path: 图片本地路径或 URL
            caption: 图片说明（可选）
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """
        发送文件
        
        Args:
            group_id: 目标群组
            file_path: 文件本地路径
            filename: 显示的文件名（可选）
            
        Returns:
            是否发送成功
        """
        pass
    
    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力描述"""
        pass


class IGroupInfoRepository(ABC):
    """
    群组信息仓储接口
    """
    
    @abstractmethod
    async def get_group_info(self, group_id: str) -> Optional['UnifiedGroup']:
        """获取群组信息"""
        pass
    
    @abstractmethod
    async def get_group_list(self) -> List[str]:
        """获取 Bot 所在的所有群组 ID"""
        pass
    
    @abstractmethod
    async def get_member_list(self, group_id: str) -> List['UnifiedMember']:
        """获取群组成员列表"""
        pass
    
    @abstractmethod
    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional['UnifiedMember']:
        """获取指定成员信息"""
        pass


class IAvatarRepository(ABC):
    """
    头像仓储接口
    
    用于获取用户和群组头像，每个平台的实现方式不同：
    - QQ/OneBot: 通过 URL 模板直接构造 (q1.qlogo.cn)
    - Telegram: 需要调用 API 获取 file_id 再转换为 URL
    - Discord: 通过 CDN URL 模板构造 (cdn.discordapp.com)
    - Slack: 从用户信息的 profile.image_* 字段获取
    - 飞书: 从用户信息的 avatar 字段获取
    """
    
    @abstractmethod
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取用户头像 URL
        
        Args:
            user_id: 用户 ID
            size: 期望的头像尺寸 (会选择最接近的可用尺寸)
            
        Returns:
            头像 URL，如果无法获取则返回 None
        """
        pass
    
    @abstractmethod
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取用户头像的 Base64 数据
        
        用于需要内嵌图片的场景（如 HTML 模板渲染）
        
        Args:
            user_id: 用户 ID
            size: 期望的头像尺寸
            
        Returns:
            Base64 编码的图片数据 (data:image/png;base64,...)，
            如果无法获取则返回 None
        """
        pass
    
    @abstractmethod
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取群组头像 URL
        
        Args:
            group_id: 群组 ID
            size: 期望的头像尺寸
            
        Returns:
            群组头像 URL，如果无法获取则返回 None
        """
        pass
    
    @abstractmethod
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """
        批量获取用户头像 URL
        
        用于报告生成等需要一次性获取多个头像的场景
        
        Args:
            user_ids: 用户 ID 列表
            size: 期望的头像尺寸
            
        Returns:
            用户 ID 到头像 URL 的映射，无法获取的用户值为 None
        """
        pass
    
    def get_default_avatar_url(self) -> str:
        """获取默认头像 URL（当无法获取用户头像时使用）"""
        # 可以返回一个通用的默认头像
        return "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDEyYzIuMjEgMCA0LTEuNzkgNC00cy0xLjc5LTQtNC00LTQgMS43OS00IDQgMS43OSA0IDQgNHptMCAyYy0yLjY3IDAtOCAxLjM0LTggNHYyaDE2di0yYzAtMi42Ni01LjMzLTQtOC00eiIvPjwvc3ZnPg=="
```

### 3.2 头像获取各平台实现策略

由于各平台头像获取方式差异较大，下面详细说明每个平台的实现策略：

#### 3.2.1 QQ/OneBot 头像获取

QQ 头像可以通过 URL 模板直接构造，无需 API 调用：

```python
# src/infrastructure/platform/adapters/onebot_avatar.py

class OneBotAvatarRepository(IAvatarRepository):
    """OneBot 头像仓储实现"""
    
    # QQ 头像 URL 模板
    USER_AVATAR_TEMPLATE = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
    USER_AVATAR_HD_TEMPLATE = "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec={size}&img_type=jpg"
    GROUP_AVATAR_TEMPLATE = "https://p.qlogo.cn/gh/{group_id}/{group_id}/{size}/"
    
    # 可用的尺寸选项
    AVAILABLE_SIZES = [40, 100, 140, 160, 640]
    
    def _get_nearest_size(self, requested_size: int) -> int:
        """获取最接近的可用尺寸"""
        return min(self.AVAILABLE_SIZES, key=lambda x: abs(x - requested_size))
    
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 用户头像 URL"""
        actual_size = self._get_nearest_size(size)
        if actual_size >= 640:
            # 使用高清头像模板
            return self.USER_AVATAR_HD_TEMPLATE.format(
                user_id=user_id,
                size=640
            )
        return self.USER_AVATAR_TEMPLATE.format(
            user_id=user_id,
            size=actual_size
        )
    
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 用户头像的 Base64 数据"""
        import aiohttp
        import base64
        
        url = await self.get_user_avatar_url(user_id, size)
        if not url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        content_type = resp.headers.get('Content-Type', 'image/png')
                        return f"data:{content_type};base64,{b64}"
        except Exception:
            pass
        return None
    
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 群头像 URL"""
        actual_size = self._get_nearest_size(size)
        return self.GROUP_AVATAR_TEMPLATE.format(
            group_id=group_id,
            size=actual_size
        )
    
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 QQ 用户头像 URL（无需 API 调用，直接构造）"""
        return {
            user_id: await self.get_user_avatar_url(user_id, size)
            for user_id in user_ids
        }
```

#### 3.2.2 Telegram 头像获取

Telegram 需要通过 Bot API 获取用户头像：

```python
# src/infrastructure/platform/adapters/telegram_avatar.py

class TelegramAvatarRepository(IAvatarRepository):
    """Telegram 头像仓储实现"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.file_base = f"https://api.telegram.org/file/bot{bot_token}"
    
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取 Telegram 用户头像 URL
        
        流程:
        1. 调用 getUserProfilePhotos 获取用户头像列表
        2. 选择合适尺寸的 PhotoSize
        3. 调用 getFile 获取 file_path
        4. 构造完整的文件 URL
        """
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: 获取用户头像列表
                photos_url = f"{self.api_base}/getUserProfilePhotos"
                async with session.get(photos_url, params={
                    "user_id": user_id,
                    "limit": 1
                }) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    
                if not data.get("ok") or not data.get("result", {}).get("photos"):
                    return None
                
                # Step 2: 选择合适尺寸的 PhotoSize
                photos = data["result"]["photos"][0]  # 最新的头像
                # Telegram 提供多个尺寸: 小(160x160), 中(320x320), 大(640x640)
                # 选择最接近请求尺寸的
                best_photo = min(photos, key=lambda p: abs(p.get("width", 0) - size))
                file_id = best_photo.get("file_id")
                
                if not file_id:
                    return None
                
                # Step 3: 获取 file_path
                file_url = f"{self.api_base}/getFile"
                async with session.get(file_url, params={"file_id": file_id}) as resp:
                    if resp.status != 200:
                        return None
                    file_data = await resp.json()
                
                if not file_data.get("ok"):
                    return None
                
                file_path = file_data["result"].get("file_path")
                if not file_path:
                    return None
                
                # Step 4: 构造完整 URL
                return f"{self.file_base}/{file_path}"
                
        except Exception:
            return None
    
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Telegram 用户头像的 Base64 数据"""
        import aiohttp
        import base64
        
        url = await self.get_user_avatar_url(user_id, size)
        if not url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        return f"data:image/jpeg;base64,{b64}"
        except Exception:
            pass
        return None
    
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Telegram 群组头像 URL"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                # 获取群组信息
                chat_url = f"{self.api_base}/getChat"
                async with session.get(chat_url, params={"chat_id": group_id}) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                
                if not data.get("ok"):
                    return None
                
                photo = data["result"].get("photo")
                if not photo:
                    return None
                
                # 获取大尺寸头像
                file_id = photo.get("big_file_id") or photo.get("small_file_id")
                if not file_id:
                    return None
                
                # 获取 file_path
                file_url = f"{self.api_base}/getFile"
                async with session.get(file_url, params={"file_id": file_id}) as resp:
                    if resp.status != 200:
                        return None
                    file_data = await resp.json()
                
                if not file_data.get("ok"):
                    return None
                
                file_path = file_data["result"].get("file_path")
                return f"{self.file_base}/{file_path}" if file_path else None
                
        except Exception:
            return None
    
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 Telegram 用户头像 URL"""
        import asyncio
        
        async def get_avatar(user_id: str):
            return user_id, await self.get_user_avatar_url(user_id, size)
        
        results = await asyncio.gather(*[get_avatar(uid) for uid in user_ids])
        return dict(results)
```

#### 3.2.3 Discord 头像获取

Discord 头像可以通过 CDN URL 模板构造：

```python
# src/infrastructure/platform/adapters/discord_avatar.py

class DiscordAvatarRepository(IAvatarRepository):
    """Discord 头像仓储实现"""
    
    CDN_BASE = "https://cdn.discordapp.com"
    
    # 有效尺寸: 16, 32, 64, 128, 256, 512, 1024, 2048, 4096
    VALID_SIZES = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
    
    def __init__(self, user_cache: dict = None):
        """
        Args:
            user_cache: 用户信息缓存 {user_id: {"avatar": "hash", "discriminator": "0"}}
        """
        self.user_cache = user_cache or {}
    
    def _get_valid_size(self, requested_size: int) -> int:
        """获取有效的尺寸（必须是 2 的幂次方，16-4096）"""
        for size in self.VALID_SIZES:
            if size >= requested_size:
                return size
        return 1024  # 默认
    
    def _get_default_avatar_index(self, user_id: str, discriminator: str = "0") -> int:
        """计算默认头像索引"""
        if discriminator == "0":
            # 新用户名系统: (user_id >> 22) % 6
            return (int(user_id) >> 22) % 6
        else:
            # 旧系统: int(discriminator) % 5
            return int(discriminator) % 5
    
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 用户头像 URL"""
        actual_size = self._get_valid_size(size)
        
        user_info = self.user_cache.get(user_id, {})
        avatar_hash = user_info.get("avatar")
        
        if avatar_hash:
            # 有自定义头像
            # 检查是否是动态头像 (以 a_ 开头)
            is_animated = avatar_hash.startswith("a_")
            ext = "gif" if is_animated else "png"
            return f"{self.CDN_BASE}/avatars/{user_id}/{avatar_hash}.{ext}?size={actual_size}"
        else:
            # 使用默认头像
            discriminator = user_info.get("discriminator", "0")
            index = self._get_default_avatar_index(user_id, discriminator)
            return f"{self.CDN_BASE}/embed/avatars/{index}.png"
    
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 用户头像的 Base64 数据"""
        import aiohttp
        import base64
        
        url = await self.get_user_avatar_url(user_id, size)
        if not url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        content_type = resp.headers.get('Content-Type', 'image/png')
                        return f"data:{content_type};base64,{b64}"
        except Exception:
            pass
        return None
    
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 服务器/频道图标 URL"""
        # Discord 的 Guild Icon URL 格式
        # 需要有 icon_hash 信息
        guild_info = self.user_cache.get(f"guild_{group_id}", {})
        icon_hash = guild_info.get("icon")
        
        if icon_hash:
            actual_size = self._get_valid_size(size)
            is_animated = icon_hash.startswith("a_")
            ext = "gif" if is_animated else "png"
            return f"{self.CDN_BASE}/icons/{group_id}/{icon_hash}.{ext}?size={actual_size}"
        return None
    
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 Discord 用户头像 URL（无需 API 调用）"""
        return {
            user_id: await self.get_user_avatar_url(user_id, size)
            for user_id in user_ids
        }
```

#### 3.2.4 Slack 头像获取

Slack 需要从用户信息 API 获取头像：

```python
# src/infrastructure/platform/adapters/slack_avatar.py

class SlackAvatarRepository(IAvatarRepository):
    """Slack 头像仓储实现"""
    
    # Slack 提供的头像尺寸
    SIZE_FIELDS = {
        24: "image_24",
        32: "image_32",
        48: "image_48",
        72: "image_72",
        192: "image_192",
        512: "image_512",
        1024: "image_1024",
    }
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_base = "https://slack.com/api"
    
    def _get_size_field(self, requested_size: int) -> str:
        """获取最接近请求尺寸的字段名"""
        sizes = sorted(self.SIZE_FIELDS.keys())
        for size in sizes:
            if size >= requested_size:
                return self.SIZE_FIELDS[size]
        return "image_512"  # 默认
    
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Slack 用户头像 URL"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base}/users.info"
                headers = {"Authorization": f"Bearer {self.bot_token}"}
                
                async with session.get(url, headers=headers, params={"user": user_id}) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                
                if not data.get("ok"):
                    return None
                
                profile = data.get("user", {}).get("profile", {})
                
                # 尝试获取请求尺寸的头像
                size_field = self._get_size_field(size)
                avatar_url = profile.get(size_field)
                
                # 如果没有，尝试获取其他尺寸
                if not avatar_url:
                    for field in ["image_512", "image_192", "image_72", "image_48"]:
                        avatar_url = profile.get(field)
                        if avatar_url:
                            break
                
                return avatar_url
                
        except Exception:
            return None
    
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Slack 用户头像的 Base64 数据"""
        import aiohttp
        import base64
        
        url = await self.get_user_avatar_url(user_id, size)
        if not url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        content_type = resp.headers.get('Content-Type', 'image/png')
                        return f"data:{content_type};base64,{b64}"
        except Exception:
            pass
        return None
    
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """Slack 频道没有头像概念，返回 None"""
        return None
    
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 Slack 用户头像 URL"""
        import asyncio
        
        async def get_avatar(user_id: str):
            return user_id, await self.get_user_avatar_url(user_id, size)
        
        # Slack API 有速率限制，需要控制并发
        results = {}
        for user_id in user_ids:
            results[user_id] = await self.get_user_avatar_url(user_id, size)
            await asyncio.sleep(0.1)  # 避免触发速率限制
        
        return results
```

### 3.3 平台异常定义

```python
# src/domain/exceptions.py

class PlatformError(Exception):
    """平台相关错误基类"""
    def __init__(self, message: str, platform: str = "unknown"):
        self.platform = platform
        super().__init__(f"[{platform}] {message}")


class PlatformNotSupportedError(PlatformError):
    """平台不支持此功能"""
    pass


class PlatformAPIError(PlatformError):
    """平台 API 调用失败"""
    def __init__(self, message: str, platform: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message, platform)


class PlatformAuthError(PlatformError):
    """平台认证失败"""
    pass


class PlatformRateLimitError(PlatformError):
    """平台请求频率限制"""
    def __init__(self, message: str, platform: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message, platform)


class BotNotInGroupError(PlatformError):
    """Bot 不在目标群组中"""
    def __init__(self, group_id: str, platform: str):
        self.group_id = group_id
        super().__init__(f"Bot not in group {group_id}", platform)
```

---

## 4. 适配器实现示例

### 4.1 适配器基类

```python
# src/infrastructure/platform/base.py
from abc import ABC
from typing import Any, Optional

from ...domain.repositories.message_repository import (
    IMessageRepository,
    IMessageSender,
    IGroupInfoRepository,
)
from ...domain.value_objects.platform_capabilities import PlatformCapabilities


class PlatformAdapter(ABC):
    """
    平台适配器基类
    
    组合了消息仓储、消息发送、群组信息三个接口。
    每个平台适配器继承此类并实现所有方法。
    """
    
    def __init__(self, bot_instance: Any, config: dict = None):
        self.bot = bot_instance
        self.config = config or {}
        self._capabilities: Optional[PlatformCapabilities] = None
    
    @property
    def capabilities(self) -> PlatformCapabilities:
        """平台能力（延迟初始化）"""
        if self._capabilities is None:
            self._capabilities = self._init_capabilities()
        return self._capabilities
    
    def _init_capabilities(self) -> PlatformCapabilities:
        """初始化平台能力，子类必须实现"""
        raise NotImplementedError
    
    # 以下方法由子类实现，对应三个接口
    # IMessageRepository
    async def fetch_messages(self, group_id: str, days: int, max_count: int): ...
    
    # IMessageSender  
    async def send_text(self, group_id: str, text: str, reply_to: str = None): ...
    async def send_image(self, group_id: str, image_path: str, caption: str = ""): ...
    async def send_file(self, group_id: str, file_path: str, filename: str = None): ...
    
    # IGroupInfoRepository
    async def get_group_info(self, group_id: str): ...
    async def get_group_list(self) -> list[str]: ...
    async def get_member_list(self, group_id: str): ...
```

### 4.2 OneBot 适配器完整实现

```python
# src/infrastructure/platform/adapters/onebot_adapter.py
from datetime import datetime, timedelta
from typing import List, Optional, Any
import asyncio

from astrbot.api import logger

from ....domain.value_objects.unified_message import (
    UnifiedMessage,
    MessageContent,
    MessageContentType,
)
from ....domain.value_objects.platform_capabilities import (
    PlatformCapabilities,
    ONEBOT_V11_CAPABILITIES,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.exceptions import (
    PlatformAPIError,
    BotNotInGroupError,
    PlatformNotSupportedError,
)
from ..base import PlatformAdapter


class OneBotAdapter(PlatformAdapter):
    """
    OneBot v11 协议适配器
    
    支持 NapCat、go-cqhttp、Lagrange 等 OneBot 实现
    """
    
    def __init__(self, bot_instance: Any, config: dict = None):
        super().__init__(bot_instance, config)
        self.bot_self_ids = [str(id) for id in config.get("bot_qq_ids", [])] if config else []
    
    def _init_capabilities(self) -> PlatformCapabilities:
        return ONEBOT_V11_CAPABILITIES
    
    # ==================== IMessageRepository ====================
    
    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """获取群组历史消息"""
        
        if not hasattr(self.bot, "call_action"):
            raise PlatformNotSupportedError(
                "Bot instance does not support call_action",
                "onebot"
            )
        
        try:
            # 调用 OneBot API
            result = await self.bot.call_action(
                "get_group_msg_history",
                group_id=int(group_id),
                count=max_count,
            )
            
            if not result or "messages" not in result:
                logger.warning(f"No messages returned for group {group_id}")
                return []
            
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            messages = []
            for raw_msg in result.get("messages", []):
                # 时间过滤
                msg_time = datetime.fromtimestamp(raw_msg.get("time", 0))
                if not (start_time <= msg_time <= end_time):
                    continue
                
                # 过滤 Bot 自己的消息
                sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                if sender_id in self.bot_self_ids:
                    continue
                
                # 转换消息
                unified = self._convert_message(raw_msg, group_id)
                if unified:
                    messages.append(unified)
            
            # 按时间升序排列
            messages.sort(key=lambda m: m.timestamp)
            
            logger.info(f"Fetched {len(messages)} messages from group {group_id}")
            return messages
            
        except Exception as e:
            error_str = str(e)
            if "retcode=1200" in error_str or "1200" in error_str:
                raise BotNotInGroupError(group_id, "onebot")
            raise PlatformAPIError(f"Failed to fetch messages: {e}", "onebot")
    
    def _convert_message(self, raw_msg: dict, group_id: str) -> Optional[UnifiedMessage]:
        """将 OneBot 消息转换为统一格式"""
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])
            
            # 如果 message 是字符串，转换为列表
            if isinstance(message_chain, str):
                message_chain = [{"type": "text", "data": {"text": message_chain}}]
            
            contents = []
            text_parts = []
            
            for seg in message_chain:
                seg_type = seg.get("type", "")
                seg_data = seg.get("data", {})
                
                if seg_type == "text":
                    text = seg_data.get("text", "")
                    text_parts.append(text)
                    contents.append(MessageContent(
                        type=MessageContentType.TEXT,
                        text=text
                    ))
                    
                elif seg_type == "image":
                    contents.append(MessageContent(
                        type=MessageContentType.IMAGE,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))
                    
                elif seg_type == "at":
                    at_qq = seg_data.get("qq", "")
                    contents.append(MessageContent(
                        type=MessageContentType.AT,
                        at_user_id=str(at_qq)
                    ))
                    
                elif seg_type in ("face", "mface", "bface", "sface"):
                    contents.append(MessageContent(
                        type=MessageContentType.EMOJI,
                        emoji_id=str(seg_data.get("id", "")),
                        raw_data={"face_type": seg_type}
                    ))
                    
                elif seg_type == "reply":
                    contents.append(MessageContent(
                        type=MessageContentType.REPLY,
                        raw_data={"reply_id": seg_data.get("id", "")}
                    ))
                    
                elif seg_type == "forward":
                    contents.append(MessageContent(
                        type=MessageContentType.FORWARD,
                        raw_data=seg_data
                    ))
                    
                elif seg_type == "record":
                    contents.append(MessageContent(
                        type=MessageContentType.VOICE,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))
                    
                elif seg_type == "video":
                    contents.append(MessageContent(
                        type=MessageContentType.VIDEO,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))
                    
                else:
                    contents.append(MessageContent(
                        type=MessageContentType.UNKNOWN,
                        raw_data=seg
                    ))
            
            # 提取回复 ID
            reply_to = None
            for c in contents:
                if c.type == MessageContentType.REPLY and c.raw_data:
                    reply_to = str(c.raw_data.get("reply_id", ""))
                    break
            
            return UnifiedMessage(
                message_id=str(raw_msg.get("message_id", "")),
                sender_id=str(sender.get("user_id", "")),
                sender_name=sender.get("nickname", ""),
                sender_card=sender.get("card", "") or None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=raw_msg.get("time", 0),
                platform="onebot",
                reply_to_id=reply_to,
            )
            
        except Exception as e:
            logger.warning(f"Failed to convert OneBot message: {e}")
            return None
    
    def get_capabilities(self) -> PlatformCapabilities:
        return self.capabilities
    
    def get_platform_name(self) -> str:
        return "onebot"
    
    # ==================== IMessageSender ====================
    
    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """发送文本消息"""
        try:
            message = [{"type": "text", "data": {"text": text}}]
            
            if reply_to:
                message.insert(0, {"type": "reply", "data": {"id": reply_to}})
            
            await self.bot.call_action(
                "send_group_msg",
                group_id=int(group_id),
                message=message,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            return False
    
    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片消息"""
        try:
            message = []
            
            if caption:
                message.append({"type": "text", "data": {"text": caption}})
            
            # 支持本地路径和 URL
            if image_path.startswith(("http://", "https://")):
                file_str = image_path
            else:
                file_str = f"file:///{image_path}"
            
            message.append({"type": "image", "data": {"file": file_str}})
            
            await self.bot.call_action(
                "send_group_msg",
                group_id=int(group_id),
                message=message,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send image: {e}")
            return False
    
    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """发送文件"""
        try:
            await self.bot.call_action(
                "upload_group_file",
                group_id=int(group_id),
                file=file_path,
                name=filename or file_path.split("/")[-1],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            return False
    
    # ==================== IGroupInfoRepository ====================
    
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取群组信息"""
        try:
            result = await self.bot.call_action(
                "get_group_info",
                group_id=int(group_id),
            )
            
            if not result:
                return None
            
            return UnifiedGroup(
                group_id=str(result.get("group_id", group_id)),
                group_name=result.get("group_name", ""),
                member_count=result.get("member_count", 0),
                owner_id=str(result.get("owner_id", "")) or None,
                create_time=result.get("group_create_time"),
                platform="onebot",
            )
        except Exception as e:
            logger.error(f"Failed to get group info: {e}")
            return None
    
    async def get_group_list(self) -> List[str]:
        """获取 Bot 所在的所有群组 ID"""
        try:
            result = await self.bot.call_action("get_group_list")
            return [str(g.get("group_id", "")) for g in result or []]
        except Exception as e:
            logger.error(f"Failed to get group list: {e}")
            return []
    
    async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
        """获取群组成员列表"""
        try:
            result = await self.bot.call_action(
                "get_group_member_list",
                group_id=int(group_id),
            )
            
            members = []
            for m in result or []:
                members.append(UnifiedMember(
                    user_id=str(m.get("user_id", "")),
                    nickname=m.get("nickname", ""),
                    card=m.get("card", "") or None,
                    role=m.get("role", "member"),
                    join_time=m.get("join_time"),
                ))
            return members
        except Exception as e:
            logger.error(f"Failed to get member list: {e}")
            return []
    
    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[UnifiedMember]:
        """获取指定成员信息"""
        try:
            result = await self.bot.call_action(
                "get_group_member_info",
                group_id=int(group_id),
                user_id=int(user_id),
            )
            
            if not result:
                return None
            
            return UnifiedMember(
                user_id=str(result.get("user_id", user_id)),
                nickname=result.get("nickname", ""),
                card=result.get("card", "") or None,
                role=result.get("role", "member"),
                join_time=result.get("join_time"),
            )
        except Exception as e:
            logger.error(f"Failed to get member info: {e}")
            return None
```

### 4.3 适配器工厂

```python
# src/infrastructure/platform/factory.py
from typing import Optional, Any, Dict, Type
from astrbot.api import logger

from .base import PlatformAdapter
from .adapters.onebot_adapter import OneBotAdapter
# from .adapters.telegram_adapter import TelegramAdapter  # 待实现
# from .adapters.discord_adapter import DiscordAdapter    # 待实现


class PlatformAdapterFactory:
    """
    平台适配器工厂
    
    根据平台名称创建对应的适配器实例。
    使用注册表模式，便于扩展新平台。
    """
    
    # 适配器注册表
    _adapters: Dict[str, Type[PlatformAdapter]] = {
        "aiocqhttp": OneBotAdapter,
        "onebot": OneBotAdapter,
        # "telegram": TelegramAdapter,
        # "discord": DiscordAdapter,
    }
    
    @classmethod
    def register(cls, platform_name: str, adapter_class: Type[PlatformAdapter]):
        """注册新的适配器"""
        cls._adapters[platform_name.lower()] = adapter_class
        logger.info(f"Registered platform adapter: {platform_name}")
    
    @classmethod
    def create(
        cls,
        platform_name: str,
        bot_instance: Any,
        config: dict = None,
    ) -> Optional[PlatformAdapter]:
        """
        创建平台适配器
        
        Args:
            platform_name: 平台名称（如 "aiocqhttp", "telegram"）
            bot_instance: AstrBot 传入的 bot 实例
            config: 配置字典
            
        Returns:
            平台适配器实例，如果平台不支持则返回 None
        """
        adapter_class = cls._adapters.get(platform_name.lower())
        
        if adapter_class is None:
            logger.warning(f"Unsupported platform: {platform_name}")
            return None
        
        try:
            adapter = adapter_class(bot_instance, config)
            logger.info(f"Created {platform_name} adapter with capabilities: {adapter.capabilities}")
            return adapter
        except Exception as e:
            logger.error(f"Failed to create {platform_name} adapter: {e}")
            return None
    
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """获取所有支持的平台名称"""
        return list(cls._adapters.keys())
    
    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """检查平台是否支持"""
        return platform_name.lower() in cls._adapters
    
    @classmethod
    def get_analyzable_platforms(cls) -> list[str]:
        """获取支持分析功能的平台"""
        result = []
        for name, adapter_class in cls._adapters.items():
            try:
                # 创建临时实例检查能力
                temp = adapter_class.__new__(adapter_class)
                temp._capabilities = None
                caps = temp._init_capabilities()
                if caps.can_analyze():
                    result.append(name)
            except Exception:
                pass
        return result
```

---

## 5. 更新后的目录结构

```
astrbot_plugin_group_daily_analysis/
├── main.py                                    # Interface Layer (入口)
├── metadata.yaml
├── requirements.txt
│
├── src/
│   ├── __init__.py
│   │
│   ├── application/                           # Application Layer
│   │   ├── __init__.py
│   │   ├── analysis_orchestrator.py           # 分析流程编排
│   │   ├── scheduling_service.py              # 定时任务服务
│   │   └── reporting_service.py               # 报告服务
│   │
│   ├── domain/                                # Domain Layer (平台无关)
│   │   ├── __init__.py
│   │   │
│   │   ├── entities/                          # 实体
│   │   │   ├── __init__.py
│   │   │   ├── analysis_task.py               # 分析任务聚合根
│   │   │   └── analysis_result.py             # 分析结果实体
│   │   │
│   │   ├── value_objects/                     # 值对象
│   │   │   ├── __init__.py
│   │   │   ├── unified_message.py             # ★ 统一消息格式
│   │   │   ├── platform_capabilities.py       # ★ 平台能力描述
│   │   │   ├── unified_group.py               # ★ 统一群组信息
│   │   │   ├── topic.py                       # 话题
│   │   │   ├── user_title.py                  # 用户称号
│   │   │   ├── golden_quote.py                # 金句
│   │   │   └── statistics.py                  # 统计数据
│   │   │
│   │   ├── services/                          # 领域服务
│   │   │   ├── __init__.py
│   │   │   ├── topic_analyzer.py              # 话题分析
│   │   │   ├── user_title_analyzer.py         # 用户称号分析
│   │   │   ├── golden_quote_analyzer.py       # 金句分析
│   │   │   ├── statistics_calculator.py       # 统计计算
│   │   │   └── report_generator.py            # 报告生成
│   │   │
│   │   ├── repositories/                      # ★ 仓储接口
│   │   │   ├── __init__.py
│   │   │   ├── message_repository.py          # IMessageRepository
│   │   │   ├── message_sender.py              # IMessageSender
│   │   │   └── group_info_repository.py       # IGroupInfoRepository
│   │   │
│   │   └── exceptions.py                      # 领域异常
│   │
│   ├── infrastructure/                        # Infrastructure Layer
│   │   ├── __init__.py
│   │   │
│   │   ├── platform/                          # ★ 平台适配层
│   │   │   ├── __init__.py
│   │   │   ├── base.py                        # 适配器基类
│   │   │   ├── factory.py                     # 适配器工厂
│   │   │   │
│   │   │   └── adapters/                      # 具体适配器
│   │   │       ├── __init__.py
│   │   │       ├── onebot_adapter.py          # ★ OneBot (QQ)
│   │   │       ├── telegram_adapter.py        # Telegram (待实现)
│   │   │       ├── discord_adapter.py         # Discord (待实现)
│   │   │       ├── slack_adapter.py           # Slack (待实现)
│   │   │       └── lark_adapter.py            # 飞书 (待实现)
│   │   │
│   │   ├── persistence/                       # 持久化
│   │   │   ├── __init__.py
│   │   │   └── history_repository.py          # 历史记录存储
│   │   │
│   │   ├── llm/                               # LLM 客户端
│   │   │   ├── __init__.py
│   │   │   └── llm_client.py
│   │   │
│   │   ├── config/                            # 配置
│   │   │   ├── __init__.py
│   │   │   └── config_manager.py
│   │   │
│   │   └── resilience/                        # 弹性组件
│   │       ├── __init__.py
│   │       ├── circuit_breaker.py
│   │       ├── rate_limiter.py
│   │       └── retry.py
│   │
│   └── shared/                                # 共享组件
│       ├── __init__.py
│       ├── constants.py
│       └── trace_context.py
│
├── tests/                                     # 测试
│   ├── __init__.py
│   ├── unit/
│   │   ├── domain/
│   │   │   └── test_unified_message.py
│   │   └── infrastructure/
│   │       └── test_onebot_adapter.py
│   └── integration/
│
└── docs/                                      # 文档
    ├── 09_ddd_cross_platform_complete_guide.md
    └── 10_platform_abstraction_layer.md       # 本文档
```

---

## 6. 重构路线图（更新版）

### 6.1 总览

| Phase | 内容 | 工作量 | 状态 |
|-------|------|--------|------|
| **Phase 0** | 准备：目录结构、接口定义 | 1 天 | 📋 待开始 |
| **Phase 1** | 平台适配器：OneBot 实现 | 2-3 天 | 📋 待开始 |
| **Phase 2** | 领域层：值对象、实体、服务 | 2-3 天 | 📋 待开始 |
| **Phase 3** | 应用层：编排器、服务 | 2-3 天 | 📋 待开始 |
| **Phase 4** | 接口层：main.py 重构 | 1-2 天 | 📋 待开始 |
| **Phase 5** | 新平台：Telegram、Discord | 每平台 1 天 | 📋 待开始 |
| **Phase 6** | 测试与文档 | 2 天 | 📋 待开始 |
| **总计** | | **12-16 天** | |

### 6.2 Phase 0 详细任务

```bash
# 创建目录结构
mkdir -p src/{application,domain/{entities,value_objects,services,repositories},infrastructure/{platform/adapters,persistence,llm,config,resilience},shared}
touch src/__init__.py
touch src/{application,domain,infrastructure,shared}/__init__.py
touch src/domain/{entities,value_objects,services,repositories}/__init__.py
touch src/infrastructure/{platform,persistence,llm,config,resilience}/__init__.py
touch src/infrastructure/platform/adapters/__init__.py
```

**检查清单**:
- [ ] 创建完整目录结构
- [ ] 定义 `UnifiedMessage` 值对象
- [ ] 定义 `PlatformCapabilities` 值对象
- [ ] 定义 `UnifiedGroup` 和 `UnifiedMember` 值对象
- [ ] 定义 `IMessageRepository` 接口
- [ ] 定义 `IMessageSender` 接口
- [ ] 定义 `IGroupInfoRepository` 接口
- [ ] 定义平台异常类
- [ ] 创建适配器基类 `PlatformAdapter`
- [ ] 创建适配器工厂 `PlatformAdapterFactory`

### 6.3 Phase 1 详细任务

**检查清单**:
- [ ] 实现 `OneBotAdapter._convert_message()` 消息转换
- [ ] 实现 `OneBotAdapter.fetch_messages()` 消息获取
- [ ] 实现 `OneBotAdapter.send_text/image/file()` 消息发送
- [ ] 实现 `OneBotAdapter.get_group_info/list()` 群组信息
- [ ] 注册到 `PlatformAdapterFactory`
- [ ] 编写单元测试

### 6.4 Phase 5 详细任务（跨平台阶段）

#### Telegram 适配器
- [ ] 研究 python-telegram-bot 或 Telethon API
- [ ] 实现 `TelegramAdapter` 基础结构
- [ ] 实现消息格式转换
- [ ] 处理 Telegram 特有的消息类型（贴纸、动图等）
- [ ] 测试并验证

#### Discord 适配器
- [ ] 研究 pycord 或 discord.py API
- [ ] 实现 `DiscordAdapter` 基础结构
- [ ] 实现消息格式转换
- [ ] 处理 Discord 特有功能（embed、reaction 等）
- [ ] 测试并验证

---

## 7. 平台能力对比表

| 功能 | OneBot | Telegram Bot | Telegram User | Discord | Slack | 飞书 | 钉钉 |
|------|--------|--------------|---------------|---------|-------|------|------|
| **消息历史** | ✅ 7天 | ❌ | ✅ 365天 | ✅ 30天 | ✅ 90天 | ✅ 30天 | ❌ |
| **群列表** | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **成员列表** | ✅ | ✅* | ✅ | ✅ | ✅ | ✅ | ❌ |
| **发送图片** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **发送文件** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **可分析** | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **用户头像** | ✅ URL模板 | ✅ API调用 | ✅ API调用 | ✅ CDN模板 | ✅ API调用 | ✅ API调用 | ❌ |
| **群组头像** | ✅ URL模板 | ✅ API调用 | ✅ API调用 | ✅ CDN模板 | ❌ | ✅ API调用 | ❌ |
| **头像尺寸** | 40-640 | 160-640 | 160-640 | 16-4096 | 24-1024 | 72-640 | - |

> *: 需要管理员权限

### 7.1 头像获取方式对比

| 平台 | 获取方式 | URL 模板 | 需要 API 调用 | 备注 |
|------|----------|----------|--------------|------|
| **QQ/OneBot** | URL 模板 | `q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}` | ❌ | 直接构造，无需认证 |
| **Telegram** | API 调用 | - | ✅ | 需要 getUserProfilePhotos + getFile |
| **Discord** | CDN 模板 | `cdn.discordapp.com/avatars/{user_id}/{hash}.png` | ❌ | 需要缓存 avatar_hash |
| **Slack** | API 调用 | - | ✅ | users.info API，profile.image_* |
| **飞书** | API 调用 | - | ✅ | 用户信息 API，avatar 字段 |
| **钉钉** | 不支持 | - | - | 机器人 API 无头像能力 |

---

## 8. 总结

本文档详细定义了：

1. **平台限界上下文** - 作为反腐败层隔离外部平台差异
2. **核心值对象** - `UnifiedMessage`, `PlatformCapabilities`, `UnifiedGroup`, `UnifiedMember`
3. **仓储接口** - `IMessageRepository`, `IMessageSender`, `IGroupInfoRepository`, `IAvatarRepository`
4. **头像获取抽象** - 各平台头像获取的统一接口和具体实现
5. **OneBot 适配器完整实现** - 可直接使用的代码
6. **目录结构** - 清晰的分层架构
7. **重构路线图** - 详细的任务清单

按照此设计实施，可以实现：
- 从 QQ 专属扩展到多平台支持
- 新增平台只需实现适配器
- 领域逻辑完全平台无关
- 可测试性大幅提升
- **模板可以使用统一的头像接口，无需关心平台差异**
