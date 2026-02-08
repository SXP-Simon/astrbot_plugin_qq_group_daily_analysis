# 09. DDD + 跨平台重构完整方案 (DDD & Cross-Platform Refactoring Complete Guide)

> **文档日期**: 2026-02-08
> **版本**: v1.0
> **整合文档**: 07_ddd_refactoring_analysis.md + 08_cross_platform_decoupling_analysis.md
> **目的**: 提供完整的 DDD 重构方案，同时解决跨平台解耦问题

---

## 1. 执行摘要

### 1.1 问题分析

本插件存在两个核心问题需要同时解决：

| 问题 | 现状 | 影响 |
|------|------|------|
| **平台耦合** | 34 处 QQ 硬编码 | 完全无法在其他平台使用 |
| **架构分层混乱** | 业务逻辑与基础设施混合 | 测试困难，维护成本高 |

### 1.2 解决方案概述

采用 **DDD 分层架构 + 平台适配器模式**：

```
┌─────────────────────────────────────────────────────────────────┐
│  Interface Layer (main.py)                                      │
│  - 使用 AstrMessageEvent 基类，不再限制 QQ 平台                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Application Layer                                              │
│  - AnalysisOrchestrator: 分析流程编排                           │
│  - SchedulingService: 定时任务管理                              │
│  - ReportingService: 报告生成与分发                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Domain Layer (平台无关)                                         │
│  - Entities: AnalysisTask, GroupAnalysisResult                  │
│  - Value Objects: UnifiedMessage, PlatformCapabilities          │
│  - Domain Services: TopicAnalyzer, StatisticsCalculator, etc.   │
│  - Repository Interfaces: IMessageRepository, IMessageSender    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Infrastructure Layer                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Platform Adapters (实现 Repository Interfaces)          │   │
│  │  - OneBotAdapter (QQ)                                    │   │
│  │  - TelegramAdapter                                       │   │
│  │  - DiscordAdapter                                        │   │
│  │  - SlackAdapter                                          │   │
│  │  - LarkAdapter (飞书)                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│  - LLMClient, ConfigManager, CircuitBreaker, etc.              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 预期收益

| 收益 | 量化 |
|------|------|
| 跨平台支持 | 从 1 个平台扩展到 5+ 个平台 |
| 可测试性 | 单元测试覆盖率可达 80%+ |
| 可维护性 | 新增平台只需 1 天工作量 |
| 可扩展性 | 新增分析器只需实现接口 |

---

## 2. 限界上下文 (Bounded Contexts)

### 2.1 上下文划分

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      群聊日常分析插件 (Plugin)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  调度上下文  │  │  分析上下文  │  │  报告上下文  │  │  平台上下文  │    │
│  │ (Scheduling)│  │ (Analysis)  │  │ (Reporting) │  │ (Platform)  │    │
│  │             │  │             │  │             │  │   [核心]    │    │
│  │ - 定时任务  │  │ - 话题分析  │  │ - 报告生成  │  │ - 消息获取  │    │
│  │ - 并发控制  │  │ - 用户画像  │  │ - 格式转换  │  │ - 消息发送  │    │
│  │ - 任务编排  │  │ - 金句提取  │  │ - 重试机制  │  │ - 群组信息  │    │
│  │             │  │ - 统计计算  │  │             │  │ - 平台能力  │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                                    │                                    │
│  ┌─────────────────────────────────┴─────────────────────────────────┐  │
│  │                      共享内核 (Shared Kernel)                      │  │
│  │  - ConfigManager: 配置管理                                         │  │
│  │  - TraceContext: 链路追踪                                          │  │
│  │  - CircuitBreaker, RateLimiter: 弹性组件                           │  │
│  │  - UnifiedMessage: 统一消息模型 [跨平台核心]                        │  │
│  │  - PlatformCapabilities: 平台能力描述 [跨平台核心]                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 上下文职责

| 上下文 | 职责 | 关键组件 |
|--------|------|----------|
| **调度** | 定时任务、并发控制、任务编排 | SchedulingService, AutoScheduler |
| **分析** | 话题分析、用户画像、金句提取、统计 | TopicAnalyzer, UserTitleAnalyzer, StatisticsCalculator |
| **报告** | 报告生成、格式转换、发送、重试 | ReportGenerator, ReportDispatcher, RetryManager |
| **平台** | 消息获取、消息发送、群组信息 | PlatformAdapter, IMessageRepository, IMessageSender |

---

## 3. 领域模型设计

### 3.1 统一消息模型 (UnifiedMessage)

**这是跨平台的核心抽象**，所有平台的消息都会被转换为此格式：

```python
# src/domain/value_objects/unified_message.py
from dataclasses import dataclass
from typing import Optional, Any
from enum import Enum

class MessageContentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    EMOJI = "emoji"
    REPLY = "reply"
    FORWARD = "forward"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class MessageContent:
    """消息内容值对象"""
    type: MessageContentType
    text: str = ""
    url: str = ""
    emoji_id: str = ""
    raw_data: Any = None  # 保留原始数据用于调试

@dataclass(frozen=True)
class UnifiedMessage:
    """
    统一消息格式 - 跨平台核心值对象
    
    设计原则：
    1. 只保留分析需要的字段
    2. 使用平台无关的类型
    3. 不可变 (frozen=True)
    """
    message_id: str
    sender_id: str
    sender_name: str
    group_id: str
    text_content: str  # 纯文本，用于 LLM 分析
    contents: tuple[MessageContent, ...]  # 完整消息链
    timestamp: int
    platform: str  # 来源平台标识
    reply_to: Optional[str] = None
    
    def has_text(self) -> bool:
        return bool(self.text_content.strip())
    
    def get_emoji_count(self) -> int:
        return sum(1 for c in self.contents if c.type == MessageContentType.EMOJI)
```

### 3.2 平台能力描述 (PlatformCapabilities)

```python
# src/domain/value_objects/platform_capabilities.py
from dataclasses import dataclass

@dataclass(frozen=True)
class PlatformCapabilities:
    """
    平台能力描述 - 用于运行时决策
    
    每个平台适配器必须声明自己的能力，
    应用层根据能力决定是否可以执行某些操作。
    """
    platform_name: str
    
    # 消息获取能力
    supports_message_history: bool = False
    max_message_history_days: int = 0
    max_message_count: int = 0
    
    # 群组信息能力
    supports_group_list: bool = False
    supports_group_info: bool = False
    supports_member_list: bool = False
    
    # 消息发送能力
    supports_text_message: bool = True
    supports_image_message: bool = True
    supports_file_message: bool = False
    supports_forward_message: bool = False
    
    def can_analyze(self) -> bool:
        """是否支持群聊分析"""
        return self.supports_message_history and self.max_message_history_days > 0


# 预定义平台能力
ONEBOT_CAPABILITIES = PlatformCapabilities(
    platform_name="onebot",
    supports_message_history=True, max_message_history_days=7, max_message_count=10000,
    supports_group_list=True, supports_group_info=True, supports_member_list=True,
    supports_text_message=True, supports_image_message=True,
    supports_file_message=True, supports_forward_message=True,
)

TELEGRAM_CAPABILITIES = PlatformCapabilities(
    platform_name="telegram",
    supports_message_history=True, max_message_history_days=30, max_message_count=10000,
    supports_group_list=True, supports_group_info=True, supports_member_list=True,
    supports_text_message=True, supports_image_message=True, supports_file_message=True,
)

DISCORD_CAPABILITIES = PlatformCapabilities(
    platform_name="discord",
    supports_message_history=True, max_message_history_days=30, max_message_count=10000,
    supports_group_list=True, supports_group_info=True, supports_member_list=True,
    supports_text_message=True, supports_image_message=True, supports_file_message=True,
)
```

### 3.3 仓储接口

```python
# src/domain/repositories/message_repository.py
from abc import ABC, abstractmethod
from typing import List
from ..value_objects.unified_message import UnifiedMessage
from ..value_objects.platform_capabilities import PlatformCapabilities

