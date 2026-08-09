# 增量分析功能设计文档

## 概述

增量分析按目标群新增消息数量触发。每个群独立累计待处理消息数，达到 `incremental_min_messages` 后立即处理一个固定规模批次。消息爆发时会连续拆分为多个批次，低活跃群则持续等待消息累积，不受时间段、执行间隔或每日次数限制。

配置的每日分析时间只负责合并已有批次并发送最终报告，不触发增量提取。

## 架构设计

```text
AstrBot 群消息事件
└── GroupDailyAnalysis.count_incremental_group_message()
    └── IncrementalTriggerCoordinator
        ├── 按平台和群组累计待处理消息数
        ├── 达到阈值后创建单群分析任务
        └── AnalysisApplicationService.execute_incremental_analysis()
            ├── 拉取并清洗断点后的消息
            ├── 取最早的固定数量消息构成批次
            ├── IncrementalStore.save_batch()
            └── 保存成功后推进分析断点

每日最终报告定时任务
└── AutoScheduler._run_scheduled_report()
    └── AnalysisApplicationService.execute_incremental_final_report()
        ├── 查询滑动窗口内的批次
        ├── IncrementalMergeService.merge_batches()
        └── 生成并发送最终报告
```

## 消息计数触发

AstrBot 没有内置的“某群达到 N 条消息”回调，因此插件监听通用群消息事件，并按 `(platform_id, group_id)` 维护独立计数。

1. 仅统计同时通过基础群名单、定时分析群名单和增量群名单的消息。
2. 过滤机器人自身消息，并通过消息 ID 抑制同一运行周期内的重复事件。
3. 待处理数量达到 `incremental_min_messages` 时，为该群创建一个分析任务。
4. 同一群同一时刻最多运行一个任务，不同群受全局并发上限约束。
5. 成功处理一个批次后扣减实际消费数量；剩余数量仍达到阈值时立即处理下一批。
6. 分析失败时保留待处理计数；执行期间到达的消息不会触发立即重试，任务结束后的下一条目标群消息到达或插件重启后再尝试。

待处理计数保存在 AstrBot KV 的 `incremental_trigger_states_v1` 中。写入会在内部短暂合并，以避免每条消息都产生一次 KV I/O；该合并仅影响状态落盘频率，不参与分析触发判断。

## 批次处理与幂等

每次拉取由 `incremental_safe_limit` 限制，清洗后只处理断点之后最早的 `incremental_min_messages` 条消息。这样每个 LLM 批次规模稳定，消息爆发只增加批次数，不放大单批负载。

批次 ID 根据平台、群组和批次消息标识生成确定性哈希。同一批消息重试时会覆盖同一个批次索引项；只有批次保存成功后才推进 `incr_last_ts_{group_id}` 断点，避免持久化失败造成消息永久跳过。

## 最终报告

最终报告仍在 `scheduled.analysis_time` 配置的时间点执行。增量群只查询报告滑动窗口内已经落盘的批次，合并统计、话题和金句后发送报告。报告任务不会强制分析不足阈值的剩余消息。

最终报告任务分别记录 `analysis_success` 和 `report_sent`。只有分析结果生成并保存成功，且至少一种配置格式实际发送成功时，总状态 `success` 才为 `true`。分析成功但未发送任何报告时返回 `report_delivery_failed`，不会打印发送成功日志，也不会清理旧增量批次。

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `incremental_group_list_mode` | `whitelist` | 增量群名单模式 |
| `incremental_group_list` | `[]` | 启用增量分析的群列表 |
| `incremental_min_messages` | `300` | 单群累计到多少条消息时触发一个批次 |
| `incremental_safe_limit` | `2000` | 单次拉取和清洗的安全上限 |
| `incremental_topics_per_batch` | `2` | 每批最多提取的话题数 |
| `incremental_quotes_per_batch` | `2` | 每批最多提取的金句数 |
| `incremental_report_immediately` | `false` | 调试时在每批完成后立即生成最终报告 |
| `incremental_fallback_enabled` | `true` | 最终报告失败时是否回退全量分析 |

## 持久化键

| KV 键 | 内容 |
|-------|------|
| `incremental_trigger_states_v1` | 各平台、群组的待处理消息计数 |
| `incr_batch_index_{group_id}` | 群增量批次索引 |
| `incr_batch_{group_id}_{batch_id}` | 单个增量批次数据 |
| `incr_last_ts_{group_id}` | 最后成功分析的时间戳及该秒内消息 ID 游标 |

## 命令

| 命令 | 说明 |
|------|------|
| `/增量状态` | 查看当前滑动窗口内已保存的增量批次 |
| `/分析设置 status` | 查看增量消息阈值及其他分析设置 |
