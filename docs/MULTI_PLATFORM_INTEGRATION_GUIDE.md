# 多平台接入完整指南

> **版本**: 1.0  
> **更新日期**: 2026-02-09  
> **适用版本**: `astrbot_plugin_qq_group_daily_analysis` v0.3.0+

---

## 目录

1. [架构总览](#1-架构总览)
2. [核心组件](#2-核心组件)
3. [接入新平台的完整步骤](#3-接入新平台的完整步骤)
4. [详细接口规范](#4-详细接口规范)
5. [Corner Cases 与注意事项](#5-corner-cases-与注意事项)
6. [平台差异对照表](#6-平台差异对照表)
7. [调试与故障排查](#7-调试与故障排查)
8. [现有适配器参考](#8-现有适配器参考)
9. [测试清单](#9-测试清单)

---

## 1. 架构总览

本插件采用 **DDD (领域驱动设计)** 架构，通过 **适配器模式** 实现多平台支持。核心设计原则：

```
┌────────────────────────────────────────────────────────────────────┐
│                        main.py (入口层)                             │
│   - 处理 AstrBot 事件和命令                                         │
│   - 协调各层组件                                                    │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                    应用层 (Application Layer)                       │
│   - AnalysisApplicationService: 编排完整的分析流程                  │
│   - AutoScheduler: 定时任务管理                                     │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                      领域层 (Domain Layer)                          │
│   - 值对象: UnifiedMessage, PlatformCapabilities, UnifiedGroup      │
│   - 领域服务: AnalysisDomainService, StatisticsService              │
│   - 仓储接口: IMessageRepository, IMessageSender, IAvatarRepository │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                   基础设施层 (Infrastructure Layer)                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    PlatformAdapter (抽象基类)                 │   │
│  │  实现: IMessageRepository + IMessageSender +                 │   │
│  │        IGroupInfoRepository + IAvatarRepository              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           ▲              ▲              ▲              ▲            │
│           │              │              │              │            │
│  ┌────────┴───┐  ┌──────┴──────┐  ┌────┴────────┐  ┌──┴─────────┐  │
│  │OneBotAdapter│  │DiscordAdapter│  │TelegramAdapter│ │ 新平台Adapter│ │
│  └────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │        BotManager: 管理多平台 Bot 实例和适配器                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │     PlatformAdapterFactory: 适配器注册与创建工厂               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **平台隔离** | 所有平台特定代码都封装在对应的 Adapter 中 |
| **统一接口** | 通过 `UnifiedMessage` 等值对象实现跨平台数据标准化 |
| **能力声明** | 每个适配器通过 `PlatformCapabilities` 声明支持的功能 |
| **懒加载** | 支持 Bot 客户端的延迟初始化，适应不同平台的启动时序 |
| **容错设计** | 所有方法都有异常处理，失败时返回空值而非抛出异常 |

---

## 2. 核心组件

### 2.1 文件结构

```
src/
├── domain/
│   ├── value_objects/
│   │   ├── unified_message.py       # 统一消息格式
│   │   ├── unified_group.py         # 统一群组/成员信息
│   │   └── platform_capabilities.py # 平台能力声明
│   └── repositories/
│       ├── message_repository.py    # 消息仓储接口
│       └── avatar_repository.py     # 头像仓储接口
│
├── infrastructure/
│   └── platform/
│       ├── base.py                  # PlatformAdapter 抽象基类
│       ├── factory.py               # PlatformAdapterFactory 工厂
│       ├── bot_manager.py           # BotManager 多平台管理
│       └── adapters/
│           ├── onebot_adapter.py    # OneBot v11 适配器
│           └── discord_adapter.py   # Discord 适配器
```

### 2.2 接口依赖关系

```python
class PlatformAdapter(
    IMessageRepository,    # 消息获取
    IMessageSender,        # 消息发送
    IGroupInfoRepository,  # 群组信息
    IAvatarRepository,     # 头像获取
    ABC                    # 抽象基类
):
    pass
```

---

## 3. 接入新平台的完整步骤

### 步骤 1：创建适配器文件

```bash
# 在 adapters 目录创建新文件
# src/infrastructure/platform/adapters/your_platform_adapter.py
```

### 步骤 2：实现适配器类

```python
"""
YourPlatform 平台适配器

支持 YourPlatform 的消息获取、发送和群组管理功能。
"""

from typing import Any, Optional
from datetime import datetime, timedelta

from ....domain.value_objects.platform_capabilities import PlatformCapabilities
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger
from ..base import PlatformAdapter


class YourPlatformAdapter(PlatformAdapter):
    """YourPlatform 平台适配器实现"""

    def __init__(self, bot_instance: Any, config: dict | None = None):
        super().__init__(bot_instance, config)
        # 1. 保存机器人自身 ID（用于消息过滤）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""
        # 2. 可选：缓存 SDK 客户端
        self._cached_client = None

    def _init_capabilities(self) -> PlatformCapabilities:
        """声明平台能力 - 这是最重要的方法之一"""
        return PlatformCapabilities(
            platform_name="your_platform",
            platform_version="v1.0",
            # === 消息获取能力 ===
            supports_message_history=True,  # 是否支持获取历史消息
            max_message_history_days=30,    # 最大历史天数
            max_message_count=10000,        # 单次最大消息数
            # === 群组信息能力 ===
            supports_group_list=True,       # 是否支持获取群列表
            supports_group_info=True,       # 是否支持获取群信息
            supports_member_list=True,      # 是否支持获取成员列表
            supports_member_info=True,      # 是否支持获取成员信息
            # === 消息发送能力 ===
            supports_text_message=True,     # 发送文本
            supports_image_message=True,    # 发送图片
            supports_file_message=True,     # 发送文件
            supports_reply_message=True,    # 回复消息
            max_text_length=4096,           # 最大文本长度
            max_image_size_mb=10.0,         # 最大图片大小
            # === 头像能力 ===
            supports_user_avatar=True,      # 用户头像
            supports_group_avatar=False,    # 群组头像
            avatar_needs_api_call=True,     # 是否需要 API 调用
            avatar_sizes=(100, 200, 400),   # 支持的头像尺寸
        )

    # ... 实现所有抽象方法 ...
```

### 步骤 3：在工厂中注册

修改 `src/infrastructure/platform/factory.py`:

```python
def _register_adapters():
    # ... 现有注册 ...

    try:
        from .adapters.your_platform_adapter import YourPlatformAdapter
        PlatformAdapterFactory.register("your_platform", YourPlatformAdapter)
        # 可选：添加别名
        PlatformAdapterFactory.register("your_platform_alias", YourPlatformAdapter)
    except ImportError:
        pass


_register_adapters()
```

### 步骤 4：更新 BotManager 的平台检测 (可选)

如果 AstrBot 无法自动识别你的平台类型，需要在 `bot_manager.py` 的 `_detect_platform_name` 方法中添加检测逻辑：

```python
def _detect_platform_name(self, bot_instance) -> str | None:
    # ... 现有逻辑 ...

    # 添加 YourPlatform 的特征检测
    if hasattr(bot_instance, "your_platform_specific_method"):
        return "your_platform"

    # 类名匹配
    class_name = type(bot_instance).__name__.lower()
    if "yourplatform" in class_name:
        return "your_platform"

    return None
```

---

## 4. 详细接口规范

### 4.1 IMessageRepository (消息获取)

```python
async def fetch_messages(
    self,
    group_id: str,
    days: int = 1,
    max_count: int = 100,
    before_id: str | None = None,
) -> list[UnifiedMessage]:
    """
    获取群组历史消息

    参数:
        group_id: 群组/频道 ID （字符串格式）
        days: 获取最近 N 天的消息
        max_count: 最大消息数量
        before_id: 分页锚点消息 ID

    返回:
        统一格式的消息列表，按时间 **升序** 排列

    重要事项:
        1. 必须过滤机器人自己的消息
        2. 必须进行时间范围过滤
        3. 返回前需要按时间排序
        4. 异常时返回空列表，不要抛出异常
    """
```

### 4.2 消息转换 (_convert_message)

```python
def _convert_message(self, raw_msg: Any, group_id: str) -> UnifiedMessage | None:
    """
    将平台原生消息转换为 UnifiedMessage

    关键字段说明:
        - message_id: 消息唯一 ID (字符串)
        - sender_id: 发送者 ID (字符串)
        - sender_name: 发送者基础名称
        - sender_card: 群内名片/昵称 (优先显示)
        - group_id: 群组 ID
        - text_content: 纯文本内容 (用于 LLM 分析)
        - contents: 消息链 (文本+图片+表情等)
        - timestamp: Unix 时间戳 (整数)
        - platform: 平台标识
        - reply_to_id: 回复的消息 ID (可选)
    """
```

### 4.3 convert_to_raw_format (向后兼容)

```python
def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
    """
    将统一消息格式转换为 OneBot 风格的字典格式

    这是为了兼容现有的 MessageHandler 分析逻辑。
    必须生成符合以下结构的字典:

    {
        "message_id": "...",
        "group_id": "...",
        "time": 1234567890,  # Unix 时间戳
        "sender": {
            "user_id": "...",
            "nickname": "...",
            "card": "..."  # 群名片
        },
        "message": [
            {"type": "text", "data": {"text": "..."}},
            {"type": "image", "data": {"url": "...", "file": "..."}},
            {"type": "at", "data": {"qq": "..."}},
            # ...
        ],
        "user_id": "...",  # 冗余字段，兼容用
    }
    """
```

### 4.4 IMessageSender (消息发送)

```python
async def send_text(self, group_id: str, text: str, reply_to: str | None = None) -> bool:
    """发送文本消息，返回是否成功"""

async def send_image(self, group_id: str, image_path: str, caption: str = "") -> bool:
    """
    发送图片消息

    image_path 可能是:
    - 本地文件路径: "/path/to/image.png"
    - HTTP URL: "https://example.com/image.png"

    需要根据平台特性处理不同情况
    """

async def send_file(self, group_id: str, file_path: str, filename: str | None = None) -> bool:
    """发送文件消息"""

async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
    """
    发送合并转发消息

    nodes 格式:
    [
        {
            "type": "node",
            "data": {
                "name": "发送者名称",
                "uin": "发送者ID",
                "content": "消息内容"
            }
        },
        ...
    ]

    如果平台不支持合并转发，应转换为多条普通消息发送
    """
```

### 4.5 IAvatarRepository (头像获取)

```python
async def get_user_avatar_url(self, user_id: str, size: int = 100) -> str | None:
    """
    获取用户头像 URL

    不同平台的策略:
    - QQ/OneBot: 直接通过 URL 模板构造，无需 API 调用
    - Discord: 通过 CDN URL 模板构造，需要对齐到 2 的幂次方尺寸
    - Telegram: 需要调用 API 获取 file_id 再转换
    - Slack: 从用户信息 API 的 profile.image_* 字段获取
    """

async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
    """
    获取头像的 Base64 数据

    格式: "data:image/png;base64,..."
    用于 HTML 模板渲染
    如果不支持，返回 None
    """

async def batch_get_avatar_urls(self, user_ids: list[str], size: int = 100) -> dict[str, str | None]:
    """批量获取头像 URL"""
```

---

## 5. Corner Cases 与注意事项

### 5.1 机器人客户端获取

> [!CAUTION]
> **懒加载问题**：许多平台的 Bot 客户端在插件初始化时可能尚未准备好。

**Discord 适配器的解决方案**：

```python
@property
def _discord_client(self) -> Any:
    """懒加载 + 多路径探测"""
    if self._cached_client:
        return self._cached_client

    # 探测路径 A: bot 本身就是 Client
    if hasattr(self.bot, "get_channel"):
        self._cached_client = self.bot
    # 探测路径 B: bot.client
    elif hasattr(self.bot, "client"):
        self._cached_client = self.bot.client
    # 探测路径 C: 其他常见属性名
    else:
        for attr in ("_client", "discord_client", "_discord_client"):
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "get_channel"):
                    self._cached_client = client
                    break

    # 兜底：从客户端获取机器人 ID
    if not self.bot_user_id and self._cached_client:
        if hasattr(self._cached_client, "user") and self._cached_client.user:
            self.bot_user_id = str(self._cached_client.user.id)

    return self._cached_client
```

### 5.2 机器人消息过滤

> [!IMPORTANT]
> 必须过滤掉机器人自己发送的消息，否则分析报告会包含机器人的回复。

```python
# 在 fetch_messages 中
for msg in raw_messages:
    sender_id = str(msg.author.id)
    # 检查是否是机器人自己
    if self.bot_user_id and sender_id == self.bot_user_id:
        continue
    # ... 处理消息
```

**注意**：机器人 ID 可能来自多个来源：
1. 配置文件中的 `bot_user_id` 或 `bot_qq_ids`
2. 运行时从 `bot.user.id` 获取
3. 从消息事件中提取

### 5.3 发送者名称优先级

> [!TIP]
> 不同平台对用户名称的定义不同，需要正确设置优先级。

**Discord 的名称层级**：
```python
# 1. 服务器昵称 (nick) - 最具体
# 2. 全局显示名 (global_name) - 用户设置的显示名
# 3. 用户名 (name) - 基础用户名

sender_card = None
if hasattr(raw_msg.author, "nick") and raw_msg.author.nick:
    sender_card = raw_msg.author.nick
elif hasattr(raw_msg.author, "global_name") and raw_msg.author.global_name:
    sender_card = raw_msg.author.global_name

return UnifiedMessage(
    sender_name=raw_msg.author.name,  # 基础名称
    sender_card=sender_card,           # 优先显示的群内名片
    # ...
)
```

**OneBot/QQ 的名称层级**：
```python
sender_name = sender.get("nickname", "")
sender_card = sender.get("card", "") or None  # 空字符串转为 None
```

### 5.4 图片发送策略

> [!WARNING]
> 不同平台对图片发送的处理方式差异很大。

**场景 1：本地文件**

| 平台 | 处理方式 |
|------|----------|
| OneBot | `file:///path/to/image.png` |
| Discord | `discord.File(image_path)` |

**场景 2：HTTP URL**

| 平台 | 处理方式 |
|------|----------|
| OneBot | 直接使用 URL（后端自动下载） |
| Discord | **必须下载到内存再发送**（Discord 无法访问内部 URL） |

**Discord 的 URL 图片处理**：
```python
async def send_image(self, group_id: str, image_path: str, caption: str = "") -> bool:
    if image_path.startswith(("http://", "https://")):
        # 下载到内存
        async with aiohttp.ClientSession() as session:
            async with session.get(image_path, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    file_to_send = discord.File(BytesIO(data), filename="report.png")
                    await channel.send(file=file_to_send)
                else:
                    # 兜底：直接发送 URL 让 Discord 尝试解析
                    await channel.send(content=image_path)
    else:
        file_to_send = discord.File(image_path)
        await channel.send(file=file_to_send)
```

### 5.5 频道/群组获取的缓存与网络请求

> [!NOTE]
> 大多数平台 SDK 都有缓存机制，但缓存可能不完整。

```python
# Discord 的双重获取策略
channel = self._discord_client.get_channel(channel_id)  # 从缓存获取
if not channel:
    # 缓存未命中，发起网络请求
    try:
        channel = await self._discord_client.fetch_channel(channel_id)
    except Exception as e:
        logger.debug(f"获取频道失败: {e}")
        return []
```

### 5.6 消息历史 API 的限制

| 平台 | 限制说明 |
|------|----------|
| OneBot/QQ | 依赖后端实现，NapCat 支持较好，go-cqhttp 需要配置 |
| Discord | 需要 "Read Message History" 权限，默认返回降序需要排序 |
| Telegram Bot API | **不支持获取历史消息**，需要 Telethon/MTProto |
| Slack | 免费版有 90 天限制，每次最多 1000 条 |

### 5.7 头像尺寸对齐

不同平台支持的头像尺寸不同，需要对齐到最近的有效值：

```python
# Discord: 必须是 2 的幂次方
DISCORD_SIZES = (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)

# QQ: 固定尺寸
QQ_SIZES = (40, 100, 140, 160, 640)

def _get_nearest_size(self, requested_size: int, available_sizes: tuple) -> int:
    """获取最接近的可用尺寸"""
    return min(available_sizes, key=lambda x: abs(x - requested_size))
```

### 5.8 合并转发消息的兼容处理

> [!IMPORTANT]
> 并非所有平台都支持合并转发消息。

**OneBot**：原生支持 `send_group_forward_msg`

**Discord**：需要转换为多条普通消息
```python
async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
    # 将节点汇总为格式化文本
    lines = ["📊 **结构化报告摘要**\n"]
    for node in nodes:
        data = node.get("data", node)
        name = data.get("name", "AstrBot")
        content = data.get("content", "")
        lines.append(f"**[{name}]**:\n{content}\n")

    full_text = "\n".join(lines)

    # 分段处理（Discord 限制 2000 字符）
    if len(full_text) > 1900:
        parts = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
        for part in parts:
            await channel.send(content=part)
    else:
        await channel.send(content=full_text)
```

### 5.9 平台 ID 与群组 ID 的区别

| 类型 | 说明 | 示例 |
|------|------|------|
| `platform_id` | AstrBot 平台实例的唯一标识 | `"discord-main"`, `"onebot-qq1"` |
| `group_id` | 群组/频道的 ID | `"123456789"` (QQ群号), `"987654321"` (Discord频道ID) |

**BotManager 通过 `platform_id` 管理多个平台实例**：
```python
# 获取特定平台的适配器
adapter = bot_manager.get_adapter(platform_id="discord-main")

# 如果只有一个平台，可以省略 platform_id
adapter = bot_manager.get_adapter()
```

### 5.10 异步上下文中的同步操作

> [!CAUTION]
> 避免在异步方法中执行阻塞的同步操作。

**错误示例**：
```python
async def fetch_messages(self, ...):
    # ❌ 这会阻塞事件循环
    with open("cache.json", "r") as f:
        cache = json.load(f)
```

**正确示例**：
```python
async def fetch_messages(self, ...):
    # ✅ 使用 asyncio.to_thread
    cache = await asyncio.to_thread(self._load_cache_sync)

def _load_cache_sync(self):
    with open("cache.json", "r") as f:
        return json.load(f)
```

---

## 6. 平台差异对照表

### 6.1 能力对比

| 能力 | OneBot (QQ) | Discord | Telegram Bot | Telegram UserBot | Slack |
|------|-------------|---------|--------------|------------------|-------|
| 历史消息获取 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 最大历史天数 | 7 | 30 | 0 | 365 | 90 |
| 群列表获取 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 成员列表获取 | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| 图片消息 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 文件消息 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 合并转发 | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| 用户头像 | ✅ (URL模板) | ✅ (CDN) | ✅ (API) | ✅ (API) | ✅ (API) |
| 编辑消息 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 撤回消息 | ✅ | ❌ | ❌ | ❌ | ❌ |

### 6.2 消息类型映射

| MessageContentType | OneBot 类型 | Discord 类型 | 说明 |
|--------------------|-------------|--------------|------|
| TEXT | `text` | `content` | 纯文本 |
| IMAGE | `image` | `attachment` (image/*) | 图片 |
| VIDEO | `video` | `attachment` (video/*) | 视频 |
| VOICE | `record` | `attachment` (audio/*) | 语音 |
| FILE | (文件消息) | `attachment` (其他) | 文件 |
| AT | `at` | `@mention` | @提及 |
| EMOJI | `face`, `mface` 等 | `sticker`, `emoji` | 表情 |
| REPLY | `reply` | `reference` | 回复 |
| FORWARD | `forward` | N/A | 转发 |

---

## 7. 调试与故障排查

### 7.1 常见问题

**Q1: 适配器创建失败**

检查以下几点：
1. 适配器类是否正确继承 `PlatformAdapter`
2. 是否实现了所有抽象方法
3. 工厂注册是否正确
4. 依赖库是否已安装

```python
# 验证注册
from src.infrastructure.platform import PlatformAdapterFactory
print(PlatformAdapterFactory.get_supported_platforms())
```

**Q2: 消息获取返回空列表**

1. 检查 Bot 是否有权限获取历史消息
2. 检查 `group_id` 格式是否正确
3. 检查时间范围是否合理
4. 查看日志中的异常信息

**Q3: 图片发送失败**

1. 检查文件路径是否正确
2. URL 是否可访问
3. 文件大小是否超过限制
4. 是否有发送图片的权限

### 7.2 调试日志

适配器内部使用统一的 logger：

```python
from ....utils.logger import logger

# 使用示例
logger.debug(f"正在获取频道 {group_id} 的消息")
logger.warning(f"API 返回非预期结果: {response}")
logger.error(f"消息发送失败: {e}", exc_info=True)
```

### 7.3 容器内验证

```bash
# 检查支持的平台
docker exec astrbot python -c "
from data.plugins.astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform import PlatformAdapterFactory
print('支持的平台:', PlatformAdapterFactory.get_supported_platforms())
"

# 检查适配器创建
docker exec astrbot python -c "
from data.plugins.astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform import PlatformAdapterFactory
adapter = PlatformAdapterFactory.create('discord', None, {})
if adapter:
    print('Discord 能力:', adapter.get_capabilities())
else:
    print('创建失败')
"
```

---

## 8. 现有适配器参考

### 8.1 OneBot 适配器 (`onebot_adapter.py`)

**特点**：
- 头像通过 URL 模板直接构造，无需 API 调用
- 支持多种表情类型 (`face`, `mface`, `bface`, `sface`)
- 消息格式可能是字符串或列表，需要兼容处理
- 支持合并转发消息

**关键代码**：

```python
# 头像 URL 模板
USER_AVATAR_TEMPLATE = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
USER_AVATAR_HD_TEMPLATE = "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec={size}&img_type=jpg"
GROUP_AVATAR_TEMPLATE = "https://p.qlogo.cn/gh/{group_id}/{group_id}/{size}/"

# 消息格式兼容
if isinstance(message_chain, str):
    message_chain = [{"type": "text", "data": {"text": message_chain}}]
```

### 8.2 Discord 适配器 (`discord_adapter.py`)

**特点**：
- 需要懒加载和多路径探测获取客户端
- 头像尺寸必须对齐到 2 的幂次方
- 图片发送需要先下载再上传
- 合并转发需要转换为格式化文本
- 支持处理 Embed 和 Sticker

**关键代码**：

```python
# 多路径客户端探测
for attr in ("_client", "discord_client", "_discord_client"):
    if hasattr(self.bot, attr):
        client = getattr(self.bot, attr)
        if hasattr(client, "get_channel"):
            return client

# 头像尺寸对齐
allowed_sizes = (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
target_size = min(allowed_sizes, key=lambda x: abs(x - size))
return user.display_avatar.with_size(target_size).url
```

---

## 9. 测试清单

### 9.1 单元测试

```python
# tests/unit/infrastructure/platform/test_your_adapter.py

import pytest
from src.infrastructure.platform.adapters.your_platform_adapter import YourPlatformAdapter

class TestYourPlatformAdapter:
    def test_init_capabilities(self):
        adapter = YourPlatformAdapter(mock_bot, {})
        caps = adapter.get_capabilities()
        assert caps.platform_name == "your_platform"
        assert caps.supports_message_history == True
        assert caps.can_analyze() == True

    @pytest.mark.asyncio
    async def test_fetch_messages_empty(self):
        adapter = YourPlatformAdapter(mock_bot, {})
        messages = await adapter.fetch_messages("invalid_group", days=1)
        assert isinstance(messages, list)
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_convert_to_raw_format(self):
        # 测试消息格式转换
        pass
```

### 9.2 集成测试清单

- [ ] 适配器能正确注册到工厂
- [ ] BotManager 能自动发现平台实例
- [ ] 消息获取返回正确格式
- [ ] 消息发送能正常工作
- [ ] 头像 URL 能正确生成
- [ ] 不支持的功能返回合理的默认值

### 9.3 手动测试步骤

1. **启动 AstrBot 并加载插件**
   ```bash
   docker-compose up -d
   docker logs -f astrbot
   ```

2. **检查平台发现日志**
   - 应该看到 "已创建 X 个 PlatformAdapter"

3. **使用命令测试**
   - `/群分析` - 检查消息获取和报告生成
   - `/分析设置 status` - 检查状态输出

4. **检查输出结果**
   - 图片报告应正确显示
   - 用户名称应使用群内名片

---

## 附录 A：完整适配器模板

```python
"""
NewPlatform 平台适配器模板
"""

from datetime import datetime, timedelta
from typing import Any

from ....domain.value_objects.platform_capabilities import PlatformCapabilities
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger
from ..base import PlatformAdapter


class NewPlatformAdapter(PlatformAdapter):
    """NewPlatform 平台适配器"""

    def __init__(self, bot_instance: Any, config: dict | None = None):
        super().__init__(bot_instance, config)
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

    def _init_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="new_platform",
            platform_version="v1.0",
            supports_message_history=True,
            max_message_history_days=30,
            max_message_count=1000,
            supports_group_list=True,
            supports_group_info=True,
            supports_member_list=True,
            supports_member_info=True,
            supports_text_message=True,
            supports_image_message=True,
            supports_file_message=True,
            supports_reply_message=True,
            max_text_length=4096,
            supports_user_avatar=True,
            supports_group_avatar=False,
        )

    # ==================== IMessageRepository ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: str | None = None,
    ) -> list[UnifiedMessage]:
        try:
            # TODO: 调用平台 API 获取消息
            raw_messages = []

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []
            for raw_msg in raw_messages:
                # 时间过滤
                msg_time = datetime.fromtimestamp(raw_msg.get("time", 0))
                if not (start_time <= msg_time <= end_time):
                    continue

                # 过滤机器人消息
                sender_id = str(raw_msg.get("sender_id", ""))
                if self.bot_user_id and sender_id == self.bot_user_id:
                    continue

                unified = self._convert_message(raw_msg, group_id)
                if unified:
                    messages.append(unified)

            messages.sort(key=lambda m: m.timestamp)
            return messages

        except Exception as e:
            logger.error(f"获取消息失败: {e}", exc_info=True)
            return []

    def _convert_message(self, raw_msg: dict, group_id: str) -> UnifiedMessage | None:
        try:
            return UnifiedMessage(
                message_id=str(raw_msg.get("id", "")),
                sender_id=str(raw_msg.get("sender_id", "")),
                sender_name=raw_msg.get("sender_name", ""),
                sender_card=raw_msg.get("sender_card"),
                group_id=group_id,
                text_content=raw_msg.get("text", ""),
                contents=(MessageContent(type=MessageContentType.TEXT, text=raw_msg.get("text", "")),),
                timestamp=raw_msg.get("time", 0),
                platform="new_platform",
                reply_to_id=raw_msg.get("reply_to"),
            )
        except Exception as e:
            logger.debug(f"消息转换失败: {e}")
            return None

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        return [
            {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": [{"type": "text", "data": {"text": c.text}} for c in msg.contents if c.type == MessageContentType.TEXT],
                "user_id": msg.sender_id,
            }
            for msg in messages
        ]

    # ==================== IMessageSender ====================

    async def send_text(self, group_id: str, text: str, reply_to: str | None = None) -> bool:
        try:
            # TODO: 实现发送逻辑
            return True
        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def send_image(self, group_id: str, image_path: str, caption: str = "") -> bool:
        try:
            # TODO: 实现发送逻辑
            return True
        except Exception as e:
            logger.error(f"发送图片失败: {e}")
            return False

    async def send_file(self, group_id: str, file_path: str, filename: str | None = None) -> bool:
        try:
            # TODO: 实现发送逻辑
            return True
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            return False

    # ==================== IGroupInfoRepository ====================

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        try:
            # TODO: 实现获取逻辑
            return UnifiedGroup(
                group_id=group_id,
                group_name="Unknown",
                member_count=0,
                platform="new_platform",
            )
        except Exception:
            return None

    async def get_group_list(self) -> list[str]:
        try:
            # TODO: 实现获取逻辑
            return []
        except Exception:
            return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        try:
            # TODO: 实现获取逻辑
            return []
        except Exception:
            return []

    async def get_member_info(self, group_id: str, user_id: str) -> UnifiedMember | None:
        try:
            # TODO: 实现获取逻辑
            return None
        except Exception:
            return None

    # ==================== IAvatarRepository ====================

    async def get_user_avatar_url(self, user_id: str, size: int = 100) -> str | None:
        try:
            # TODO: 实现获取逻辑
            return None
        except Exception:
            return None

    async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
        return None

    async def get_group_avatar_url(self, group_id: str, size: int = 100) -> str | None:
        return None

    async def batch_get_avatar_urls(self, user_ids: list[str], size: int = 100) -> dict[str, str | None]:
        return {uid: await self.get_user_avatar_url(uid, size) for uid in user_ids}
```

---

*文档最后更新: 2026-02-09*
