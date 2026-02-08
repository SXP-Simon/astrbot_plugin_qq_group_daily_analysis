# 08. 跨平台解耦调研报告 (Cross-Platform Decoupling Analysis)

> **调研日期**: 2026-02-08
> **调研范围**: AstrBot 平台抽象层 + 插件 QQ 硬编码分析
> **调研目的**: 分析如何将插件从 QQ 专属改造为跨平台通用插件

---

## 1. 执行摘要

### 1.1 当前问题

本插件 (`astrbot_plugin_qq_group_daily_analysis`) 当前存在严重的平台耦合问题：

| 问题类型 | 数量 | 影响 |
|----------|------|------|
| **直接导入 aiocqhttp** | 1 处 | 插件无法在非 QQ 平台加载 |
| **AiocqhttpMessageEvent 类型检查** | 12+ 处 | 所有命令仅限 QQ 平台 |
| **OneBot API 调用 (call_action)** | 8+ 处 | 消息获取/发送依赖 OneBot |
| **QQ 特定数据结构** | 15+ 处 | 消息格式、表情类型等 |
| **QQ 号相关逻辑** | 10+ 处 | bot_qq_id、self_id 等 |

### 1.2 核心发现

**AstrBot 已提供完善的跨平台抽象层**，支持 12+ 个平台：

| 平台 | 适配器 | 消息历史支持 |
|------|--------|--------------|
| QQ (OneBot v11) | `aiocqhttp` | ✅ `get_group_msg_history` |
| QQ 官方 | `qqofficial` | ❌ 不支持 |
| Telegram | `telegram` | ✅ 可通过 API 获取 |
| Discord | `discord` | ✅ 可通过 API 获取 |
| Slack | `slack` | ✅ 可通过 API 获取 |
| 飞书 | `lark` | ✅ 可通过 API 获取 |
| 钉钉 | `dingtalk` | ⚠️ 有限支持 |
| 企业微信 | `wecom` | ⚠️ 有限支持 |
| Misskey | `misskey` | ✅ 可通过 API 获取 |
| Satori | `satori` | 取决于实现 |
| 微信公众号 | `weixin_offacc` | ❌ 不支持 |
| WebChat | `webchat` | ❌ 不支持 |

### 1.3 解耦可行性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| **技术可行性** | ✅ 高 | AstrBot 已有完善的平台抽象 |
| **工作量** | 中等 | 约 3-5 天工作量 |
| **风险** | 低 | 渐进式重构，可保持兼容 |
| **收益** | 高 | 支持 5+ 主流平台 |

---

## 2. AstrBot 平台抽象层分析

### 2.1 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AstrBot Core                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Platform Abstraction                    │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │   Platform   │  │ AstrMessage  │  │  MessageType │   │   │
│  │  │  (Abstract)  │  │    Event     │  │    (Enum)    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ AstrBotMsg   │  │    Group     │  │MessageMember │   │   │
│  │  │   (Model)    │  │   (Model)    │  │   (Model)    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Platform Adapters                       │   │
│  │                                                          │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │aiocqhttp│ │telegram│ │discord │ │ slack  │ │  lark  │ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │dingtalk│ │ wecom  │ │misskey │ │ satori │ │ webchat│ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心抽象类

#### 2.2.1 Platform (平台基类)

**文件**: `astrbot/core/platform/platform.py`

```python
class Platform(abc.ABC):
    """平台适配器基类"""
    
    def __init__(self, config: dict, event_queue: Queue):
        self.config = config
        self._event_queue = event_queue
        self.client_self_id = uuid.uuid4().hex
    
    @abc.abstractmethod
    def run(self) -> Coroutine[Any, Any, None]:
        """启动平台"""
        raise NotImplementedError
    
    @abc.abstractmethod
    def meta(self) -> PlatformMetadata:
        """获取平台元数据"""
        raise NotImplementedError
    
    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        """通过会话发送消息（跨平台统一接口）"""
        pass
    
    def commit_event(self, event: AstrMessageEvent):
        """提交事件到事件队列"""
        self._event_queue.put_nowait(event)
    
    def get_client(self):
        """获取平台客户端对象"""
        pass
```

#### 2.2.2 AstrMessageEvent (消息事件基类)

**文件**: `astrbot/core/platform/astr_message_event.py`

