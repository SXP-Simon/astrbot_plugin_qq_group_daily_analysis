# 07. DDD 重构分析报告 (Domain-Driven Design Refactoring Analysis)

> **分析日期**: 2026-02-08
> **分析范围**: 插件完整代码库 + 现有文档 (01-06)
> **分析目的**: 基于 DDD 范式，结合现有代码现状和 06_review.md 的务实建议，制定可落地的重构方案

---

## 1. 执行摘要 (Executive Summary)

### 1.1 当前状态评估

经过对代码库的深度分析，本插件已经完成了一次显著的重构（基于 06_review.md 的建议），当前架构状态：

| 维度 | 状态 | 说明 |
|------|------|------|
| **模块拆分** | ✅ 已完成 | AutoScheduler 已从 1000+ 行精简至 517 行 |
| **职责分离** | ✅ 已完成 | MessageSender、ReportDispatcher、BotManager 已独立 |
| **TraceID** | ✅ 已实现 | 使用 contextvars 实现零侵入链路追踪 |
| **熔断器** | ✅ 已实现 | CircuitBreaker + GlobalRateLimiter 已就绪 |
| **框架对齐** | ✅ 已完成 | 使用 Context.cron_manager + OnPlatformLoaded 钩子 |
| **DDD 分层** | ⚠️ 部分 | 有模块划分但未严格遵循 DDD 分层架构 |

### 1.2 核心结论

**本插件已完成 06_review.md 建议的务实重构，代码质量良好。**

进一步的 DDD 重构应聚焦于：
1. **领域边界明确化** - 定义清晰的限界上下文
2. **领域模型增强** - 引入轻量级 DDD 战术模式
3. **依赖方向规范** - 确保依赖指向领域层
4. **可测试性提升** - 通过接口抽象支持单元测试

---

## 2. 现有架构分析

### 2.1 当前目录结构

```
astrbot_plugin_qq_group_daily_analysis/
├── main.py                          # 插件入口 (Application Layer - Controller)
├── src/
│   ├── core/                        # 核心模块
│   │   ├── bot_manager.py           # Bot 实例管理 (Infrastructure)
│   │   ├── config.py                # 配置管理 (Infrastructure)
│   │   ├── history_manager.py       # 历史记录管理 (Infrastructure)
│   │   ├── message_handler.py       # 消息处理 (Application Service)
│   │   └── message_sender.py        # 消息发送 (Infrastructure)
│   ├── scheduler/                   # 调度模块
│   │   ├── auto_scheduler.py        # 自动调度器 (Application Service)
│   │   └── retry.py                 # 重试管理器 (Infrastructure)
│   ├── analysis/                    # 分析模块
│   │   ├── llm_analyzer.py          # LLM 分析协调器 (Application Service)
│   │   ├── analyzers/               # 具体分析器 (Domain Services)
│   │   │   ├── base_analyzer.py
│   │   │   ├── topic_analyzer.py
│   │   │   ├── user_title_analyzer.py
│   │   │   └── golden_quote_analyzer.py
│   │   └── utils/                   # 分析工具
│   │       ├── json_utils.py
│   │       └── llm_utils.py
│   ├── models/                      # 数据模型
│   │   └── data_models.py           # 数据结构定义 (Domain Models)
│   ├── reports/                     # 报告模块
│   │   ├── dispatcher.py            # 报告分发器 (Application Service)
│   │   ├── generators.py            # 报告生成器 (Domain Service)
│   │   └── templates/               # 报告模板 (Infrastructure)
│   ├── visualization/               # 可视化模块
│   │   └── activity_charts.py       # 活跃度图表 (Domain Service)
│   └── utils/                       # 工具模块
│       ├── helpers.py               # 辅助函数
│       ├── pdf_utils.py             # PDF 工具 (Infrastructure)
│       ├── resilience.py            # 熔断器/限流器 (Infrastructure)
│       └── trace_context.py         # 链路追踪 (Infrastructure)
└── docs/                            # 文档
```

### 2.2 当前架构优点

| 优点 | 体现 |
|------|------|
| **模块化清晰** | 按功能划分目录：core、scheduler、analysis、reports、visualization |
| **职责单一** | MessageSender 只负责发送，ReportDispatcher 只负责分发 |
| **可观测性** | TraceContext + TraceLogFilter 实现全链路追踪 |
| **弹性设计** | CircuitBreaker + GlobalRateLimiter + RetryManager |
| **框架对齐** | 使用 AstrBot 的 cron_manager、platform_manager、put_kv_data |
| **并发控制** | asyncio.Semaphore 控制并发，asyncio.gather 并行执行 |

