# 系统架构设计规范 (System Architecture Specification)

本文档阐述 **群聊日常分析插件 (`astrbot_plugin_qq_group_daily_analysis`)** 的整体架构设计、分层约束、DDD 领域建模与端到端核心流水线。

---

## 1. 架构总览 (Architectural Overview)

本插件遵循 **领域驱动设计 (DDD)**、**整洁架构 (Clean Architecture)** 与 **关注点分离原则 (SoC)**，划分为四个清晰的单向依赖层次：

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       WebUI 控制台 (Presentation Layer)                                │
│                     React 18 + Feature-Sliced Design (FSD) + MVVM + Ant Design 5 / Tailwind            │
└───────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                    │ HTTP REST / SSE 实时管道 (PluginPageWebUIBridge)
┌───────────────────────────────────────────────────▼────────────────────────────────────────────────────┐
│                                    应用服务层 (Application Service Layer)                              │
│  ┌──────────────────────────────┬──────────────────────────────┬───────────────────────────────────┐   │
│  │  AnalysisApplicationService  │  IncrementalAnalysisService  │      AnalysisRecoveryService      │   │
│  │   (全量每日分析核心用例门面) │   (增量批次分析与最终聚合)   │   (Checkpoint 断点续跑与重绘)     │   │
│  └──────────────┬───────────────┴──────────────┬───────────────┴───────────────────┬───────────────┘   │
│                 │                              │                                   │                   │
│                 │   ┌──────────────────────────┴───────────────────────────────┐   │                   │
│                 └───► TaskGuard (群锁互斥) | PipelineContext | ResultSerializer ◄───┘                   │
└─────────────────────────────────────────────┬──────────────────────────────────────────────────────────┘
                                              │ 依赖领域模型与仓储契约
┌─────────────────────────────────────────────▼──────────────────────────────────────────────────────────┐
│                                       领域层 (Domain Core Layer)                                       │
│                                                                                                        │
│   ┌────────────────────────┐    ┌─────────────────────────────────────────────────────────────────┐    │
│   │   entities/ (聚合根)   │    │                  value_objects/ (不可变值对象)                  │    │
│   │   IncrementalState     │    │  AnalysisResults (SummaryTopic, UserTitle, GoldenQuote, Stats)  │    │
│   │   IncrementalBatch     │    │  UnifiedMessage | UnifiedGroup | PlatformCapabilities           │    │
│   └───────────┬────────────┘    └────────────────────────────────┬────────────────────────────────┘    │
│               │                                                  │                                     │
│   ┌───────────▼──────────────────────────────────────────────────▼────────────────────────────────┐    │
│   │  services/: IncrementalMergeService | StatisticsService | MessageCleanerService               │    │
│   │  repositories/: IAnalysisProvider | IConfigProvider | IIncrementalStore | ICheckpointStore    │    │
│   └───────────────────────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────▲──────────────────────────────────────────────────────────┘
                                              │ 实现抽象接口契约
┌─────────────────────────────────────────────┴──────────────────────────────────────────────────────────┐
│                                     基础设施层 (Infrastructure Layer)                                  │
│                                                                                                        │
│   ┌────────────────────────┐    ┌────────────────────────┐    ┌───────────────────────────────────┐    │
│   │ reporting/ (报表渲染)  │    │  platform/ (平台适配)  │    │       analysis/ (LLM 分析器)      │    │
│   │ - ReportGenerator      │    │ - OneBot / QQ / TG / DC│    │ - LLMAnalyzer (门面)              │    │
│   │ - RenderDataPreparer   │    │ - MessageConverter     │    │ - Topic / UserTitle / Quote /     │    │
│   │ - ProfileMappings      │    │ - GroupFileManager     │    │   ChatQuality / Comic Analyzers   │    │
│   └────────────────────────┘    └────────────────────────┘    └───────────────────────────────────┘    │
│   ┌────────────────────────┐    ┌────────────────────────┐    ┌───────────────────────────────────┐    │
│   │ persistence/ (持久化)  │    │  config/ (配置管理)    │    │      scheduler/ (定时调度)        │    │
│   │ - CheckpointStore      │    │ - ConfigManager        │    │ - AutoScheduler (Cron 触发器)     │    │
│   │ - IncrementalStore     │    │ - ConfigMigrator       │    │ - ScheduledTargetResolver (解析器)│    │
│   │ - TraceSQLiteStore     │    │   (跨版本迁移与升级)   │    │   (分层白名单/免打扰/并发过滤)    │    │
│   └────────────────────────┘    └────────────────────────┘    └───────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 领域层设计规范 (Domain Layer)