```python
class AstrMessageEvent(abc.ABC):
    """统一消息事件基类 - 所有平台事件的父类"""
    
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
    ):
        self.message_str = message_str          # 纯文本消息
        self.message_obj = message_obj          # 完整消息对象
        self.platform_meta = platform_meta      # 平台元数据
        self.session = MessageSession(...)      # 会话信息
    
    # 统一的跨平台方法
    def get_platform_name(self) -> str:         # 获取平台类型
    def get_platform_id(self) -> str:           # 获取平台实例ID
    def get_message_str(self) -> str:           # 获取消息文本
    def get_message_type(self) -> MessageType:  # 获取消息类型
    def get_group_id(self) -> str:              # 获取群组ID
    def get_self_id(self) -> str:               # 获取机器人ID
    def get_sender_id(self) -> str:             # 获取发送者ID
    def get_sender_name(self) -> str:           # 获取发送者名称
    
    # 统一的发送方法
    async def send(self, message: MessageChain):
        """发送消息（由子类实现具体逻辑）"""
        pass
    
    async def get_group(self, group_id: str = None) -> Group | None:
        """获取群组信息（由支持的平台实现）"""
        pass
```

#### 2.2.3 AstrBotMessage (统一消息模型)

**文件**: `astrbot/core/platform/astrbot_message.py`

```python
class AstrBotMessage:
    """AstrBot 统一消息对象"""
    
    type: MessageType           # 消息类型 (GROUP_MESSAGE, FRIEND_MESSAGE, OTHER)
    self_id: str                # 机器人ID
    session_id: str             # 会话ID
    message_id: str             # 消息ID
    group: Group | None         # 群组信息
    sender: MessageMember       # 发送者信息
    message: list[BaseMessageComponent]  # 消息链
    message_str: str            # 纯文本消息
    raw_message: object         # 原始消息对象
    timestamp: int              # 时间戳

class MessageMember:
    user_id: str                # 用户ID (平台无关)
    nickname: str | None        # 昵称

class Group:
    group_id: str               # 群组ID (平台无关)
    group_name: str | None      # 群名称
    group_owner: str | None     # 群主ID
    group_admins: list[str]     # 管理员ID列表
    members: list[MessageMember] # 群成员列表
```

#### 2.2.4 MessageType (消息类型枚举)

**文件**: `astrbot/core/platform/message_type.py`

```python
class MessageType(Enum):
    GROUP_MESSAGE = "GroupMessage"    # 群组消息
    FRIEND_MESSAGE = "FriendMessage"  # 私聊消息
    OTHER_MESSAGE = "OtherMessage"    # 其他消息
```

### 2.3 各平台适配器对比

| 平台 | 事件类 | 消息获取方法 | 消息发送方法 | 群信息获取 |
|------|--------|--------------|--------------|------------|
| aiocqhttp | `AiocqhttpMessageEvent` | `call_action("get_group_msg_history")` | `send_group_msg` | `get_group_info` |
| telegram | `TelegramPlatformEvent` | `get_chat_history()` | `send_message()` | `get_chat()` |
| discord | `DiscordPlatformEvent` | `channel.history()` | `channel.send()` | `get_channel()` |
| slack | `SlackMessageEvent` | `conversations_history()` | `chat_postMessage()` | `conversations_info()` |
| lark | `LarkMessageEvent` | 飞书 API | 飞书 API | 飞书 API |

### 2.4 平台检测与适配模式

**正确的跨平台写法**:

```python
# ✅ 推荐：使用基类 AstrMessageEvent
from astrbot.api.event import AstrMessageEvent

@filter.command("分析")
async def analyze(self, event: AstrMessageEvent):
    # 使用统一接口
    group_id = event.get_group_id()
    platform = event.get_platform_name()
    
    # 根据平台选择策略
    if platform == "aiocqhttp":
        messages = await self._fetch_qq_messages(event)
    elif platform == "telegram":
        messages = await self._fetch_telegram_messages(event)
    elif platform == "discord":
        messages = await self._fetch_discord_messages(event)
    else:
        yield event.plain_result(f"❌ 平台 {platform} 暂不支持消息历史获取")
        return
```

---

## 3. 插件 QQ 硬编码清单

### 3.1 硬编码分类汇总