class IMessageRepository(ABC):
    """消息仓储接口 - 每个平台适配器必须实现"""
    
    @abstractmethod
    async def fetch_messages(
        self, group_id: str, days: int, max_count: int = 1000
    ) -> List[UnifiedMessage]:
        """获取群组历史消息，返回统一格式"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力描述"""
        pass


# src/domain/repositories/message_sender.py
class IMessageSender(ABC):
    """消息发送接口"""
    
    @abstractmethod
    async def send_text(self, group_id: str, text: str) -> bool:
        pass
    
    @abstractmethod
    async def send_image(self, group_id: str, image_url: str, caption: str = "") -> bool:
        pass
    
    @abstractmethod
    async def send_file(self, group_id: str, file_path: str) -> bool:
        pass


# src/domain/repositories/group_info_repository.py
@dataclass
class UnifiedGroup:
    group_id: str
    group_name: str
    member_count: int
    owner_id: Optional[str] = None

class IGroupInfoRepository(ABC):
    """群组信息仓储接口"""
    
    @abstractmethod
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        pass
    
    @abstractmethod
    async def get_group_list(self) -> List[str]:
        pass
```

### 3.4 实体设计

```python
# src/domain/entities/analysis_task.py
from dataclasses import dataclass, field
from enum import Enum
import time, uuid

class TaskStatus(Enum):
    PENDING = "pending"
    CHECKING_PLATFORM = "checking_platform"
    FETCHING_MESSAGES = "fetching_messages"
    ANALYZING = "analyzing"
    GENERATING_REPORT = "generating_report"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED_PLATFORM = "unsupported_platform"

