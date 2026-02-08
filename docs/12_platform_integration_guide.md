# 平台接入开发指南

本文档说明如何为 QQ 群聊日报分析插件接入新的消息平台。

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
            supports_history_fetch=True,
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

首先，明确你的平台支持哪些功能：

```python
from ....domain.value_objects.platform_capabilities import PlatformCapabilities

YOUR_PLATFORM_CAPABILITIES = PlatformCapabilities(
    platform_name="your_platform",           # 平台标识符
    supports_history_fetch=True,             # 是否支持历史消息获取
    supports_image_message=True,             # 是否支持图片消息
    supports_file_message=True,              # 是否支持文件消息
    supports_text_message=True,              # 是否支持文本消息
    max_history_days=7,                      # 历史消息最大天数
    max_messages_per_fetch=100,              # 单次获取最大消息数
    supports_avatar=True,                    # 是否支持头像获取
    supports_group_info=True,                # 是否支持群组信息
    supports_member_list=True,               # 是否支持成员列表
)
```

### 2. 实现消息获取

```python
async def fetch_messages(
    self,
    group_id: str,
    days: int = 1,
    max_count: int = 1000,
    before_id: Optional[str] = None,
) -> List[UnifiedMessage]:
    """
    获取群组消息历史
    
    重要：
    1. 过滤掉机器人自己的消息
    2. 只返回指定时间范围内的消息
    3. 按时间升序排序
    """
    # 你的实现...
```

### 3. 实现消息转换

将平台原生消息转换为 `UnifiedMessage`：

```python
def _convert_message(self, raw_msg: Any, group_id: str) -> Optional[UnifiedMessage]:
    """将平台原生消息转换为统一格式"""
    contents = []
    
    # 处理文本
    if raw_msg.text:
        contents.append(MessageContent(
            type=MessageContentType.TEXT,
            text=raw_msg.text
        ))
    
    # 处理图片
    for img in raw_msg.images:
        contents.append(MessageContent(
            type=MessageContentType.IMAGE,
            url=img.url
        ))
    
    return UnifiedMessage(
        message_id=str(raw_msg.id),
        sender_id=str(raw_msg.author.id),
        sender_name=raw_msg.author.name,
        group_id=group_id,
        text_content=raw_msg.text or "",
        contents=tuple(contents),
        timestamp=int(raw_msg.created_at.timestamp()),
        platform="your_platform",
    )
```

### 4. 实现原生格式转换

用于向后兼容现有分析器：

```python
def convert_to_raw_format(self, messages: List[UnifiedMessage]) -> List[dict]:
    """将统一消息转换回平台原生格式"""
    return [
        {
            "id": msg.message_id,
            "author": {"id": msg.sender_id, "name": msg.sender_name},
            "content": msg.text_content,
            "timestamp": msg.timestamp,
            # ... 平台特定字段
        }
        for msg in messages
    ]
```

### 5. 实现消息发送

```python
async def send_text(self, group_id: str, text: str, reply_to: Optional[str] = None) -> bool:
    """发送文本消息"""
    try:
        # 调用平台 API 发送消息
        await self.bot.send_message(group_id, text)
        return True
    except Exception:
        return False

async def send_image(self, group_id: str, image_path: str, caption: str = "") -> bool:
    """发送图片消息"""
    # 你的实现...

async def send_file(self, group_id: str, file_path: str, filename: Optional[str] = None) -> bool:
    """发送文件"""
    # 你的实现...
```

### 6. 实现群组信息获取

```python
async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
    """获取群组信息"""
    # 你的实现...

async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
    """获取群组成员列表"""
    # 你的实现...
```

### 7. 实现头像获取

```python
async def get_user_avatar_url(self, user_id: str, size: int = 100) -> Optional[str]:
    """获取用户头像 URL"""
    # 返回头像 URL 或 None

async def batch_get_avatar_urls(self, user_ids: List[str], size: int = 100) -> Dict[str, Optional[str]]:
    """批量获取用户头像 URL"""
    return {uid: await self.get_user_avatar_url(uid, size) for uid in user_ids}
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
    supports_history_fetch=False,  # 不支持历史消息获取
    max_history_days=0,            # 无法获取历史消息
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
        assert caps.supports_history_fetch == True
    
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