| 类别 | 文件 | 行数 | 严重程度 | 解耦难度 |
|------|------|------|----------|----------|
| 直接导入 aiocqhttp | `main.py` | 14-16 | 🔴 高 | 低 |
| 类型检查 AiocqhttpMessageEvent | `main.py` | 多处 | 🔴 高 | 低 |
| OneBot API 调用 | `message_handler.py` | 90-110 | 🔴 高 | 中 |
| OneBot API 调用 | `auto_scheduler.py` | 85-90 | 🔴 高 | 中 |
| QQ 表情类型处理 | `message_handler.py` | 206-256 | 🟡 中 | 中 |
| QQ 号相关逻辑 | `bot_manager.py` | 多处 | 🟡 中 | 低 |
| 消息格式假设 | `message_handler.py` | 133-147 | 🟡 中 | 中 |
| 错误码检查 | 多文件 | 多处 | 🟢 低 | 低 |

### 3.2 详细硬编码清单

#### 3.2.1 main.py - 入口文件

```python
# 🔴 硬编码 1: 直接导入 aiocqhttp 事件类
# 行 14-16
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

# 🔴 硬编码 2-13: 所有命令都限制 QQ 平台
# 行 122, 128-129
async def analyze_group_daily(self, event: AiocqhttpMessageEvent, ...):
    if not isinstance(event, AiocqhttpMessageEvent):
        yield event.plain_result("❌ 此功能仅支持QQ群聊")
        return

# 同样的模式在以下命令中重复:
# - set_output_format (行 330, 336-338)
# - set_report_template (行 377, 383-385)
# - view_templates (行 447, 452-454)
# - install_pdf_deps (行 533, 538-540)
# - analysis_settings (行 556, 567-569)

# 🔴 硬编码 14: 直接调用 OneBot API 发送消息
# 行 218-225
if hasattr(bot_instance, "api") and hasattr(bot_instance.api, "call_action"):
    await bot_instance.api.call_action(
        "send_group_msg",
        group_id=int(group_id),
        message=message_chain,
    )
```

#### 3.2.2 message_handler.py - 消息处理

```python
# 🔴 硬编码 15: QQ 号提取逻辑
# 行 40-48
def _extract_bot_qq_id_from_instance(self, bot_instance):
    """从bot实例中提取QQ号（单个）"""
    if hasattr(bot_instance, "self_id") and bot_instance.self_id:
        return str(bot_instance.self_id)
    elif hasattr(bot_instance, "qq") and bot_instance.qq:
        return str(bot_instance.qq)
    ...

# 🔴 硬编码 16: OneBot API 调用获取消息历史
# 行 90-111
if hasattr(bot_instance, "call_action"):
    result = await bot_instance.call_action(
        "get_group_msg_history", **payloads
    )
elif hasattr(bot_instance, "api"):
    # QQ 官方 bot (botClient) 不支持历史消息
    logger.error("检测到 QQ 官方 Bot，官方 API 不支持获取历史消息")
    return []

# 🟡 硬编码 17: QQ 消息格式假设
# 行 124-147
round_messages = result.get("messages", [])
for msg in round_messages:
    msg_time = datetime.fromtimestamp(msg.get("time", 0))
    sender_id = str(msg.get("sender", {}).get("user_id", ""))

# 🟡 硬编码 18-22: QQ 特定表情类型处理
# 行 206-256
elif content.get("type") == "face":      # QQ基础表情
    emoji_statistics.face_count += 1
elif content.get("type") == "mface":     # 动画表情/魔法表情
    emoji_statistics.mface_count += 1
elif content.get("type") == "bface":     # 超级表情
    emoji_statistics.bface_count += 1
elif content.get("type") == "sface":     # 小表情
    emoji_statistics.sface_count += 1
```

#### 3.2.3 auto_scheduler.py - 自动调度

```python
# 🔴 硬编码 23: OneBot API 调用获取群信息
# 行 85-92
if hasattr(bot_instance, "call_action"):
    result = await bot_instance.call_action(
        "get_group_info", group_id=int(group_id)
    )

# 🟡 硬编码 24: OneBot 错误码检查
# 行 100-107
if "retcode=1200" in error_msg or "消息undefined不存在" in error_msg:
    logger.warning(f"群 {group_id} 机器人不在此群中")

# 🔴 硬编码 25: OneBot API 获取群列表
# 行 478-479
result = await call_action_func("get_group_list")
```

#### 3.2.4 bot_manager.py - Bot 管理

