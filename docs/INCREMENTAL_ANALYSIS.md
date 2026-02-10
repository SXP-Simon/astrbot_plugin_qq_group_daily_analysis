# 增量分析功能设计文档

## 概述

增量分析是对传统"一天一次完整分析"模式的改进。核心思路是在一天内多次执行小批量分析，将结果作为独立批次存储，最终在配置的报告时间点按滑动窗口查询并合并所有批次，生成完整的日报。

### 解决的问题

1. **消息量过大时分析效果差**：单次拉取的消息量有限，无法覆盖全天聊天内容
2. **24小时活跃图表形同虚设**：单次分析只能捕捉到部分时段的数据
3. **API端点短期压力暴增**：所有群聊在同一时间点执行分析，LLM API 瞬时负载极高
4. **天然日期隔离问题**：旧版按天存储（key含日期），跨天分析数据断裂，多次发送报告时窗口内容相同

## 架构设计

增量分析遵循项目现有的 DDD 分层架构：

```
应用层 (Application)
└── AnalysisApplicationService
    ├── execute_incremental_analysis()    # 单次增量 → 存储独立批次
    └── execute_incremental_final_report() # 滑动窗口查询 → 合并 → 报告

领域层 (Domain)
├── IncrementalBatch         # 独立批次实体（持久化单元）
├── IncrementalState         # 聚合视图（不持久化，报告时合并产生）
└── IncrementalMergeService  # 合并服务（merge_batches + 去重 + 统计构建）

基础设施层 (Infrastructure)
├── IncrementalStore          # 批次持久化（KV索引 + 批次数据）
├── AutoScheduler             # 调度器（传统/增量双模式 + 过期清理）
└── LLMAnalyzer               # LLM分析（增量并发方法）
```

### 核心特性

| 维度 | 设计方案 | 优势 |
|------|---------|------|
| 存储单元 | 独立的 `IncrementalBatch` | 批次间天然隔离，无并发冲突 |
| KV Key | `incr_batch_{group_id}_{batch_id}` | 支持无限扩展和按时间范围查询 |
| 合并时机 | 报告生成时按窗口查询后合并 | 灵活调整窗口（如24h/48h），无数据断裂 |
| 窗口范围 | 滑动窗口（now - analysis_days×24h ~ now） | 任何时间点生成的报告都覆盖完整周期 |
| 多次发送 | 窗口随时间滑动，数据不同 | 支持一天多次生成报告，每次都是最新的 |

## 数据流

### 增量分析批次流程

```
定时触发 → AutoScheduler._run_incremental_analysis()
    → 获取启用的群聊目标
    → 交错并发执行（控制API压力）
        → AnalysisApplicationService.execute_incremental_analysis()
            → 获取 last_analyzed_timestamp（跨批次去重）
            → 拉取自上次分析以来的新消息
            → 检查最小消息数阈值（不足则跳过）
            → LLM 并发分析（话题 + 金句，限制数量）
            → 统计小时级消息分布、用户活跃度
            → 构建 IncrementalBatch 对象
            → save_batch() 保存批次 + 更新索引
            → update_last_analyzed_timestamp()
```

### 最终报告生成流程

```
定时触发 → AutoScheduler._run_incremental_final_report()
    → 获取启用的群聊目标
    → 交错并发执行
        → AnalysisApplicationService.execute_incremental_final_report()
            → 计算滑动窗口: [now - analysis_days×24h, now]
            → query_batches() 按窗口查询批次列表
            → IncrementalMergeService.merge_batches() → IncrementalState
            → 用户画像分析（使用合并后的全窗口数据）
            → build_analysis_result() → analysis_result
            → ReportDispatcher 分发报告
            → cleanup_old_batches() 清理 2×窗口外的过期批次
```

## 持久化（KV 键设计）

```
批次索引:  incr_batch_index_{group_id}
  值: [{"batch_id": "uuid", "timestamp": 1234567890.0}, ...]

批次数据:  incr_batch_{group_id}_{batch_id}
  值: IncrementalBatch.to_dict()

去重时间戳: incr_last_ts_{group_id}
  值: int (最后分析消息的 epoch 时间戳)
```

### 滑动窗口查询

```python
# 报告生成时
window_end = time.time()
window_start = window_end - (analysis_days * 24 * 3600)
batches = await store.query_batches(group_id, window_start, window_end)
state = merge_service.merge_batches(batches, window_start, window_end)
```

### 过期清理

报告发送成功后，清理 2×窗口范围之前的旧批次：

```python
before_ts = time.time() - (analysis_days * 2 * 24 * 3600)
await store.cleanup_old_batches(group_id, before_ts)
```

## 去重机制

### 消息去重（跨批次）

使用全局的 `incr_last_ts_{group_id}` 记录最后分析消息时间戳，
每次增量分析只处理时间戳大于该值的新消息。

### 话题去重（合并时）

使用 Jaccard 字符级相似度，阈值 0.6：

```python
similarity = len(chars_a & chars_b) / len(chars_a | chars_b)
```

比较维度：`topic` 文本的字符集合。

### 金句去重（合并时）

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
- 在配置的报告时间点按滑动窗口合并所有批次生成最终报告
- 适合消息量大、需要全天覆盖的群聊
- 支持同一天多次发送报告（窗口随时间滑动）

## 命令

| 命令 | 说明 |
|------|------|
| `/增量状态` | 查看当前滑动窗口内的增量分析累积情况 |
| `/分析设置 status` | 查看完整设置状态（含增量分析配置） |

## 文件清单

| 文件 | 层 | 说明 |
|------|-----|------|
| `src/domain/entities/incremental_state.py` | 领域 | IncrementalBatch（批次实体）+ IncrementalState（聚合视图） |
| `src/domain/services/incremental_merge_service.py` | 领域 | merge_batches() + 构建统计、话题、金句 |
| `src/infrastructure/persistence/incremental_store.py` | 基础设施 | 批次索引/数据 KV 持久化、窗口查询、过期清理 |
| `src/infrastructure/analysis/llm_analyzer.py` | 基础设施 | `analyze_incremental_concurrent()` |
| `src/infrastructure/analysis/analyzers/base_analyzer.py` | 基础设施 | `_incremental_max_count` 属性 |
| `src/infrastructure/scheduler/auto_scheduler.py` | 基础设施 | 双模式调度（传统+增量）+ 报告后过期批次清理 |
| `src/infrastructure/config/config_manager.py` | 基础设施 | 10个增量配置 getter |
| `src/application/services/analysis_application_service.py` | 应用 | 增量分析（存批次）+ 最终报告（窗口查询+合并）|
| `main.py` | 入口 | 接线 + `/增量状态` 命令（滑动窗口查询）|
| `_conf_schema.json` | 配置 | 增量分析配置 Schema |
