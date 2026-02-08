# 平台集成指南

本指南详细说明了 `astrbot_plugin_qq_group_daily_analysis` 的多平台支持架构、如何添加新平台支持，以及当前的平台支持情况。

## 1. 架构概览

本插件采用 DDD (领域驱动设计) 风格的架构，将平台特定的逻辑与核心业务逻辑解耦。

### 核心组件

*   **PlatformAdapter (平台适配器)**: 定义了统一的接口，用于屏蔽不同平台的差异。所有平台适配器都必须继承自 `src/infrastructure/platform/base.py` 中的 `PlatformAdapter` 基类。
*   **UnifiedMessage (统一消息模型)**: 定义了平台无关的消息结构。适配器负责将平台原生消息转换为 `UnifiedMessage`。
*   **BotManager (Bot 管理器)**: 负责管理 Bot 实例和平台适配器，并根据平台类型自动创建对应的适配器。

### 数据流

1.  **消息获取**: `BotManager` 获取特定平台的 `PlatformAdapter` -> 调用 `fetch_messages` -> 适配器调用平台 API 获取消息 -> 适配器将消息转换为 `UnifiedMessage` 列表 -> 返回给业务层。
2.  **消息发送**: 业务层调用 `PlatformAdapter` 的 `send_text` / `send_image` 等方法 -> 适配器调用平台 API 发送消息。

## 2. 当前支持的平台

目前插件内置支持以下平台：

| 平台名称 | 适配器类 | 关键特性支持 | 备注 |
| :--- | :--- | :--- | :--- |
| **OneBot V11** | `OneBotAdapter` | ✅ 消息获取 (Api)<br>✅ 消息发送<br>✅ 群成员信息<br>✅ 头像获取 | 完美支持 (aiocqhttp, NapCat, go-cqhttp 等) |
| **Discord** | `DiscordAdapter` | ✅ 消息获取 (History)<br>✅ 消息发送<br>✅ 频道成员信息<br>✅ 头像获取 | 依赖 `py-cord` 或 `discord.py` |

> **注意**: 
> *   **QQ 官方 Bot (qq-bot-py)**: 由于官方 API 限制，**不支持**获取历史消息，因此无法使用本插件的分析功能。
> *   **Gewechat**: 尚未实现适配器，欢迎贡献。

## 3. 开发新平台适配器

若要支持新平台（例如 Telegram, Feishu 等），请按照以下步骤操作：

### 步骤 1: 创建适配器类

在 `src/infrastructure/platform/adapters/` 目录下创建一个新的 Python 文件（例如 `telegram_adapter.py`），并定义一个继承自 `PlatformAdapter` 的类。

```python
from ..base import PlatformAdapter
from ....domain.value_objects.platform_capabilities import PlatformCapabilities

class TelegramAdapter(PlatformAdapter):
    
    def _init_capabilities(self) -> PlatformCapabilities:
        # 定义该平台的能力
        return PlatformCapabilities(
            platform_name="telegram",
            can_fetch_history=True,
            can_analyze=True,
            # ... 其他能力配置
        )

    # 实现抽象方法...
    async def fetch_messages(self, group_id, days, max_count, before_id=None):
        # 1. 调用平台 API 获取消息
        # 2. 将消息转换为 UnifiedMessage 列表
        pass
        
    # ... 实现其他必要接口 (send_text, get_group_info 等)
```

### 步骤 2: 实现消息转换

核心是实现 `_convert_message` 方法，将平台原生的消息格式转换为 `UnifiedMessage`。

你需要处理：
*   **基本信息**: 消息 ID, 发送者 ID, 时间戳等。
*   **消息内容**: 将文本、图片、At、回复等转换为 `MessageContent` 对象列表。

### 步骤 3: 注册适配器

在 `src/infrastructure/platform/factory.py` 中注册你的新适配器：

```python
# src/infrastructure/platform/factory.py

def _register_adapters():
    # ... 其他注册 ...
    
    try:
        from .adapters.telegram_adapter import TelegramAdapter
        PlatformAdapterFactory.register("telegram", TelegramAdapter)
    except ImportError:
        pass
```

### 步骤 4: 自动发现 (可选)

`BotManager` 会尝试自动检测平台类型。你可以在 `src/core/bot_manager.py` 的 `_detect_platform_name` 方法中添加特征检测逻辑，或者确保你的 Bot 实例的类名包含平台名称（例如 `TelegramBot`）。

## 4. 常见问题与调试

### Q: 为什么我的 Bot 无法获取历史消息？
A: 请检查该平台的 API 是否支持获取历史消息。某些平台（如 QQ 官方 Bot）不支持此功能。

### Q: 如何调试适配器？
A: 在 `src/core/config.py` 中开启 `debug_mode`，查看详细的日志输出。适配器的所有关键操作都会有日志记录。

### Q: 适配器如何获取配置？
A: 适配器初始化时会传入 `config` 字典。你可以在 `__init__` 方法中获取所需的配置项。

## 5. 最佳实践

*   **解耦**: 尽量不要在业务逻辑中引入平台特定的代码，使用 `UnifiedMessage` 进行交互。
*   **容错**: 平台 API 调用可能会失败，请做好异常处理，避免整个插件崩溃。
*   **懒加载**: 在 `_register_adapters` 中使用 `try-except ImportError` 包裹导入语句，确保即使缺少某些依赖库，插件的其他部分也能正常工作。