```python
# 🟡 硬编码 26-28: QQ 号相关属性和方法
# 行 18, 39-47, 80-82
self._bot_qq_ids = []  # 命名暗示 QQ 专属

def set_bot_qq_ids(self, bot_qq_ids):
    """设置bot QQ号（支持单个QQ号或QQ号列表）"""

def has_bot_qq_id(self) -> bool:
    """检查是否有配置的bot QQ号"""

# 🟡 硬编码 29: 平台检查硬编码
# 行 151-154
if hasattr(event, "get_platform_name") and event.get_platform_name() != "aiocqhttp":
    return False
```

#### 3.2.5 message_sender.py - 消息发送

```python
# 🔴 硬编码 30-32: OneBot API 调用发送消息
# 行 38-40, 73-75, 117-119
await bot.api.call_action("send_group_msg", group_id=group_id, message=...)
```

#### 3.2.6 retry.py - 重试管理

```python
# 🔴 硬编码 33-34: OneBot API 调用
# 行 192-206
if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
    result = await bot.api.call_action(
        "send_group_msg", group_id=int(task.group_id), message=message
    )

# 行 296-304
await bot.api.call_action(
    "send_group_forward_msg",
    group_id=int(task.group_id),
    messages=nodes,
)
```

### 3.3 硬编码影响分析

```
┌─────────────────────────────────────────────────────────────────┐
│                     硬编码影响链                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  main.py                                                        │
│    └── import AiocqhttpMessageEvent ──────────────────────────┐ │
│          │                                                     │ │
│          ▼                                                     │ │
│    所有命令处理器                                               │ │
│    (12个命令全部限制 QQ)                                        │ │
│          │                                                     │ │
│          ▼                                                     │ │
│  message_handler.py                                            │ │
│    └── call_action("get_group_msg_history") ──────────────────┤ │
│          │                                                     │ │
│          ▼                                                     │ │
│  auto_scheduler.py                                             │ │
│    └── call_action("get_group_info") ─────────────────────────┤ │
│    └── call_action("get_group_list") ─────────────────────────┤ │
│          │                                                     │ │
│          ▼                                                     │ │
│  message_sender.py / retry.py                                  │ │
│    └── call_action("send_group_msg") ─────────────────────────┘ │
│    └── call_action("send_group_forward_msg")                    │
│                                                                 │
│  结果: 插件完全无法在非 QQ 平台使用                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 跨平台解耦方案

### 4.1 设计目标

1. **平台无关的核心逻辑** - 分析、报告生成与平台解耦
2. **可插拔的平台适配器** - 每个平台独立的消息获取/发送实现
3. **渐进式迁移** - 保持 QQ 功能完整，逐步添加其他平台
4. **统一的接口抽象** - 定义清晰的平台能力接口

### 4.2 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    Plugin Architecture (目标)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                     │   │
│  │  main.py - 使用 AstrMessageEvent 基类                    │   │
│  │  - 命令处理器接受所有平台事件                             │   │
│  │  - 根据平台能力选择处理策略                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Domain Layer                          │   │
│  │  - MessageAnalyzer (平台无关)                            │   │
│  │  - ReportGenerator (平台无关)                            │   │
│  │  - LLMAnalyzer (平台无关)                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Platform Abstraction Layer                 │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │  IPlatformMessageRepository (Interface)          │   │   │
│  │  │  - fetch_messages(group_id, days) -> List[Msg]   │   │   │
│  │  │  - get_group_info(group_id) -> GroupInfo         │   │   │
│  │  │  - get_group_list() -> List[str]                 │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │  IPlatformMessageSender (Interface)              │   │   │
│  │  │  - send_text(group_id, text) -> bool             │   │   │
│  │  │  - send_image(group_id, image) -> bool           │   │   │
│  │  │  - send_file(group_id, file) -> bool             │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │  PlatformCapabilities (Value Object)             │   │   │
│  │  │  - supports_message_history: bool                │   │   │
│  │  │  - supports_group_list: bool                     │   │   │
│  │  │  - supports_file_upload: bool                    │   │   │
│  │  │  - supports_forward_message: bool                │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                Platform Implementations                  │   │
│  │                                                          │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │   │
│  │  │  OneBot    │ │  Telegram  │ │  Discord   │  ...      │   │
│  │  │  Adapter   │ │  Adapter   │ │  Adapter   │           │   │
│  │  └────────────┘ └────────────┘ └────────────┘           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 接口定义

#### 4.3.1 平台消息仓储接口

```python
# src/platform/interfaces.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class UnifiedMessage:
    """统一消息格式"""
    message_id: str
    sender_id: str
    sender_name: str
    content: str              # 纯文本内容
    raw_content: list         # 原始消息链
    timestamp: int
    message_type: str         # text, image, file, etc.