领域层是系统的核心，**绝对不依赖** 任何基础设施组件、外部 IM 协议或 Web 框架。

### 2.1 实体 (Entities) vs 值对象 (Value Objects)
为了彻底消除概念混淆，领域层严格遵循以下职责划分：

| 类别 | 模块路径 | 包含类型 | 特征与职责 |
|---|---|---|---|
| **实体聚合根** | `src/domain/entities/` | `IncrementalState`<br>`IncrementalBatch` | 具备唯一标识与生命周期状态，支持可变聚合与批次持久化追溯 |
| **分析结果值对象** | `src/domain/value_objects/analysis_results.py` | `SummaryTopic`<br>`UserTitle`<br>`GoldenQuote`<br>`QualityReview`<br>`GroupStatistics`<br>`TokenUsage` | 纯不可变数据载体与分析快照，具备自校验与不变性维护规则 |
| **统一通信抽象** | `src/domain/value_objects/unified_*.py` | `UnifiedMessage`<br>`UnifiedGroup`<br>`PlatformCapabilities` | 平台无关的消息结构、群信息与驱动能力集描述 |

> **注**：领域层中严禁设立模糊的 `models/` 目录，所有不可变数据载体统一归位为 `value_objects/`。

### 2.2 仓储与能力契约 (Repositories)
位于 `src/domain/repositories/`，以抽象基类（`ABC`）形式定义外部技术能力契约：
- `IAnalysisProvider`：多维度语义分析接口契约；
- `IConfigProvider`：配置读取与分层检索契约；
- `IIncrementalStore` / `ICheckpointStore`：增量批次与阶段快照持久化契约；
- `IReportGenerator` / `IActivityVisualizer`：报表渲染与图表生成契约。

---

## 3. 应用服务层设计规范 (Application Layer)

应用服务层负责组织用例流转，杜绝单文件膨胀的“上帝类”，通过专职服务实现职责正交解耦：

```text
src/application/services/
├── analysis_application_service.py   # 全量每日分析核心编排器 (单用例聚合门面)
├── incremental_analysis_service.py    # 增量批次提取与滑动窗口汇总用例服务
├── analysis_recovery_service.py       # 断点快照续跑 (Resume) 与免 Token 重绘 (Rerender)
├── analysis_serializer.py             # 领域分析结果与 JSON/Dict 之间的双向序列化器
├── incremental_batch_builder.py       # 增量原始消息批次切分与小时级统计预构建
├── pipeline_context.py                # 跨阶段上下文与产物容器 PipelineContext
└── task_guard.py                      # 基于异步互斥锁的单群并发排他管控 (TaskGuard)
```

### 3.1 核心服务职责划分
1. **`AnalysisApplicationService`**：
   - 处理指令触发或定时触发的**全量每日分析**用例；
   - 协同 `TaskGuard` 确保同一群同一时刻仅执行一个分析任务；
   - 将增量用例请求与断点恢复用例请求透明委托给细分服务。
2. **`IncrementalAnalysisService`**：
   - `execute_incremental_analysis`：滑动窗口增量批次分析；
   - `execute_incremental_final_report`：定时最终汇总报告生成与增量状态归档。
3. **`AnalysisRecoveryService`**：
   - `resume_from_checkpoint`：根据已生成的阶段快照跳过已耗费 Token 的 LLM 阶段，无缝续跑剩余流程；
   - `rerender_report`：纯前端/排版重绘，免 LLM 消耗快速切换视觉模板。

---

## 4. 基础设施层解耦规范 (Infrastructure Layer)

基础设施层为应用层与领域层提供具体技术实现，各大核心子系统均已完成深度解耦：

