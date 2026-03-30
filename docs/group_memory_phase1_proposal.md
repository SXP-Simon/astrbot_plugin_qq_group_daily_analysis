# 15. 群聊记忆模块 Phase 1 提案

## 1. 文档定位

本文档是基于以下两份前置文档收敛后的第一阶段设计：

- `docs/group_memory_proposal.md`
- `docs/group_memory_feasibility_review.md`

与总提案不同，本文只回答一个问题：

在当前插件代码与 AstrBot 宿主生态的真实边界下，第一阶段到底做什么、怎么做、做到什么程度算完成。

## 2. Phase 1 目标

### 2.1 目标描述

Phase 1 的目标不是做一个“完美的认知架构”，而是交付一个可运行、可演化、可清理的群级长期记忆系统。

它需要满足以下能力：

- 以群为天然作用域，维护长期记忆空间。
- 能从增量批次中抽取结构化长期记忆候选。
- 能维护群级长期画像。
- 能维护群内成员轻量长期画像。
- 能在最终总结前检索相关长期记忆，并增强总结 prompt。
- 能通过 compact / retention 机制控制存储膨胀。

### 2.2 交付标准

当 Phase 1 完成时，应具备以下可见效果：

- 同一个群的总结开始体现持续的群风格。
- 对同一个成员的描述不再完全依赖当天表现，而是出现轻量长期连续性。
- 总结中可以自然提到与近期历史相关的延续话题。
- 长期记忆不会无限增长，并且支持清理和重建。

## 3. Phase 1 范围

### 3.1 In Scope

- 群级记忆作用域：`group_scope_id`
- 事件型记忆：`Episode`
- 群画像：`GroupProfile`
- 成员轻量画像：`MemberProfileLite`
- 最终总结记忆增强
- 基础 compact / cleanup
- 基础安全过滤

### 3.2 Out of Scope

- thread / topic 级作用域
- 跨群统一成员画像
- embedding / vector retrieval
- 图谱式关系建模
- 高复杂度人格漂移模型
- 大规模原始聊天回放式记忆拼装

## 4. 核心设计原则

### 4.1 首期只做群级作用域

Phase 1 的长期记忆主键统一为：

```text
group_scope_id = "{platform_id}:GroupMessage:{group_id}"
```

说明：

- `platform_id` 使用 AstrBot 的标准平台实例 ID
- `GroupMessage` 保持与 UMO 格式一致
- `group_id` 与插件当前已有调度和增量分析逻辑保持一致

这样可以直接与当前插件工作流兼容。

### 4.2 记忆增强只影响最终总结

首期不要求所有 analyzer 都接入长期记忆。

仅在最终总结链路中引入长期记忆摘要：

- 群画像摘要
- 成员画像摘要
- 相关历史事件摘要

这样可以显著降低改造面。

### 4.3 长期画像只做轻量版

首期成员画像不追求复杂人格建模，只保留插件当前信号源能够稳定支持的维度。

## 5. Phase 1 数据模型

## 5.1 `GroupProfile`

用于描述一个群的长期稳定特征。

建议字段：

```json
{
  "scope_id": "qq:GroupMessage:123456",
  "summary": "这是一个以插件开发和部署交流为主，同时夹杂大量整活和吐槽的技术群。",
  "tone_tags": ["技术讨论", "高频吐槽", "互助答疑"],
  "recurring_topics": ["AstrBot", "插件开发", "平台适配", "LLM配置"],
  "interaction_style": ["高信息密度", "熟人化交流", "延续性梗较多"],
  "core_members": [
    {"user_id": "u1", "role": "答疑核心"},
    {"user_id": "u2", "role": "整活与吐槽"}
  ],
  "confidence": 0.72,
  "updated_at": 1710000000
}
```

### 5.2 `MemberProfileLite`

用于描述一个成员在某个群内的轻量长期画像。

建议字段：