@dataclass
class UnifiedGroup:
    """统一群组格式"""
    group_id: str
    group_name: str
    member_count: int
    owner_id: Optional[str] = None

@dataclass
class PlatformCapabilities:
    """平台能力描述"""
    platform_name: str
    supports_message_history: bool = False
    supports_group_list: bool = False
    supports_group_info: bool = False
    supports_file_upload: bool = False
    supports_forward_message: bool = False
    max_message_history_days: int = 0

class IPlatformMessageRepository(ABC):
    """平台消息仓储接口"""
    
    @abstractmethod
    async def fetch_messages(
        self, 
        group_id: str, 
        days: int,
        max_count: int = 1000
    ) -> List[UnifiedMessage]:
        """获取群消息历史"""
        pass
    
    @abstractmethod
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取群信息"""
        pass
    
    @abstractmethod
    async def get_group_list(self) -> List[str]:
        """获取群列表"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力"""
        pass

class IPlatformMessageSender(ABC):
    """平台消息发送接口"""
    
    @abstractmethod
    async def send_text(self, group_id: str, text: str) -> bool:
        """发送文本消息"""
        pass
    
    @abstractmethod
    async def send_image(self, group_id: str, image_url: str) -> bool:
        """发送图片消息"""
        pass
    
    @abstractmethod
    async def send_file(self, group_id: str, file_path: str) -> bool:
        """发送文件"""
        pass
```

#### 4.3.2 OneBot 实现示例

```python
# src/platform/adapters/onebot_adapter.py
from ..interfaces import (
    IPlatformMessageRepository,
    IPlatformMessageSender,
    UnifiedMessage,
    UnifiedGroup,
    PlatformCapabilities,
)