### 2.3 当前架构不足 (DDD 视角)

| 不足 | 说明 | 影响 |
|------|------|------|
| **领域边界模糊** | 没有明确的限界上下文定义 | 模块间耦合度难以评估 |
| **贫血模型** | data_models.py 只有数据结构，无行为 | 业务逻辑分散在 Service 中 |
| **依赖方向混乱** | Application 层直接依赖 Infrastructure | 测试困难，替换实现困难 |
| **缺少聚合根** | 没有定义实体的一致性边界 | 状态管理分散 |
| **接口抽象不足** | 直接依赖具体实现类 | Mock 测试困难 |

---

## 3. DDD 重构方案

### 3.1 限界上下文识别 (Bounded Contexts)

基于业务能力分析，本插件包含以下限界上下文：

```
┌─────────────────────────────────────────────────────────────────┐
│                    群聊日常分析插件 (Plugin)                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   调度上下文     │  │   分析上下文     │  │   报告上下文     │  │
│  │  (Scheduling)   │  │  (Analysis)     │  │  (Reporting)    │  │
│  │                 │  │                 │  │                 │  │
│  │ - 定时任务      │  │ - 话题分析      │  │ - 报告生成      │  │
│  │ - 并发控制      │  │ - 用户画像      │  │ - 格式转换      │  │
│  │ - 任务编排      │  │ - 金句提取      │  │ - 消息发送      │  │
│  │                 │  │ - 统计计算      │  │ - 重试机制      │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                │                                │
│  ┌─────────────────────────────┴─────────────────────────────┐  │
│  │                    共享内核 (Shared Kernel)                 │  │
│  │  - 配置管理 (ConfigManager)                                │  │
│  │  - Bot 管理 (BotManager)                                   │  │
│  │  - 链路追踪 (TraceContext)                                 │  │
│  │  - 弹性组件 (CircuitBreaker, RateLimiter)                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 DDD 分层架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        Interface Layer                          │
│                       (接口层 / 用户界面)                         │
│  main.py - 命令处理、事件响应、框架集成                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│                       (应用层 / 用例)                            │
│  - AnalysisOrchestrator: 分析流程编排                           │
│  - SchedulingService: 定时任务管理                              │
│  - ReportingService: 报告生成与分发                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Layer                             │
│                      (领域层 / 核心业务)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Entities (实体)                                          │    │
│  │  - AnalysisTask: 分析任务实体                            │    │
│  │  - GroupAnalysisResult: 群分析结果实体                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Value Objects (值对象)                                   │    │
│  │  - SummaryTopic, UserTitle, GoldenQuote                 │    │
│  │  - GroupStatistics, TokenUsage                          │    │
│  │  - AnalysisContext, RetryPolicy                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Domain Services (领域服务)                               │    │
│  │  - TopicAnalyzer, UserTitleAnalyzer, GoldenQuoteAnalyzer│    │
│  │  - StatisticsCalculator, ActivityVisualizer             │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Repository Interfaces (仓储接口)                         │    │
│  │  - IAnalysisHistoryRepository                           │    │
│  │  - IMessageRepository                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                         │
│                      (基础设施层 / 实现)                          │
│  - KVAnalysisHistoryRepository: 使用 AstrBot KV 存储            │
│  - OneBotMessageRepository: 通过 OneBot API 获取消息            │
│  - MessageSender: 消息发送实现                                  │
│  - LLMClient: LLM API 调用实现                                  │
│  - ConfigManager: 配置读写实现                                  │
│  - BotManager: Bot 实例管理实现                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 目标目录结构

```
astrbot_plugin_qq_group_daily_analysis/
├── main.py                              # Interface Layer
├── src/
│   ├── application/                     # Application Layer
│   │   ├── __init__.py
│   │   ├── analysis_orchestrator.py     # 分析流程编排
│   │   ├── scheduling_service.py        # 定时任务服务
│   │   └── reporting_service.py         # 报告服务
│   │
│   ├── domain/                          # Domain Layer
│   │   ├── __init__.py
│   │   ├── entities/                    # 实体
│   │   │   ├── __init__.py
│   │   │   ├── analysis_task.py         # 分析任务实体
│   │   │   └── analysis_result.py       # 分析结果实体
│   │   ├── value_objects/               # 值对象
│   │   │   ├── __init__.py
│   │   │   ├── topic.py                 # SummaryTopic
│   │   │   ├── user_title.py            # UserTitle
│   │   │   ├── golden_quote.py          # GoldenQuote
│   │   │   ├── statistics.py            # GroupStatistics, TokenUsage
│   │   │   └── analysis_context.py      # AnalysisContext
│   │   ├── services/                    # 领域服务
│   │   │   ├── __init__.py
│   │   │   ├── topic_analyzer.py
│   │   │   ├── user_title_analyzer.py
│   │   │   ├── golden_quote_analyzer.py
│   │   │   ├── statistics_calculator.py
│   │   │   └── report_generator.py
│   │   └── repositories/                # 仓储接口
│   │       ├── __init__.py
│   │       ├── analysis_history_repository.py
│   │       └── message_repository.py
│   │
│   ├── infrastructure/                  # Infrastructure Layer
│   │   ├── __init__.py
│   │   ├── persistence/                 # 持久化实现
│   │   │   ├── __init__.py
│   │   │   └── kv_analysis_history_repository.py
│   │   ├── messaging/                   # 消息通信
│   │   │   ├── __init__.py
│   │   │   ├── onebot_message_repository.py
│   │   │   ├── message_sender.py
│   │   │   └── retry_manager.py
│   │   ├── llm/                         # LLM 集成
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py
│   │   │   └── llm_utils.py
│   │   ├── bot/                         # Bot 管理
│   │   │   ├── __init__.py
│   │   │   └── bot_manager.py
│   │   ├── config/                      # 配置管理
│   │   │   ├── __init__.py
│   │   │   └── config_manager.py
│   │   └── resilience/                  # 弹性组件
│   │       ├── __init__.py
│   │       ├── circuit_breaker.py
│   │       ├── rate_limiter.py
│   │       └── trace_context.py
│   │
│   └── shared/                          # 共享内核
│       ├── __init__.py
│       └── exceptions.py                # 自定义异常
│
├── tests/                               # 测试
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   └── integration/
│
└── docs/                                # 文档
```

---

## 4. 领域模型设计

### 4.1 实体 (Entities)

#### 4.1.1 AnalysisTask (分析任务)

```python
# src/domain/entities/analysis_task.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid

class TaskStatus(Enum):
    PENDING = "pending"
    FETCHING_MESSAGES = "fetching_messages"
    ANALYZING = "analyzing"
    GENERATING_REPORT = "generating_report"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AnalysisTask:
    """
    分析任务实体 - 聚合根
    封装单次群聊分析的完整生命周期
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    platform_id: str = ""
    trace_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    is_manual: bool = False
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 结果引用
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    
    # 业务方法
    def start(self):
        """开始执行任务"""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in {self.status} status")
        self.status = TaskStatus.FETCHING_MESSAGES
        self.started_at = time.time()
    
    def advance_to(self, status: TaskStatus):
        """推进任务状态"""
        self.status = status
    
    def complete(self, result_id: str):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.result_id = result_id
        self.completed_at = time.time()
    
    def fail(self, error: str):
        """标记失败"""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = time.time()
    
    @property
    def duration(self) -> Optional[float]:
        """任务耗时"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
```

#### 4.1.2 GroupAnalysisResult (分析结果)

```python
# src/domain/entities/analysis_result.py
from dataclasses import dataclass, field
from typing import List, Optional
import time

@dataclass
class GroupAnalysisResult:
    """
    群分析结果实体
    聚合所有分析产出
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    group_id: str = ""
    trace_id: str = ""
    
    # 分析结果
    statistics: Optional['GroupStatistics'] = None
    topics: List['SummaryTopic'] = field(default_factory=list)
    user_titles: List['UserTitle'] = field(default_factory=list)
    golden_quotes: List['GoldenQuote'] = field(default_factory=list)
    
    # 元数据
    message_count: int = 0
    analysis_days: int = 1
    created_at: float = field(default_factory=time.time)
    
    # 部分失败记录
    partial_failures: List[str] = field(default_factory=list)
    
    def add_partial_failure(self, module: str):
        """记录部分失败"""
        if module not in self.partial_failures:
            self.partial_failures.append(module)
    
    def is_complete(self) -> bool:
        """检查是否完整"""
        return len(self.partial_failures) == 0
    
    def to_dict(self) -> dict:
        """转换为字典（用于报告生成）"""
        return {
            "statistics": self.statistics,
            "topics": self.topics,
            "user_titles": self.user_titles,
            "golden_quotes": self.golden_quotes,
        }
```

### 4.2 值对象 (Value Objects)

当前 `data_models.py` 中的类已经是良好的值对象设计，保持不变：

- `SummaryTopic` - 话题摘要
- `UserTitle` - 用户称号
- `GoldenQuote` - 金句
- `GroupStatistics` - 群统计
- `TokenUsage` - Token 使用量
- `EmojiStatistics` - 表情统计
- `ActivityVisualization` - 活跃度可视化

新增值对象：

```python
# src/domain/value_objects/analysis_context.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AnalysisContext:
    """
    分析上下文值对象
    封装单次分析的元信息
    """
    trace_id: str
    group_id: str
    platform_id: str
    analysis_days: int
    is_manual: bool
    unified_msg_origin: str = ""

@dataclass(frozen=True)
class RetryPolicy:
    """
    重试策略值对象
    """
    max_retries: int = 3
    base_delay: float = 5.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_range: tuple = (1.0, 5.0)
```

### 4.3 仓储接口 (Repository Interfaces)

```python
# src/domain/repositories/analysis_history_repository.py
from abc import ABC, abstractmethod
from typing import Optional, List

class IAnalysisHistoryRepository(ABC):
    """分析历史仓储接口"""
    
    @abstractmethod
    async def save(self, group_id: str, result: 'GroupAnalysisResult') -> bool:
        """保存分析结果"""
        pass
    
    @abstractmethod
    async def get(self, group_id: str, date_str: str, time_str: str) -> Optional[dict]:
        """获取指定时间的分析结果"""
        pass
    
    @abstractmethod
    async def exists(self, group_id: str, date_str: str, time_str: str) -> bool:
        """检查是否存在分析记录"""
        pass
    
    @abstractmethod
    async def list_by_group(self, group_id: str, limit: int = 10) -> List[dict]:
        """列出群的历史分析"""
        pass


# src/domain/repositories/message_repository.py
from abc import ABC, abstractmethod
from typing import List

class IMessageRepository(ABC):
    """消息仓储接口"""
    
    @abstractmethod
    async def fetch_messages(
        self, 
        group_id: str, 
        days: int,
        platform_id: str
    ) -> List[dict]:
        """获取群消息"""
        pass
```

---

## 5. 重构路线图

### Phase 0: 准备工作 (1 天)

**目标**: 建立重构基础设施

1. **创建目录结构**
   - 按照 3.3 节创建新的目录结构
   - 保留原有文件，采用渐进式迁移

2. **定义接口**
   - 创建 `IAnalysisHistoryRepository` 接口
   - 创建 `IMessageRepository` 接口
   - 创建 `IMessageSender` 接口

3. **添加共享异常**
   ```python
   # src/shared/exceptions.py
   class AnalysisError(Exception): pass
   class MessageFetchError(AnalysisError): pass
   class LLMError(AnalysisError): pass
   class ReportGenerationError(AnalysisError): pass
   class MessageSendError(AnalysisError): pass
   ```

### Phase 1: 领域层提取 (3-4 天)

**目标**: 将核心业务逻辑迁移到领域层

1. **迁移值对象**
   - 将 `data_models.py` 拆分到 `domain/value_objects/`
   - 添加 `AnalysisContext` 和 `RetryPolicy`

2. **创建实体**
   - 实现 `AnalysisTask` 实体
   - 实现 `GroupAnalysisResult` 实体

3. **迁移领域服务**
   - 将 `analyzers/` 移动到 `domain/services/`
   - 将 `ActivityVisualizer` 移动到 `domain/services/`
   - 确保领域服务不依赖基础设施

**验收标准**:
- 领域层代码无外部依赖（除 Python 标准库和 dataclasses）
- 所有领域逻辑可独立测试

### Phase 2: 基础设施层实现 (2-3 天)

**目标**: 实现仓储和外部集成

1. **实现仓储**
   - `KVAnalysisHistoryRepository` 实现 `IAnalysisHistoryRepository`
   - `OneBotMessageRepository` 实现 `IMessageRepository`

2. **迁移基础设施组件**
   - 将 `message_sender.py` 移动到 `infrastructure/messaging/`
   - 将 `bot_manager.py` 移动到 `infrastructure/bot/`
   - 将 `config.py` 移动到 `infrastructure/config/`
   - 将 `resilience.py` 拆分到 `infrastructure/resilience/`

3. **LLM 客户端封装**
   - 创建 `LLMClient` 封装 LLM 调用
   - 集成熔断器和限流器

**验收标准**:
- 基础设施层实现所有仓储接口
- 可通过 Mock 替换任意基础设施组件

### Phase 3: 应用层重构 (2-3 天)

**目标**: 实现用例编排

1. **创建应用服务**
   - `AnalysisOrchestrator`: 编排完整分析流程
   - `SchedulingService`: 管理定时任务
   - `ReportingService`: 处理报告生成和发送

2. **依赖注入**
   - 应用服务通过构造函数注入仓储接口
   - 使用接口而非具体实现

3. **重构 AutoScheduler**
   - 将业务逻辑委托给 `AnalysisOrchestrator`
   - AutoScheduler 仅保留调度职责

**验收标准**:
- 应用层仅依赖领域层接口
- 可为应用服务编写单元测试

### Phase 4: 接口层对接 (1-2 天)

**目标**: 更新入口点

1. **重构 main.py**
   - 使用依赖注入组装各层
   - 命令处理器委托给应用服务

2. **保持向后兼容**
   - 确保所有命令功能不变
   - 配置格式保持兼容

**验收标准**:
- 所有现有功能正常工作
- 通过 `ruff check` 和 `ruff format`

### Phase 5: 测试与文档 (2 天)

**目标**: 补充测试和更新文档

1. **单元测试**
   - 领域实体测试
   - 领域服务测试
   - 应用服务测试（Mock 仓储）

2. **集成测试**
   - 端到端分析流程测试

3. **文档更新**
   - 更新 README
   - 更新架构文档

---

## 6. 风险评估与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 重构引入回归 Bug | 中 | 高 | 渐进式迁移，保留原有代码直到验证完成 |
| 过度设计 | 中 | 中 | 遵循 YAGNI，仅实现必要的抽象 |
| 性能下降 | 低 | 中 | 保持异步架构，避免不必要的对象创建 |
| 团队学习曲线 | 中 | 低 | 提供清晰的文档和代码示例 |
| 与 AstrBot 框架冲突 | 低 | 高 | 继续遵循 06_review.md 的框架对齐原则 |

---

## 7. 不建议实施的方案

基于 06_review.md 的分析和当前代码状态，以下方案**不建议**实施：

| 方案 | 原因 |
|------|------|
| 自建 EventBus | AstrBot 已有事件系统，自建会造成重复 |
| 完整 CQRS 模式 | 插件规模不足以支撑 CQRS 复杂度 |
| 独立数据库 | 应使用 AstrBot 的 KV 存储 |
| 复杂的 Saga 模式 | 当前流程足够简单，不需要分布式事务 |
| 领域事件 + 事件溯源 | 过度设计，简单的状态机即可 |

---

## 8. 总结与建议

### 8.1 当前状态

本插件已经完成了一次成功的务实重构，代码质量显著提升：
- ✅ AutoScheduler 精简化
- ✅ MessageSender、ReportDispatcher 独立
- ✅ TraceContext 链路追踪
- ✅ CircuitBreaker + RateLimiter 弹性设计
- ✅ 框架 API 对齐

### 8.2 DDD 重构建议

**推荐程度**: ⭐⭐⭐ (可选，非必须)

当前代码已经足够好用。DDD 重构的主要收益是：
1. **更好的可测试性** - 通过接口抽象支持 Mock
2. **更清晰的边界** - 领域层与基础设施层分离
3. **更好的可扩展性** - 新增分析器更容易

**建议优先级**:
1. **P0 (推荐)**: 定义仓储接口，提升可测试性
2. **P1 (可选)**: 引入 AnalysisTask 实体，统一状态管理
3. **P2 (可选)**: 完整的目录结构重组

### 8.3 下一步行动

如果决定进行 DDD 重构：
1. 从 Phase 0 开始，先建立接口定义
2. 采用渐进式迁移，不要一次性重写
3. 每个 Phase 完成后进行功能验证
4. 保持与 AstrBot 框架的对齐

如果决定维持现状：
1. 当前架构已足够支撑业务需求
2. 可以在需要时逐步引入 DDD 元素
3. 重点关注功能迭代而非架构重构

---

## 附录 A: 术语表

| 术语 | 定义 |
|------|------|
| **限界上下文 (Bounded Context)** | 领域模型的边界，定义了模型的适用范围 |
| **实体 (Entity)** | 具有唯一标识的领域对象，生命周期内身份不变 |
| **值对象 (Value Object)** | 无唯一标识的领域对象，通过属性值定义 |
| **聚合根 (Aggregate Root)** | 聚合的入口点，保证聚合内的一致性 |
| **领域服务 (Domain Service)** | 无状态的领域逻辑，不属于任何实体 |
| **仓储 (Repository)** | 领域对象的持久化抽象 |
| **应用服务 (Application Service)** | 用例编排，协调领域对象完成业务流程 |

## 附录 B: 参考资料

1. Eric Evans - *Domain-Driven Design: Tackling Complexity in the Heart of Software*
2. Vaughn Vernon - *Implementing Domain-Driven Design*
3. 06_review.md - 本项目的务实重构审查报告
4. AstrBot 官方文档 - https://astrbot.app/