```json
{
  "scope_id": "qq:GroupMessage:123456",
  "user_id": "789",
  "display_name": "Simon",
  "activity_traits": ["高频发言", "晚间活跃"],
  "topic_preferences": ["插件架构", "调度逻辑", "兼容性问题"],
  "style_traits": ["直接", "技术密度高", "偶尔吐槽"],
  "role_tags": ["答疑者", "推进者"],
  "confidence": 0.64,
  "last_active_at": 1710000000,
  "updated_at": 1710000000
}
```

注意：

- `style_traits` 在首期只允许用保守表达
- `role_tags` 必须是群内行为角色，不是现实人格标签

### 5.3 `Episode`

用于描述最近一段时间中值得记住的事件型记忆。

建议字段：

```json
{
  "memory_id": "ep_xxx",
  "scope_id": "qq:GroupMessage:123456",
  "time_range": {
    "start_ts": 1710000000,
    "end_ts": 1710001200
  },
  "summary": "群里围绕飞书成员权限预热方案持续讨论，最终收敛到先执行缓存预检查的做法。",
  "keywords": ["飞书", "权限", "缓存预热"],
  "participants": ["u1", "u2", "u3"],
  "importance": 0.81,
  "source_batch_ids": ["batch_a", "batch_b"],
  "expires_at": 1712592000
}
```

### 5.4 `MemorySnapshot`

用于在最终总结阶段快速构建记忆上下文，而不是每次都从零扫描大量条目。

建议字段：

```json
{
  "scope_id": "qq:GroupMessage:123456",
  "group_profile_digest": "...",
  "member_profile_digests": [
    {"user_id": "u1", "digest": "..."},
    {"user_id": "u2", "digest": "..."}
  ],
  "recent_episode_digest": [
    {"memory_id": "ep_1", "digest": "..."},
    {"memory_id": "ep_2", "digest": "..."}
  ],
  "updated_at": 1710000000
}
```

## 6. 存储设计

### 6.1 存储介质

Phase 1 采用：

- 主存储：插件 KV
- 大快照与导出：`plugin_data`

不引入新数据库。

### 6.2 KV Key 设计

建议采用如下 key 结构：

```text
mem_group_profile_{scope_id}
mem_member_profile_index_{scope_id}
mem_member_profile_{scope_id}_{user_id}
mem_episode_index_{scope_id}
mem_episode_{scope_id}_{memory_id}
mem_snapshot_{scope_id}
mem_meta_{scope_id}
```

### 6.3 Index 设计

为了避免单 key 无限膨胀，所有列表型结构都采用：

- 单独索引 key
- 单条实体 key

与 `IncrementalStore` 的模式保持一致。

例如：

- `mem_episode_index_{scope_id}` 存储最近 episode 的 id + timestamp
- `mem_episode_{scope_id}_{memory_id}` 存储单个 episode 正文

### 6.4 并发控制

MemoryStore 必须具备 scope 级锁。

理由：

- 增量分析可能并发触发
- 最终报告与 compact 可能冲突
- KV 本身不提供锁

建议做法：

- 在 `MemoryApplicationService` 内使用 `asyncio.Lock`
- lock key 为 `memory:{scope_id}`

## 7. 配置设计

建议新增 `memory` 配置组：

```yaml
memory:
  enabled: true
  enable_memory_in_summary: true
  enable_group_profile: true
  enable_member_profile_lite: true
  max_episode_per_group: 120
  max_member_profile_count: 200
  episode_retention_days: 21
  snapshot_refresh_interval_hours: 24
  retrieve_episode_top_k: 4
  retrieve_member_top_k: 5
  min_profile_confidence: 0.45
  enable_memory_safety_filter: true
```

## 8. 新增模块设计

## 8.1 `MemoryStore`

位置建议：

```text
src/infrastructure/persistence/memory_store.py
```

职责：

- 保存群画像
- 保存成员轻量画像
- 保存 episode
- 保存 snapshot
- 查询与清理