class OneBotMessageRepository(IPlatformMessageRepository):
    """OneBot v11 消息仓储实现"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
    
    async def fetch_messages(
        self, group_id: str, days: int, max_count: int = 1000
    ) -> List[UnifiedMessage]:
        """通过 get_group_msg_history 获取消息"""
        if not hasattr(self.bot, "call_action"):
            return []
        
        try:
            result = await self.bot.call_action(
                "get_group_msg_history",
                group_id=int(group_id),
                count=max_count,
            )
            
            messages = []
            for msg in result.get("messages", []):
                # 转换为统一格式
                unified = self._convert_message(msg)
                if unified:
                    messages.append(unified)
            return messages
            
        except Exception as e:
            logger.error(f"OneBot fetch_messages failed: {e}")
            return []
    
    def _convert_message(self, raw_msg: dict) -> UnifiedMessage:
        """将 OneBot 消息转换为统一格式"""
        sender = raw_msg.get("sender", {})
        
        # 提取纯文本内容
        text_parts = []
        for seg in raw_msg.get("message", []):
            if seg.get("type") == "text":
                text_parts.append(seg.get("data", {}).get("text", ""))
        
        return UnifiedMessage(
            message_id=str(raw_msg.get("message_id", "")),
            sender_id=str(sender.get("user_id", "")),
            sender_name=sender.get("nickname", "") or sender.get("card", ""),
            content="".join(text_parts),
            raw_content=raw_msg.get("message", []),
            timestamp=raw_msg.get("time", 0),
            message_type="mixed",
        )
    
    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="onebot",
            supports_message_history=True,
            supports_group_list=True,
            supports_group_info=True,
            supports_file_upload=True,
            supports_forward_message=True,
            max_message_history_days=7,
        )
```

#### 4.3.3 Telegram 实现示例

```python
# src/platform/adapters/telegram_adapter.py
class TelegramMessageRepository(IPlatformMessageRepository):
    """Telegram 消息仓储实现"""
    
    def __init__(self, bot_client):
        self.bot = bot_client
    
    async def fetch_messages(
        self, group_id: str, days: int, max_count: int = 1000
    ) -> List[UnifiedMessage]:
        """通过 Telegram API 获取消息历史"""
        try:
            from datetime import datetime, timedelta
            
            # Telegram 使用 chat_id
            chat_id = int(group_id)
            
            # 获取消息历史 (需要 bot 有读取历史的权限)
            messages = []
            async for message in self.bot.get_chat_history(
                chat_id=chat_id,
                limit=max_count,
            ):
                # 过滤时间范围
                msg_time = message.date
                if msg_time < datetime.now() - timedelta(days=days):
                    break
                
                unified = self._convert_message(message)
                if unified:
                    messages.append(unified)
            
            return messages
            
        except Exception as e:
            logger.error(f"Telegram fetch_messages failed: {e}")
            return []
    
    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="telegram",
            supports_message_history=True,
            supports_group_list=True,
            supports_group_info=True,
            supports_file_upload=True,
            supports_forward_message=True,
            max_message_history_days=30,
        )
```

### 4.4 平台适配器工厂

```python
# src/platform/factory.py
from typing import Optional
from .interfaces import IPlatformMessageRepository, IPlatformMessageSender
from .adapters.onebot_adapter import OneBotMessageRepository, OneBotMessageSender
from .adapters.telegram_adapter import TelegramMessageRepository, TelegramMessageSender
from .adapters.discord_adapter import DiscordMessageRepository, DiscordMessageSender

class PlatformAdapterFactory:
    """平台适配器工厂"""
    
    @staticmethod
    def create_repository(
        platform_name: str, 
        bot_instance
    ) -> Optional[IPlatformMessageRepository]:
        """根据平台类型创建消息仓储"""
        
        adapters = {
            "aiocqhttp": OneBotMessageRepository,
            "telegram": TelegramMessageRepository,
            "discord": DiscordMessageRepository,
            "slack": SlackMessageRepository,
            "lark": LarkMessageRepository,
        }
        
        adapter_class = adapters.get(platform_name)
        if adapter_class:
            return adapter_class(bot_instance)
        
        return None
    
    @staticmethod
    def create_sender(
        platform_name: str, 
        bot_instance
    ) -> Optional[IPlatformMessageSender]:
        """根据平台类型创建消息发送器"""
        
        senders = {
            "aiocqhttp": OneBotMessageSender,
            "telegram": TelegramMessageSender,
            "discord": DiscordMessageSender,
            "slack": SlackMessageSender,
            "lark": LarkMessageSender,
        }
        
        sender_class = senders.get(platform_name)
        if sender_class:
            return sender_class(bot_instance)
        
        return None
    
    @staticmethod
    def get_supported_platforms() -> list[str]:
        """获取支持的平台列表"""
        return ["aiocqhttp", "telegram", "discord", "slack", "lark"]
```

### 4.5 重构后的命令处理器

```python
# main.py (重构后)
from astrbot.api.event import AstrMessageEvent  # 使用基类

class GroupDailyAnalysis(Star):  # 改名，去掉 QQ 前缀
    
    @filter.command("群分析")
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AstrMessageEvent, days: int | None = None  # 使用基类
    ):
        """分析群聊日常活动 - 跨平台支持"""
        
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return
        
        platform_name = event.get_platform_name()
        
        # 获取平台适配器
        repository = self._get_repository_for_platform(platform_name, event)
        if not repository:
            yield event.plain_result(f"❌ 平台 {platform_name} 暂不支持此功能")
            return
        
        # 检查平台能力
        capabilities = repository.get_capabilities()
        if not capabilities.supports_message_history:
            yield event.plain_result(
                f"❌ 平台 {platform_name} 不支持获取消息历史"
            )
            return
        
        # 使用统一接口获取消息
        messages = await repository.fetch_messages(group_id, days or 1)
        
        if not messages:
            yield event.plain_result("❌ 未找到足够的消息记录")
            return
        
        # 后续分析逻辑不变...
        yield event.plain_result(f"📊 已获取 {len(messages)} 条消息，正在分析...")
        
        # 分析和报告生成使用统一的消息格式
        analysis_result = await self.message_analyzer.analyze_unified_messages(
            messages, group_id, event.unified_msg_origin
        )
        
        # 发送报告
        await self._send_report(event, analysis_result)
```

---

## 5. 执行路线图

### Phase 0: 准备工作 (0.5 天)

**目标**: 建立基础设施

| 任务 | 说明 |
|------|------|
| 创建 `src/platform/` 目录 | 平台抽象层 |
| 定义接口文件 | `interfaces.py` |
| 创建工厂类 | `factory.py` |

### Phase 1: OneBot 适配器 (1 天)

**目标**: 将现有 QQ 逻辑封装为适配器

| 任务 | 说明 |
|------|------|
| 实现 `OneBotMessageRepository` | 封装 `get_group_msg_history` |
| 实现 `OneBotMessageSender` | 封装消息发送 |
| 添加消息格式转换 | OneBot → UnifiedMessage |
| 单元测试 | 确保功能不变 |

### Phase 2: 核心逻辑解耦 (1 天)

**目标**: 使核心逻辑平台无关

| 任务 | 说明 |
|------|------|
| 修改 `MessageHandler` | 使用 `UnifiedMessage` |
| 修改 `MessageAnalyzer` | 移除平台假设 |
| 修改 `AutoScheduler` | 使用适配器工厂 |
| 修改 `BotManager` | 重命名 QQ 相关方法 |

### Phase 3: main.py 重构 (0.5 天)

**目标**: 使命令处理器跨平台

| 任务 | 说明 |
|------|------|
| 移除 `AiocqhttpMessageEvent` 导入 | 使用基类 |
| 移除类型检查 | 改用能力检查 |
| 添加平台适配器选择逻辑 | 根据 `platform_name` |
| 更新错误消息 | 更通用的提示 |

### Phase 4: 添加 Telegram 支持 (1 天)

**目标**: 验证跨平台架构

| 任务 | 说明 |
|------|------|
| 实现 `TelegramMessageRepository` | 使用 python-telegram-bot |
| 实现 `TelegramMessageSender` | |
| 测试 Telegram 群分析 | 端到端验证 |

### Phase 5: 添加更多平台 (可选)

| 平台 | 优先级 | 工作量 |
|------|--------|--------|
| Discord | P1 | 1 天 |
| Slack | P2 | 1 天 |
| 飞书 | P2 | 1 天 |
| 钉钉 | P3 | 1 天 |

---

## 6. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 平台 API 差异大 | 高 | 中 | 统一消息格式 + 能力检查 |
| 消息历史获取受限 | 高 | 高 | 明确标注平台能力，提供降级方案 |
| 表情/特殊消息处理 | 中 | 低 | 只提取文本内容进行分析 |
| 测试覆盖不足 | 中 | 中 | 为每个适配器编写集成测试 |
| 性能差异 | 低 | 低 | 异步处理 + 缓存 |

---

## 7. 总结

### 7.1 关键发现

1. **AstrBot 已有完善的平台抽象** - 不需要自建抽象层
2. **插件硬编码严重但可解耦** - 约 34 处需要修改
3. **核心分析逻辑平台无关** - LLM 分析、报告生成不受影响
4. **渐进式迁移可行** - 可以保持 QQ 功能同时添加新平台

### 7.2 建议优先级

| 优先级 | 任务 | 收益 |
|--------|------|------|
| **P0** | 定义平台抽象接口 | 架构基础 |
| **P0** | 封装 OneBot 适配器 | 保持现有功能 |
| **P1** | 重构 main.py 使用基类 | 解除平台限制 |
| **P1** | 添加 Telegram 支持 | 验证架构 |
| **P2** | 添加 Discord 支持 | 扩大用户群 |

### 7.3 预期成果

- ✅ 插件可在 5+ 主流平台运行
- ✅ 新增平台只需实现适配器接口
- ✅ 核心逻辑无需修改
- ✅ 保持与 AstrBot 框架的对齐

---

## 附录 A: 平台 API 对比

| 功能 | OneBot v11 | Telegram | Discord | Slack |
|------|------------|----------|---------|-------|
| 获取消息历史 | `get_group_msg_history` | `get_chat_history` | `channel.history()` | `conversations.history` |
| 获取群信息 | `get_group_info` | `get_chat` | `get_channel` | `conversations.info` |
| 获取群列表 | `get_group_list` | `get_my_commands` | `guilds` | `conversations.list` |
| 发送文本 | `send_group_msg` | `send_message` | `channel.send` | `chat.postMessage` |
| 发送图片 | `[CQ:image]` | `send_photo` | `channel.send(file=)` | `files.upload` |
| 发送文件 | `[CQ:file]` | `send_document` | `channel.send(file=)` | `files.upload` |
| 转发消息 | `send_group_forward_msg` | N/A | N/A | N/A |

## 附录 B: 参考资料

1. AstrBot 官方文档 - https://astrbot.app/
2. OneBot v11 标准 - https://github.com/botuniverse/onebot-11
3. python-telegram-bot - https://python-telegram-bot.org/
4. Pycord (Discord) - https://pycord.dev/
5. Slack SDK - https://slack.dev/python-slack-sdk/