### 4.1 报表与视觉排版 (`infrastructure/reporting/`)
- `generators.py` (`ReportGenerator`)：专职负责 Jinja2 模板加载、Playwright T2I 渲染与双轮降级输出；
- `render_data_preparer.py` (`RenderDataPreparer`)：专职负责脱敏、活跃度图表装配、MBTI/SBTI/ACGTI 人格卡片徽章映射及 HTML 上下文胶囊打包；
- `profile_mappings.py`：维护 MBTI、SBTI、ACGTI 多套视觉主题的查表与映射规则。

### 4.2 配置中心与跨版本迁移 (`infrastructure/config/`)
- `config_manager.py` (`ConfigManager`)：专职处理配置读取、类型校验、层级名单合并与动态设值；
- `config_migrator.py` (`ConfigMigrator`)：专职负责版本断代升级（如 v1 $\to$ v2 模板升级）、数据目录备份与 schema 自动迁移。

### 4.3 定时调度与名单解析 (`infrastructure/scheduler/`)
- `auto_scheduler.py` (`AutoScheduler`)：专职负责 Cron/时间点调度器注册、后台心跳循环与触发执行；
- `target_resolver.py` (`ScheduledTargetResolver`)：专职负责分层名单过滤（全局白名单/黑名单/免打扰/增量排他）、动态群聊扫描与目标群名单解析。

### 4.4 平台适配与消息转换 (`infrastructure/platform/`)
- `OneBotAdapter`：处理与 OneBot 协议端（NapCat、LLOneBot 等）的 API 交互；
- `message_converter.py` (`MessageConverter`)：专职负责 OneBot CQ 码/消息段与统一 `UnifiedMessage` 的双向转换；
- `group_file_manager.py` (`GroupFileManager`)：专职负责群文件上传与归档管理；
- `QQOfficialAdapter`, `TelegramAdapter`, `DiscordAdapter`：跨平台协议独立实现。

### 4.5 LLM 语义分析器 (`infrastructure/analysis/`)
- `LLMAnalyzer`：作为 IAnalysisProvider 门面协调器；
- 各独立 Analyzer（`TopicAnalyzer`, `UserTitleAnalyzer`, `GoldenQuoteAnalyzer`, `ChatQualityAnalyzer`, `ComicStoryboardAnalyzer`）继承自泛型基类 `BaseAnalyzer[TDataObject, TInputData]`，实现标准化重试、结构化 Schema 校验与 Token 统计。

---

## 5. Web 控制台架构 (Dashboard WebUI)

WebUI 控制台（`dashboard/`）采用 **React 18 + Feature-Sliced Design (FSD)** 规范开发，构建为自包含的单 Bundle 控制台：

```text
dashboard/src/
├── shared/       # [Atoms 原子组件 / 基础通信库 / formatters]
├── entities/     # [领域实体: task, trace, group, metric, report, config, log]
├── features/     # [交互行为: trigger-task, filter-traces, cancel-task, filter-logs]
├── widgets/      # [Organisms 复合微件: TraceTable, TraceDrawer, ActiveTaskBoard]
├── pages/        # [页面组合与 MVVM ViewModel: use*ViewModel]
└── app/          # [根容器与全局上下文配置]
```

- **MVVM 模式**：页面视图（View）与 ViewModel 严格解耦，网络请求与衍生计算全部内聚在 `use*ViewModel`；
- **强类型通信桥**：通过 `shared/api/bridge.ts` 与 AstrBot 宿主进行严格类型的 Iframe Bridge 与 SSE 订阅通信。

---

## 6. 质量保障与门禁指标 (Quality Gates)

任何提交合并均需严格通过以下质量门禁：

1. **类型安全**：`npx pyright` 严格模式 **0 错误、0 警告**；
2. **代码风格与导入**：`uv run ruff check .` 与 `uv run ruff format --check .` 全量通过；
3. **自动化测试**：`uv run pytest` 全量自动化测试套件 **100% 通过**；
4. **前端规范**：`pnpm lint` 与 `pnpm typecheck` **0 错误**。