### 8.2 `MemoryApplicationService`

位置建议：

```text
src/application/services/memory_application_service.py
```

职责：

- 统一封装 extract / update / retrieve / compact
- 维护 scope 级锁
- 控制错误回退策略

### 8.3 `MemoryExtractor`

位置建议：

```text
src/infrastructure/analysis/analyzers/memory_extractor.py
```

职责：

- 从 `IncrementalBatch` 提取 episode candidate
- 从 `IncrementalState` / `analysis_result` 提取画像候选

### 8.4 `MemoryUpdater`

位置建议：

```text
src/domain/services/memory_updater.py
```

职责：

- 合并候选记忆到长期存储
- 做去重、置信度调整、替换和衰减

### 8.5 `MemoryPromptBuilder`

位置建议：

```text
src/domain/services/memory_prompt_builder.py
```

职责：

- 将检索到的记忆拼成有限长度的 `memory_digest`
- 控制 prompt 大小
- 避免冗余或极低置信度记忆进入总结 prompt

## 9. 与现有代码的集成点

### 9.1 插件初始化

在 `main.py` 中新增：

- `MemoryStore`
- `MemoryApplicationService`

并注入到 `AnalysisApplicationService`。

### 9.2 增量分析成功后

在 `execute_incremental_analysis()` 成功保存 `IncrementalBatch` 后，新增：

```text
await memory_application_service.update_from_batch(batch, platform_id)
```

要求：

- best-effort
- 失败只记录日志
- 不阻塞主流程成功返回

### 9.3 最终报告前

在 `execute_incremental_final_report()` 中构建最终总结前，新增：

```text
memory_bundle = await memory_application_service.retrieve_for_summary(
    scope_id=group_scope_id,
    state=state,
)
```

返回内容应至少包括：

- `group_profile_digest`
- `member_profile_digests`
- `episode_digests`

### 9.4 最终总结 prompt 注入

需要在最终总结使用的 prompt 构建中引入：

- 当前窗口摘要
- 记忆摘要

注意：

- 记忆增强只作用于最终总结相关 prompt
- 不强制所有 analyzer 都接入

### 9.5 最终报告成功后

在最终报告成功完成后，再执行：

```text
await memory_application_service.refresh_from_final_result(
    scope_id=group_scope_id,
    state=state,
    analysis_result=analysis_result,
)
```

用于更新：

- `GroupProfile`
- `MemberProfileLite`
- `MemorySnapshot`

## 10. Phase 1 检索设计

### 10.1 检索输入

检索阶段只基于以下信息：

- 当前窗口话题
- 当前活跃成员列表
- 当前窗口关键词

### 10.2 检索目标

检索：

- 最近相关的 3 到 4 条 episode
- 当前最活跃成员对应的画像摘要
- 一个群级画像摘要

### 10.3 检索排序

Phase 1 不做 embedding，相似度以规则为主：

- 关键词重合
- 参与者重合
- 时间接近度
- importance
- confidence

建议排序公式：

```text
score =
  keyword_overlap * 0.35 +
  participant_overlap * 0.20 +
  recency * 0.20 +
  importance * 0.15 +
  confidence * 0.10
```

## 11. Phase 1 画像更新设计

### 11.1 `GroupProfile` 更新

更新来源：

- 最近 N 个 batch 的 recurring topics
- 最终总结的群体风格描述
- 最近活跃成员构成

更新原则：

- 不做完全覆盖
- 优先保留已有稳定标签
- 对新标签先低置信度写入

### 11.2 `MemberProfileLite` 更新

更新来源：

- 用户活跃统计
- 其参与的话题
- 最终总结里的用户描述

更新原则：

- 标签必须保守
- 需要多次出现才升高置信度
- 允许保留“近期变化”但不立即改写长期画像

### 11.3 `Episode` 更新

更新来源：

- 增量批次中的话题、金句、参与者、关键词