@dataclass
class AnalysisTask:
    """分析任务实体 - 聚合根"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    group_id: str = ""
    platform_name: str = ""
    trace_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    is_manual: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    
    def start(self, capabilities: PlatformCapabilities) -> bool:
        """开始任务，验证平台能力"""
        if not capabilities.can_analyze():
            self.status = TaskStatus.UNSUPPORTED_PLATFORM
            self.error_message = f"Platform {capabilities.platform_name} does not support analysis"
            return False
        self.status = TaskStatus.FETCHING_MESSAGES
        self.started_at = time.time()
        return True
    
    def complete(self, result_id: str):
        self.status = TaskStatus.COMPLETED
        self.result_id = result_id
        self.completed_at = time.time()
    
    def fail(self, error: str):
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = time.time()
```

---

## 4. 平台适配器设计

### 4.1 适配器架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     PlatformAdapter (Base)                      │
│  - message_repository: IMessageRepository                       │
│  - message_sender: IMessageSender                               │
│  - group_info_repository: IGroupInfoRepository                  │
│  - capabilities: PlatformCapabilities                           │
└─────────────────────────────────────────────────────────────────┘
                              △
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────┴───────┐  ┌─────────┴─────────┐  ┌───────┴───────┐
│ OneBotAdapter │  │ TelegramAdapter   │  │ DiscordAdapter │
│               │  │                   │  │               │
│ - call_action │  │ - python-telegram │  │ - pycord      │
│ - OneBot v11  │  │   -bot API        │  │ - Discord API │
└───────────────┘  └───────────────────┘  └───────────────┘
```

### 4.2 OneBot 适配器实现

```python
# src/infrastructure/platform/adapters/onebot_adapter.py
from datetime import datetime, timedelta
from typing import List, Optional, Any
from astrbot.api import logger

from ....domain.repositories.message_repository import IMessageRepository
from ....domain.value_objects.unified_message import UnifiedMessage, MessageContent, MessageContentType
from ....domain.value_objects.platform_capabilities import PlatformCapabilities, ONEBOT_CAPABILITIES

class OneBotMessageRepository(IMessageRepository):
    """OneBot v11 消息仓储实现"""
    
    def __init__(self, bot_instance: Any, bot_self_ids: List[str] = None):
        self.bot = bot_instance
        self.bot_self_ids = bot_self_ids or []
    
    async def fetch_messages(self, group_id: str, days: int, max_count: int = 1000) -> List[UnifiedMessage]:
        if not hasattr(self.bot, "call_action"):
            return []
        
        try:
            result = await self.bot.call_action(
                "get_group_msg_history",
                group_id=int(group_id),
                count=max_count,
            )
            
            if not result or "messages" not in result:
                return []
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            messages = []
            for raw_msg in result.get("messages", []):
                msg_time = datetime.fromtimestamp(raw_msg.get("time", 0))
                if not (start_time <= msg_time <= end_time):
                    continue
                
                sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                if sender_id in self.bot_self_ids:
                    continue
                
                unified = self._convert_message(raw_msg, group_id)
                if unified:
                    messages.append(unified)
            
            return messages
            
        except Exception as e:
            if "retcode=1200" in str(e):
                logger.warning(f"Bot not in group {group_id}")
            else:
                logger.error(f"OneBot fetch_messages failed: {e}")
            return []
    
    def _convert_message(self, raw_msg: dict, group_id: str) -> Optional[UnifiedMessage]:
        """将 OneBot 消息转换为统一格式"""
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])
            
            contents = []
            text_parts = []
            
            for seg in message_chain:
                seg_type = seg.get("type", "")
                seg_data = seg.get("data", {})
                
                if seg_type == "text":
                    text = seg_data.get("text", "")
                    text_parts.append(text)
                    contents.append(MessageContent(type=MessageContentType.TEXT, text=text))
                elif seg_type == "image":
                    contents.append(MessageContent(type=MessageContentType.IMAGE, url=seg_data.get("url", "")))
                elif seg_type in ("face", "mface", "bface", "sface"):
                    contents.append(MessageContent(type=MessageContentType.EMOJI, emoji_id=str(seg_data.get("id", ""))))
                else:
                    contents.append(MessageContent(type=MessageContentType.UNKNOWN, raw_data=seg))
            
            return UnifiedMessage(
                message_id=str(raw_msg.get("message_id", "")),
                sender_id=str(sender.get("user_id", "")),
                sender_name=sender.get("nickname", "") or sender.get("card", ""),
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=raw_msg.get("time", 0),
                platform="onebot",
            )
        except Exception as e:
            logger.warning(f"Failed to convert message: {e}")
            return None
    
    def get_capabilities(self) -> PlatformCapabilities:
        return ONEBOT_CAPABILITIES
```

### 4.3 适配器工厂

```python
# src/infrastructure/platform/factory.py
from typing import Optional, Any

class PlatformAdapterFactory:
    """平台适配器工厂"""
    
    _adapters = {
        "aiocqhttp": OneBotAdapter,
        # "telegram": TelegramAdapter,
        # "discord": DiscordAdapter,
    }
    
    @classmethod
    def create(cls, platform_name: str, bot_instance: Any, config: dict = None) -> Optional[PlatformAdapter]:
        adapter_class = cls._adapters.get(platform_name)
        if adapter_class is None:
            return None
        return adapter_class(bot_instance, config)
    
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        return list(cls._adapters.keys())
    
    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        return platform_name in cls._adapters
```

---

## 5. 应用层设计

### 5.1 分析编排器

```python
# src/application/analysis_orchestrator.py
from typing import Optional
import asyncio
from astrbot.api import logger

from ..domain.entities.analysis_task import AnalysisTask, TaskStatus
from ..domain.entities.analysis_result import GroupAnalysisResult
from ..domain.repositories.message_repository import IMessageRepository

class AnalysisOrchestrator:
    """
    分析流程编排器 - 应用层核心
    
    职责：协调消息获取、分析、报告生成
    特点：平台无关，通过仓储接口与基础设施层交互
    """
    
    def __init__(self, config_manager, llm_client, history_repository):
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.history_repository = history_repository
        
        # 领域服务
        self.statistics_calculator = StatisticsCalculator()
        self.topic_analyzer = TopicAnalyzer(llm_client)
        self.user_title_analyzer = UserTitleAnalyzer(llm_client)
        self.golden_quote_analyzer = GoldenQuoteAnalyzer(llm_client)
    
    async def execute(
        self,
        task: AnalysisTask,
        message_repository: IMessageRepository,
        unified_msg_origin: str = "",
    ) -> Optional[GroupAnalysisResult]:
        """执行分析任务"""
        try:
            # 1. 验证平台能力
            capabilities = message_repository.get_capabilities()
            if not task.start(capabilities):
                logger.warning(f"Platform {capabilities.platform_name} not supported")
                return None
            
            # 2. 获取消息
            days = self.config_manager.get_analysis_days()
            max_count = self.config_manager.get_max_messages()
            
            messages = await message_repository.fetch_messages(task.group_id, days, max_count)
            
            if not messages:
                task.fail("No messages found")
                return None
            
            min_threshold = self.config_manager.get_min_messages_threshold()
            if len(messages) < min_threshold:
                task.fail(f"Not enough messages: {len(messages)} < {min_threshold}")
                return None
            
            # 3. 执行分析
            task.advance_to(TaskStatus.ANALYZING)
            
            result = GroupAnalysisResult(
                group_id=task.group_id,
                trace_id=task.trace_id,
                message_count=len(messages),
            )
            
            # 统计计算 (本地)
            result.statistics = self.statistics_calculator.calculate(messages)
            
            # LLM 分析 (并行)
            topics, titles, quotes = await asyncio.gather(
                self.topic_analyzer.analyze(messages, unified_msg_origin),
                self.user_title_analyzer.analyze(messages, unified_msg_origin),
                self.golden_quote_analyzer.analyze(messages, unified_msg_origin),
                return_exceptions=True
            )
            
            # 处理结果
            if not isinstance(topics, Exception):
                result.topics = topics
            if not isinstance(titles, Exception):
                result.user_titles = titles
            if not isinstance(quotes, Exception):
                result.golden_quotes = quotes
            
            # 4. 保存并完成
            await self.history_repository.save(task.group_id, result)
            task.complete(result.id)
            
            return result
            
        except Exception as e:
            task.fail(str(e))
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return None
```

---

## 6. 目标目录结构

```
astrbot_plugin_group_daily_analysis/          # 去掉 QQ 前缀
├── main.py                                   # Interface Layer
├── src/
│   ├── application/                          # Application Layer
│   │   ├── __init__.py
│   │   ├── analysis_orchestrator.py          # 分析流程编排
│   │   ├── scheduling_service.py             # 定时任务服务
│   │   └── reporting_service.py              # 报告服务
│   │
│   ├── domain/                               # Domain Layer
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── analysis_task.py
│   │   │   └── analysis_result.py
│   │   ├── value_objects/
│   │   │   ├── unified_message.py            # 统一消息格式
│   │   │   ├── platform_capabilities.py      # 平台能力
│   │   │   ├── topic.py, user_title.py, etc.
│   │   ├── services/
│   │   │   ├── topic_analyzer.py
│   │   │   ├── statistics_calculator.py
│   │   │   └── report_generator.py
│   │   └── repositories/
│   │       ├── message_repository.py         # IMessageRepository
│   │       ├── message_sender.py             # IMessageSender
│   │       └── group_info_repository.py      # IGroupInfoRepository
│   │
│   ├── infrastructure/                       # Infrastructure Layer
│   │   ├── __init__.py
│   │   ├── platform/
│   │   │   ├── factory.py                    # 适配器工厂
│   │   │   ├── base.py                       # 适配器基类
│   │   │   └── adapters/
│   │   │       ├── onebot_adapter.py         # OneBot (QQ)
│   │   │       ├── telegram_adapter.py
│   │   │       ├── discord_adapter.py
│   │   │       └── slack_adapter.py
│   │   ├── persistence/
│   │   ├── llm/
│   │   ├── config/
│   │   └── resilience/
│   │
│   └── shared/
│       ├── exceptions.py
│       └── constants.py
│
├── tests/
└── docs/
```

---

## 7. 重构路线图

### 总览

| Phase | 内容 | 工作量 | 优先级 |
|-------|------|--------|--------|
| Phase 0 | 准备工作：目录结构、接口定义 | 1 天 | P0 |
| Phase 1 | 平台适配器：OneBot 实现 | 2-3 天 | P0 |
| Phase 2 | 领域层：值对象、实体、服务 | 2-3 天 | P0 |
| Phase 3 | 应用层：编排器、服务 | 2-3 天 | P0 |
| Phase 4 | 接口层：main.py 重构 | 1-2 天 | P0 |
| Phase 5 | 新平台：Telegram、Discord | 每平台 1 天 | P1 |
| Phase 6 | 测试与文档 | 2 天 | P1 |
| **总计** | | **12-16 天** | |

### Phase 0: 准备工作 (1 天)

```bash
# 创建目录结构
mkdir -p src/{application,domain/{entities,value_objects,services,repositories},infrastructure/{platform/adapters,persistence,llm,config,resilience},shared}
```

**任务清单**:
- [ ] 创建目录结构
- [ ] 定义 UnifiedMessage 值对象
- [ ] 定义 PlatformCapabilities 值对象
- [ ] 定义 IMessageRepository 接口
- [ ] 定义 IMessageSender 接口
- [ ] 定义 IGroupInfoRepository 接口
- [ ] 定义共享异常类

### Phase 1: 平台适配器 (2-3 天)

**任务清单**:
- [ ] 实现 OneBotMessageRepository
- [ ] 实现 OneBotMessageSender
- [ ] 实现 OneBotGroupInfoRepository
- [ ] 实现 OneBotAdapter (组合)
- [ ] 实现 PlatformAdapterFactory
- [ ] 编写单元测试

### Phase 2: 领域层重构 (2-3 天)

**任务清单**:
- [ ] 迁移 data_models.py 到 value_objects/
- [ ] 实现 AnalysisTask 实体
- [ ] 实现 GroupAnalysisResult 实体
- [ ] 重构分析器使用 UnifiedMessage
- [ ] 重构 StatisticsCalculator

### Phase 3: 应用层重构 (2-3 天)

**任务清单**:
- [ ] 实现 AnalysisOrchestrator
- [ ] 实现 SchedulingService
- [ ] 实现 ReportingService
- [ ] 重构 AutoScheduler

### Phase 4: 接口层重构 (1-2 天)

**任务清单**:
- [ ] 移除 AiocqhttpMessageEvent 导入
- [ ] 使用 AstrMessageEvent 基类
- [ ] 添加平台适配器选择逻辑
- [ ] 更新错误消息

### Phase 5: 新平台支持 (每平台 1 天)

**Telegram 适配器**:
- [ ] TelegramMessageRepository
- [ ] TelegramMessageSender
- [ ] TelegramAdapter

**Discord 适配器**:
- [ ] DiscordMessageRepository
- [ ] DiscordMessageSender
- [ ] DiscordAdapter

---

## 8. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 重构引入回归 | 中 | 高 | 渐进式迁移，保留原代码 |
| 平台 API 差异 | 高 | 中 | 统一消息格式 + 能力检查 |
| 消息历史受限 | 高 | 高 | 明确能力声明，提供降级 |
| 过度设计 | 中 | 中 | YAGNI 原则 |

---

## 9. 总结

### 9.1 核心设计决策

1. **UnifiedMessage** - 跨平台消息抽象，领域层只处理此格式
2. **PlatformCapabilities** - 平台能力声明，运行时决策
3. **IMessageRepository** - 消息获取抽象，每个平台实现
4. **PlatformAdapterFactory** - 适配器工厂，统一创建入口

### 9.2 收益总结

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| 平台支持 | 仅 QQ | QQ + Telegram + Discord + ... |
| 可测试性 | 困难 | 80%+ 覆盖率 |
| 新增平台 | N/A | 1 天 |
| 新增分析器 | 需要了解 QQ API | 只需实现接口 |

### 9.3 参考文档

- 07_ddd_refactoring_analysis.md - 原 DDD 分析
- 08_cross_platform_decoupling_analysis.md - 跨平台调研
- 06_review.md - 务实重构审查

---

## 附录: 平台能力对比

| 功能 | OneBot | Telegram | Discord | Slack | 飞书 |
|------|--------|----------|---------|-------|------|
| 消息历史 | ✅ 7天 | ✅ 30天 | ✅ 30天 | ✅ 30天 | ✅ 30天 |
| 群列表 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 发送图片 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 发送文件 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 转发消息 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 消息回应 | ❌ | ✅ | ✅ | ✅ | ✅ |
