# 平台接入开发指南

本文档说明如何为群聊日报分析插件接入新的消息平台。

## 目录

1. [架构概述](#架构概述)
2. [快速开始](#快速开始)
3. [详细步骤](#详细步骤)
4. [接口说明](#接口说明)
5. [最佳实践](#最佳实践)
6. [示例代码](#示例代码)
7. [测试指南](#测试指南)

---

## 架构概述

本插件采用 DDD（领域驱动设计）架构，通过平台适配器模式实现多平台支持：

```
┌─────────────────────────────────────────────────────────┐
│                    应用层 (Application)                   │
│                  AnalysisOrchestrator                    │
└─────────────────────────┬───────────────────────────────┘
                          │ 使用
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   基础设施层 (Infrastructure)             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              PlatformAdapter (抽象基类)           │   │
│  │  - fetch_messages()                              │   │
│  │  - send_text/image/file()                        │   │
│  │  - get_group_info()                              │   │
│  │  - convert_to_raw_format()                       │   │
│  └─────────────────────────────────────────────────┘   │
│           ▲              ▲              ▲               │
│           │              │              │               │
│  ┌────────┴───┐  ┌──────┴──────┐  ┌────┴────────┐     │
│  │OneBotAdapter│  │DiscordAdapter│  │ 新平台Adapter │     │
│  │  (QQ平台)   │  │  (Discord)   │  │   (待实现)    │     │
│  └────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 路径 | 说明 |
|------|------|------|
| PlatformAdapter | `src/infrastructure/platform/base.py` | 平台适配器抽象基类 |
| PlatformAdapterFactory | `src/infrastructure/platform/factory.py` | 适配器工厂，管理注册和创建 |
| UnifiedMessage | `src/domain/value_objects/unified_message.py` | 统一消息格式 |
| PlatformCapabilities | `src/domain/value_objects/platform_capabilities.py` | 平台能力声明 |

---

## 快速开始

接入新平台只需 3 步：

### 步骤 1：创建适配器文件

```bash
# 在 adapters 目录下创建新文件
touch src/infrastructure/platform/adapters/your_platform_adapter.py
```

### 步骤 2：实现适配器类

```python
from ..base import PlatformAdapter
from ....domain.value_objects.platform_capabilities import PlatformCapabilities

class YourPlatformAdapter(PlatformAdapter):
    def _init_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="your_platform",
            supports_message_history=True,
            # ... 其他能力
        )
    
    # 实现所有抽象方法...
```

### 步骤 3：注册适配器

在 `factory.py` 的 `_register_adapters()` 函数中添加：

```python
try:
    from .adapters.your_platform_adapter import YourPlatformAdapter
    PlatformAdapterFactory.register("your_platform", YourPlatformAdapter)
except ImportError:
    pass
```

---

## 详细步骤

### 1. 定义平台能力

首先，明确你的平台支持哪些功能。以 `Discord` 为例：

```python
from ....domain.value_objects.platform_capabilities import PlatformCapabilities

DISCORD_CAPABILITIES = PlatformCapabilities(
    platform_name="discord",                 # 平台标识符
    platform_version="api_v10",              # 平台版本
    supports_message_history=True,           # 是否支持历史消息获取
    max_message_history_days=30,             # 历史消息最大天数
    max_message_count=10000,                 # 最大消息数量
    supports_group_list=True,                # 是否支持获取群列表
    supports_group_info=True,                # 是否支持获取群信息
    supports_member_list=True,               # 是否支持获取成员列表
    supports_text_message=True,              # 是否支持文本消息
    supports_image_message=True,             # 是否支持图片消息
    supports_file_message=True,              # 是否支持文件消息
    supports_reply_message=True,             # 是否支持回复消息
    max_text_length=2000,                    # 最大文本长度
    max_image_size_mb=8.0,                   # 最大图片大小
    supports_edit=True,                      # 是否支持编辑
    supports_user_avatar=True,               # 是否支持用户头像
    supports_group_avatar=True,              # 是否支持群头像
    avatar_sizes=(16, 32, 64, 128, 256, 512, 1024, 2048, 4096), # 支持的头像尺寸
)
```

### 2. 实现消息获取

消息获取是分析的核心。你需要实现 `fetch_messages` 方法。

**以 Discord 为例：**

```python
    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """
        获取 Discord 频道消息历史
        """
        if not discord:
            logger.error("未安装 py-cord 库，无法使用 Discord 适配器")
            return []

        try:
            channel_id = int(group_id)
            channel = self._discord_client.get_channel(channel_id)
            # ... 获取 channel 逻辑 ...

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []
            
            # 构建 history 参数
            history_kwargs = {"limit": max_count, "after": start_time}
            if before_id:
                # 处理分页
                try:
                    history_kwargs["before"] = discord.Object(id=int(before_id))
                except ValueError:
                    pass

            # 获取消息
            async for msg in channel.history(**history_kwargs):
                # 过滤机器人自己的消息（如果配置了 ID）
                if self.bot_user_id and str(msg.author.id) == self.bot_user_id:
                    continue

                unified = self._convert_message(msg, group_id)
                if unified:
                    messages.append(unified)

            # 按时间升序排序
            messages.sort(key=lambda m: m.timestamp)
            return messages

        except Exception as e:
            logger.error(f"获取 Discord 消息失败: {e}", exc_info=True)
            return []
```

### 3. 实现消息转换

将平台原生消息转换为 `UnifiedMessage`。这是解耦的关键。

**以 Discord 为例：**

```python
    def _convert_message(self, raw_msg: Any, group_id: str) -> Optional[UnifiedMessage]:
        """
        将 Discord 消息转换为统一格式
        """
        try:
            contents = []

            # 1. 文本内容
            if raw_msg.content:
                contents.append(
                    MessageContent(type=MessageContentType.TEXT, text=raw_msg.content)
                )

            # 2. 附件处理 (图片/视频/文件)
            for attachment in raw_msg.attachments:
                content_type = attachment.content_type or ""
                if content_type.startswith("image/"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE, url=attachment.url
                        )
                    )
                # ... 处理其他类型 ...

            # 3. 嵌入内容 (Embeds)
            for embed in raw_msg.embeds:
                if embed.image:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE, url=embed.image.url
                        )
                    )
                # ...

            # 4. 贴纸 (Stickers)
            if raw_msg.stickers:
                for sticker in raw_msg.stickers:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,  # 贴纸视为图片
                            url=sticker.url,
                            # ...
                        )
                    )

            # 构造 UnifiedMessage
            return UnifiedMessage(
                message_id=str(raw_msg.id),
                sender_id=str(raw_msg.author.id),
                sender_name=raw_msg.author.name,  # 用户名
                sender_card=getattr(raw_msg.author, "nick", None) or getattr(raw_msg.author, "global_name", None),  # 优先显示服务器昵称
                group_id=group_id,
                text_content=raw_msg.content, # 用于 LLM 分析的纯文本
                contents=tuple(contents),
                timestamp=int(raw_msg.created_at.timestamp()),
                platform="discord",
                reply_to_id=str(raw_msg.reference.message_id) if raw_msg.reference else None,
            )
        except Exception as e:
            logger.error(f"转换 Discord 消息失败: {e}")
            return None
```

### 4. 实现原生格式转换

为了保持与现有分析器（如 `MessageHandler`）的向后兼容性，需要实现 `convert_to_raw_format`。

```python
    def convert_to_raw_format(self, messages: List[UnifiedMessage]) -> List[dict]:
        """
        将统一消息格式转换为 OneBot 兼容格式 (用于兼容 MessageHandler)
        """
        raw_messages = []
        for msg in messages:
            # 构造 OneBot 风格的消息字典
            raw_msg = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card,
                },
                "message": [],
            }

            # 构造消息链
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    raw_msg["message"].append(
                        {"type": "text", "data": {"text": content.text}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    raw_msg["message"].append(
                        {
                            "type": "image",
                            "data": {"url": content.url, "file": content.url},
                        }
                    )
                # ... 其他类型 ...

            raw_messages.append(raw_msg)

        return raw_messages
```

### 5. 实现消息发送

实现发送文本、图片等功能。

**以 Discord 为例：**

```python
    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片到 Discord 频道"""
        # ... 获取 channel ...

        try:
            # 处理本地文件或 URL
            file_to_send = None
            if image_path.startswith(("http://", "https://")):
                # URL 方式，需要下载图片后作为文件发送
                # 因为 Discord 无法访问内部/本地 URL
                import aiohttp
                from io import BytesIO

                async with aiohttp.ClientSession() as session:
                    async with session.get(image_path) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            # ...
                            file_to_send = discord.File(BytesIO(image_data), filename="report.png")
            else:
                # 本地文件
                file_to_send = discord.File(image_path)

            if file_to_send:
                await channel.send(content=caption if caption else None, file=file_to_send)
            return True

        except Exception as e:
            logger.error(f"Discord 发送图片失败: {e}")
            return False
```

### 6. 实现群组和成员信息获取

实现 `get_group_info`、`get_group_list`、`get_member_list` 等方法，以便插件可以自动发现群组并获取成员信息。

**以 Discord 为例：**

```python
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取 Discord 频道信息"""
        # ... 获取 channel ...
        
        # 尝试获取 Guild 信息
        guild = getattr(channel, "guild", None)
        group_name = getattr(channel, "name", str(channel.id))
        
        if guild:
            member_count = guild.member_count
            owner_id = str(guild.owner_id)
        else:
            # 私信
            member_count = len(getattr(channel, "recipients", [])) + 1
            owner_id = None

        return UnifiedGroup(
            group_id=str(channel.id),
            group_name=group_name,
            member_count=member_count,
            owner_id=owner_id,
            create_time=int(channel.created_at.timestamp()),
            platform="discord",
        )
```

### 7. 实现头像获取

实现 `get_user_avatar_url` 等方法，用于生成报告时的头像显示。

**以 Discord 为例：**

```python
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 用户头像 URL"""
        # ... 获取 user ...
        
        if user:
            # 调整 size 到最接近的 2 的幂次方 (Discord 要求)
            allowed_sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
            target_size = min(allowed_sizes, key=lambda x: abs(x - size))

            # display_avatar 自动处理默认头像
            return user.display_avatar.with_size(target_size).url
        return None
```

---

## 接口说明

### PlatformAdapter 必须实现的方法

| 方法 | 说明 | 返回类型 |
|------|------|----------|
| `_init_capabilities()` | 初始化平台能力 | `PlatformCapabilities` |
| `fetch_messages()` | 获取消息历史 | `List[UnifiedMessage]` |
| `convert_to_raw_format()` | 转换为原生格式 | `List[dict]` |
| `send_text()` | 发送文本 | `bool` |
| `send_image()` | 发送图片 | `bool` |
| `send_file()` | 发送文件 | `bool` |
| `get_group_info()` | 获取群组信息 | `Optional[UnifiedGroup]` |
| `get_group_list()` | 获取群组列表 | `List[str]` |
| `get_member_list()` | 获取成员列表 | `List[UnifiedMember]` |
| `get_member_info()` | 获取成员信息 | `Optional[UnifiedMember]` |
| `get_user_avatar_url()` | 获取头像 URL | `Optional[str]` |
| `get_user_avatar_data()` | 获取头像 Base64 | `Optional[str]` |
| `get_group_avatar_url()` | 获取群头像 URL | `Optional[str]` |
| `batch_get_avatar_urls()` | 批量获取头像 | `Dict[str, Optional[str]]` |

### UnifiedMessage 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `message_id` | `str` | 消息唯一 ID |
| `sender_id` | `str` | 发送者 ID |
| `sender_name` | `str` | 发送者昵称 |
| `sender_card` | `Optional[str]` | 发送者群名片 |
| `group_id` | `str` | 群组 ID |
| `text_content` | `str` | 纯文本内容 |
| `contents` | `Tuple[MessageContent, ...]` | 消息内容列表 |
| `timestamp` | `int` | Unix 时间戳 |
| `platform` | `str` | 平台标识 |
| `reply_to_id` | `Optional[str]` | 回复的消息 ID |

### MessageContentType 枚举

| 类型 | 说明 |
|------|------|
| `TEXT` | 文本 |
| `IMAGE` | 图片 |
| `AT` | @某人 |
| `EMOJI` | 表情 |
| `REPLY` | 回复 |
| `FORWARD` | 转发 |
| `VOICE` | 语音 |
| `VIDEO` | 视频 |
| `FILE` | 文件 |
| `UNKNOWN` | 未知类型 |

---

## 最佳实践

### 1. 不要硬编码平台特定逻辑

❌ **错误做法**：
```python
# 在应用层硬编码平台判断
if platform == "qq":
    messages = fetch_qq_messages()
elif platform == "discord":
    messages = fetch_discord_messages()
```

✅ **正确做法**：
```python
# 使用适配器模式
adapter = PlatformAdapterFactory.create(platform_name, bot_instance, config)
messages = await adapter.fetch_messages(group_id, days, max_count)
```

### 2. 使用中文注释

所有代码注释必须使用中文：

```python
def fetch_messages(self, group_id: str, days: int = 1) -> List[UnifiedMessage]:
    """
    获取群组消息历史
    
    参数：
        group_id: 群组 ID
        days: 获取多少天内的消息
        
    返回：
        UnifiedMessage 列表
    """
```

### 3. 优雅处理异常

```python
async def fetch_messages(self, ...) -> List[UnifiedMessage]:
    try:
        # 正常逻辑
        return messages
    except SpecificError as e:
        logger.warning(f"获取消息失败: {e}")
        return []
    except Exception:
        # 不要让异常传播到上层
        return []
```

### 4. 过滤机器人自己的消息

```python
# 在 __init__ 中保存机器人 ID
self.bot_user_id = config.get("bot_user_id", "")

# 在 fetch_messages 中过滤
if str(msg.author.id) == self.bot_user_id:
    continue
```

### 5. 声明正确的平台能力

如果平台不支持某功能，在 `PlatformCapabilities` 中正确声明：

```python
PlatformCapabilities(
    supports_message_history=False,  # 不支持历史消息获取
    max_message_history_days=0,      # 无法获取历史消息
)
```

---

## 示例代码

完整的适配器示例请参考：

- **OneBot 适配器**（QQ）：`src/infrastructure/platform/adapters/onebot_adapter.py`
- **Discord 适配器**（骨架）：`src/infrastructure/platform/adapters/discord_adapter.py`

---

## 测试指南

### 1. 单元测试

为适配器编写单元测试：

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
    
    @pytest.mark.asyncio
    async def test_fetch_messages(self):
        adapter = YourPlatformAdapter(mock_bot, {})
        messages = await adapter.fetch_messages("group_123", days=1)
        assert isinstance(messages, list)
```

### 2. Docker 容器内验证

在 Docker 容器内验证适配器注册：

```bash
docker exec astrbot python -c "
from data.plugins.astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform import PlatformAdapterFactory
print('支持的平台:', PlatformAdapterFactory.get_supported_platforms())
print('Discord 支持:', PlatformAdapterFactory.is_supported('discord'))
"
```

### 3. 集成测试

确保适配器与 `AnalysisOrchestrator` 正确集成：

```python
from src.application.analysis_orchestrator import AnalysisOrchestrator

orchestrator = AnalysisOrchestrator.create_for_platform(
    platform_name="your_platform",
    bot_instance=bot,
    config={},
)
assert orchestrator is not None
assert orchestrator.can_analyze() == True
```

---

## 常见问题

### Q: 如何处理平台特定的消息类型？

使用 `MessageContentType.UNKNOWN` 并在 `raw_data` 中保存原始数据：

```python
contents.append(MessageContent(
    type=MessageContentType.UNKNOWN,
    raw_data={"platform_specific_type": "sticker", "data": sticker_data}
))
```

### Q: 如何支持分页获取消息？

使用 `before_id` 参数：

```python
async def fetch_messages(self, ..., before_id: Optional[str] = None):
    if before_id:
        # 从此消息 ID 之前开始获取
        messages = await api.get_history(before=before_id, limit=max_count)
    else:
        messages = await api.get_history(limit=max_count)
```

### Q: 如何处理不支持的功能？

在能力声明中标记为不支持，并在方法中返回空/默认值：

```python
# 能力声明
PlatformCapabilities(supports_member_list=False)

# 方法实现
async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
    return []  # 平台不支持，返回空列表
```

---

## 贡献检查清单

在提交 PR 之前，请确保：

- [ ] 适配器继承自 `PlatformAdapter`
- [ ] 实现了所有抽象方法
- [ ] 在工厂中注册了适配器
- [ ] 所有注释使用中文
- [ ] 编写了单元测试
- [ ] 在 Docker 容器内验证通过
- [ ] 更新了相关文档

---

*最后更新：2026-02-08*