更新原则：

- 同主题且时间相邻的 episode 可以合并
- 长期无引用 episode 自动过期

## 12. 总结 Prompt 设计

### 12.1 Prompt 结构

建议在最终总结 prompt 中新增如下区块：

```text
[当前窗口信息]
...

[群长期画像摘要]
...

[相关历史事件摘要]
...

[活跃成员长期画像摘要]
...
```

### 12.2 使用规则

必须明确约束模型：

- 以当前窗口事实为主
- 长期记忆只做背景增强
- 低置信度信息不得用确定性口吻表达

### 12.3 预期输出增强

记忆增强后，最终总结建议包含以下隐含效果：

- 话题延续性
- 人物连续性
- 群风格辨识度
- 今日反差点

## 13. 安全与治理

### 13.1 敏感信息过滤

在写入长期记忆前，过滤：

- 电话号
- 邮箱
- 地址
- 明显私人身份信息

### 13.2 保守画像原则

禁用以下危险画像方式：

- 现实人格判断
- 心理诊断式标签
- 政治、宗教、健康等敏感推断

### 13.3 低置信度不进最终总结

如果：

- 画像 `confidence` 太低
- episode `importance` 太低
- 内容带明显攻击性或疑似玩梗误导

则不进入最终总结的记忆增强上下文。

## 14. Compact 与 Cleanup 设计

### 14.1 执行方式

通过 AstrBot `cron_manager` 注册：

- 每日轻量 compact
- 每周深度 snapshot 重建

### 14.2 每日 compact 内容

- 删除过期 episode
- 限制最大 episode 数
- 降低长期未更新画像的置信度

### 14.3 每周 snapshot 重建

- 重写 `MemorySnapshot`
- 合并过旧且低价值的 episode
- 修正摘要冗余

## 15. 开发顺序建议

### Step 1

新增：

- `memory_models.py`
- `memory_store.py`
- `memory_application_service.py`

### Step 2

在 `main.py` 中完成依赖注入。

### Step 3

在 `execute_incremental_analysis()` 中接入 `update_from_batch()`。

### Step 4

在 `execute_incremental_final_report()` 中接入 `retrieve_for_summary()`。

### Step 5

把 `memory_digest` 接入最终总结 prompt。

### Step 6

在最终报告成功后接入 `refresh_from_final_result()`。

### Step 7

接入 `cron_manager` 做 compact / cleanup。

## 16. 测试建议

### 16.1 单元测试

- MemoryStore 的保存、查询、清理
- 画像更新规则
- episode 合并规则
- memory digest 长度控制

### 16.2 集成测试

- 增量批次后能生成记忆
- 最终总结前能正确检索记忆
- 记忆失败不影响主分析结果
- compact 后索引仍然一致

### 16.3 回归重点

- 自动分析调度是否变慢
- 增量分析成功率是否下降
- 现有报告生成是否被破坏
- KV key 数量是否增长过快

## 17. 验收标准

Phase 1 可以判定完成的标准如下：

1. 至少一个群在连续多次增量分析后形成可检索的长期记忆。
2. 最终总结能稳定引用群画像、成员画像或历史 episode 中的一部分信息。
3. 记忆写入失败不会导致分析失败。
4. compact / cleanup 可运行，且能控制记忆条目规模。
5. 不引入新的数据库依赖，不破坏现有调度与报告流程。

## 18. 结论

Phase 1 的核心不是“做一个很强的记忆系统”，而是：

- 把长期记忆作为当前增量分析链路上的第四层结构化沉淀；
- 把它首先用于增强最终总结；
- 以最低风险方式，为后续更复杂的成员画像、关系图谱和 thread 级记忆打基础。

只要这一阶段做稳，后续迭代就会非常自然：

- Phase 2 可以增加更强的画像与漂移判断
- Phase 3 再考虑更细粒度 scope 和向量检索

但在现在，最重要的是先把这条基础链路跑通。
