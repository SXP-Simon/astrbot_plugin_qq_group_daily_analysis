# 增量分析功能设计文档

## 概述

增量分析是对传统"一天一次完整分析"模式的改进。核心思路是在一天内多次执行小批量分析，将结果累积合并，最终在配置的报告时间点生成完整的日报。

### 解决的问题

1. **消息量过大时分析效果差**：单次拉取的消息量有限，无法覆盖全天聊天内容
2. **24小时活跃图表形同虚设**：单次分析只能捕捉到部分时段的数据
3. **API端点短期压力暴增**：所有群聊在同一时间点执行分析，LLM API 瞬时负载极高
4. **空闲时段浪费分析次数**：固定间隔调度无法适应群聊活跃度的波动

## 架构设计

增量分析遵循项目现有的 DDD 分层架构：

```
应用层 (Application)
└── AnalysisApplicationService
    ├── execute_incremental_analysis()    # 单次增量批次
    └── execute_incremental_final_report() # 最终报告生成

领域层 (Domain)
├── IncrementalState         # 增量状态实体（累积数据）
├── BatchRecord              # 批次记录值对象
└── IncrementalMergeService  # 合并服务（去重、统计构建）

基础设施层 (Infrastructure)
├── IncrementalStore          # 持久化（KV存储）
├── AutoScheduler             # 调度器（传统/增量双模式）
└── LLMAnalyzer               # LLM分析（增量并发方法）
```

## 数据流

### 增量分析批次流程

```
定时触发 → AutoScheduler._run_incremental_analysis()
    → 获取启用的群聊目标
    → 交错并发执行（控制API压力）
        → AnalysisApplicationService.execute_incremental_analysis()
            → 加载/创建当天 IncrementalState
            → 拉取自上次分析以来的新消息
            → 检查最小消息数阈值（不足则跳过）
            → LLM 并发分析（话题 + 金句，限制数量）
            → 统计小时级消息分布、用户活跃度
            → IncrementalState.merge_batch() 合并（去重）
            → 持久化保存
```

### 最终报告生成流程

```
定时触发 → AutoScheduler._run_incremental_final_report()
    → 获取启用的群聊目标
    → 交错并发执行
        → AnalysisApplicationService.execute_incremental_final_report()
            → 加载当天 IncrementalState
            → 检查是否有分析数据
            → IncrementalMergeService.build_final_statistics() → GroupStatistics
            → IncrementalMergeService.build_topics_for_report() → [SummaryTopic]
            → IncrementalMergeService.build_quotes_for_report() → [GoldenQuote]
            → 用户画像分析（使用累积的全天数据）
            → 组装 analysis_result
            → ReportDispatcher 分发报告
```

## 去重机制

### 话题去重

使用 Jaccard 字符级相似度，阈值 0.6：

```python
similarity = len(chars_a & chars_b) / len(chars_a | chars_b)
```

比较维度：`keyword` + `summary` 文本拼接后的字符集合。

### 金句去重

同样使用 Jaccard 字符级相似度，阈值 0.7（更严格，避免误去重）。

比较维度：`content` 文本的字符集合。

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `incremental_enabled` | `false` | 是否启用增量分析模式 |
| `incremental_interval_minutes` | `120` | 增量分析间隔（分钟） |
| `incremental_max_daily_analyses` | `8` | 每日最大增量分析次数 |
| `incremental_max_messages` | `300` | 每次增量分析最大消息数 |
| `incremental_min_messages` | `20` | 触发增量分析的最小消息数 |
| `incremental_topics_per_batch` | `3` | 每次增量分析提取的话题数 |
| `incremental_quotes_per_batch` | `3` | 每次增量分析提取的金句数 |
| `incremental_active_start_hour` | `8` | 增量分析活跃时段开始小时 |
| `incremental_active_end_hour` | `23` | 增量分析活跃时段结束小时 |
| `incremental_stagger_seconds` | `30` | 多群并发分析的交错间隔（秒） |

## 调度模式对比

### 传统模式（默认）

- 在配置的时间点（如 `23:00`）执行一次完整分析
- 一次性拉取所有消息、LLM 分析、生成报告
- 适合消息量不大的群聊

### 增量模式（新增）

- 在活跃时段内按间隔执行小批量分析（如每2小时一次）
- 每次只分析上次以来的新消息，提取少量话题和金句
- 在配置的报告时间点汇总全天数据生成最终报告
- 适合消息量大、需要全天覆盖的群聊

## 命令

| 命令 | 说明 |
|------|------|
| `/增量状态` | 查看当前群今日的增量分析累积情况 |
| `/分析设置 status` | 查看完整设置状态（含增量分析配置） |

## 持久化

增量状态使用 AstrBot 的 KV 存储：

- Key 格式：`incremental_state_{group_id}_{date_str}`
- Value：JSON 序列化的 `IncrementalState`
- 每日自然过期（下一天生成新的 key）

## 文件清单

| 文件 | 层 | 说明 |
|------|-----|------|
| `src/domain/entities/incremental_state.py` | 领域 | 增量状态实体 + 批次记录 |
| `src/domain/services/incremental_merge_service.py` | 领域 | 合并服务（构建统计、话题、金句） |
| `src/infrastructure/persistence/incremental_store.py` | 基础设施 | KV 持久化仓储 |
| `src/infrastructure/analysis/llm_analyzer.py` | 基础设施 | 新增 `analyze_incremental_concurrent()` |
| `src/infrastructure/analysis/analyzers/base_analyzer.py` | 基础设施 | 新增 `_incremental_max_count` 属性 |
| `src/infrastructure/analysis/analyzers/topic_analyzer.py` | 基础设施 | 覆盖 `get_max_count()` |
| `src/infrastructure/analysis/analyzers/golden_quote_analyzer.py` | 基础设施 | 覆盖 `get_max_count()` |
| `src/infrastructure/scheduler/auto_scheduler.py` | 基础设施 | 双模式调度（传统+增量） |
| `src/infrastructure/config/config_manager.py` | 基础设施 | 10个增量配置 getter |
| `src/application/services/analysis_application_service.py` | 应用 | 增量分析 + 最终报告用例 |
| `main.py` | 入口 | 接线 + `/增量状态` 命令 |
| `_conf_schema.json` | 配置 | 增量分析配置 Schema |
