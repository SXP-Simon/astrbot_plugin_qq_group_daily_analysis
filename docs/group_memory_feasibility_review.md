# 14. 群聊记忆模块可执行性复盘与研究记录

## 1. 文档目的

本文档用于沉淀上一轮“群聊记忆模块提案”的后续研究结果，重点回答两个问题：

1. 这套方案在当前插件代码里是否真的能落地？
2. 在 AstrBot 宿主生态下，哪些能力可以直接复用，哪些地方必须调整？

这份文档不再重复完整愿景，而是保留讨论过程中的关键判断、约束、风险和修订方向，作为后续 Phase 1 设计与开发的依据。

## 2. 研究范围

本轮研究从两个方向并行展开：

### 2.1 插件内部可执行性

关注点包括：

- 现有分析链路有哪些真实接入点
- 当前数据模型是否足以支撑长期画像
- KV 持久化是否能承接记忆库
- 调度、并发、回退机制是否会被影响

### 2.2 AstrBot 宿主生态适配性

关注点包括：

- AstrBot 是否已经提供插件级 KV 和数据目录能力
- 宿主是否有可复用的 cron/scheduler 机制
- 会话、人格、UMO、消息历史这些基础设施如何复用
- 哪些宿主能力不适合拿来存长期记忆

## 3. 研究输入

本轮研究主要基于以下资料和代码：

- 群聊记忆总提案：`docs/group_memory_proposal.md`
- 插件应用层编排：`src/application/services/analysis_application_service.py`
- 插件增量存储：`src/infrastructure/persistence/incremental_store.py`
- 插件历史摘要存储：`src/infrastructure/persistence/history_manager.py`
- 插件消息入库：`src/application/services/message_processing_service.py`
- 插件配置管理：`src/infrastructure/config/config_manager.py`
- 插件最终报告生成：`src/domain/services/report_generator.py`
- AstrBot 插件 KV：`astrbot/core/utils/plugin_kv_store.py`
- AstrBot 路径工具：`astrbot/core/utils/astrbot_path.py`
- AstrBot 共享偏好：`astrbot/core/utils/shared_preferences.py`
- AstrBot 定时任务管理：`astrbot/core/cron/manager.py`
- AstrBot 会话与 UMO：`astrbot/core/platform/message_session.py`
- AstrBot 人格管理：`astrbot/core/persona_mgr.py`

## 4. 当前插件已经具备的“记忆底座”

研究后确认，插件并不是从零开始。

当前已经存在三层非常重要的中间能力：

### 4.1 原始消息层

插件在群消息到达时，已经通过 `MessageProcessingService` 将消息写入宿主的 `message_history_manager`。

这意味着：

- 原始聊天记录已经有统一入口
- 记忆系统不需要再自己拦第二份原始消息日志
- 长期记忆应当是“结构化提炼层”，不是“原始历史副本层”

### 4.2 增量批次层

插件已经有成熟的增量分析能力：

- 增量分析时只处理新消息
- 生成 `IncrementalBatch`
- 将话题、金句、用户统计、参与者等中间结果落入 KV
- 最终报告时再按窗口合并

这一层非常适合作为长期记忆的“短期原料层”。

换句话说：

- `IncrementalBatch` 不是长期记忆本身
- 但它天然适合作为长期记忆抽取的输入

### 4.3 最终汇总层

插件在最终报告阶段已经能做：

- 滑动窗口合并
- 用户称号分析
- 质量锐评汇总
- 报告生成与发送

这使得“记忆检索增强最终总结”成为可能。

## 5. 插件侧核心研究结论

### 5.1 方案方向是成立的

结论很明确：

- 方案不是空中楼阁
- 现有插件结构足够支撑“长期记忆层”的加入
- 不需要推倒重写现有分析链路

真正的问题不在于“能不能做”，而在于“第一期要做到什么程度才可控”。

### 5.2 真实接入点只有三个

研究后确认，长期记忆闭环真正适合挂接的位置只有三处：

1. `execute_incremental_analysis()` 成功保存批次之后
2. `execute_incremental_final_report()` 生成最终总结之前
3. `execute_incremental_final_report()` 成功完成之后

它们分别对应：

- 批次后抽取
- 总结前检索
- 总结后刷新

这意味着提案中的记忆闭环应该收敛为：

```text
IncrementalBatch saved
-> extract candidate memories
-> update long-term memory

Final report begins
-> retrieve relevant memory digests
-> inject into summary prompt

Final report succeeds
-> refresh group/member snapshots
```

### 5.3 现在还没有“记忆上下文注入链路”

这是本轮 review 里最重要的结论之一。

现有 `ReportGenerator` 和 LLM 分析链路只关心：

- 统计数据
- 话题
- 用户称号
- 金句
- 聊天质量

但提案里想要的是：

- 群长期画像摘要
- 成员长期画像摘要
- 历史 episode 摘要

这些内容目前没有地方可以传进去。

所以如果要实现“记忆增强总结”，必须先新增一种中间结构，比如：

- `memory_context`
- `memory_digest`
- `retrieved_memory_bundle`

然后把它接进：

- 最终总结 prompt 构建
- 分析结果中间对象
- 可能的报告文案生成逻辑

### 5.4 成员长期画像所需信号还不够丰富

当前插件对用户的统计维度主要包括：

- 消息数
- 字符数
- 回复数
- 表情数
- 活跃时段

这些信号可以支持：

- 活跃用户画像
- 时段偏好
- 轻量角色归纳

但还不足以稳定支撑：

- 话题偏好图谱
- 风格特征
- 关系线索
- 长期行为漂移判断

因此提案需要修正：

- 第一阶段的成员画像只能做轻量版
- 更复杂的画像特征，需要后续新增规则抽取或单独 LLM 画像流程

### 5.5 `thread_scope_id` 暂时不适合作为首期目标

虽然从理论上，Telegram topic、Discord thread、子频道这些都应该成为独立子作用域，但当前插件的稳定主键仍然以 `group_id` 为核心。

研究中发现：

- 消息处理层当前只稳定存群级会话
- 调度层也是按群名单工作
- 增量批次与汇总模型也默认按群聚合

这意味着如果一开始就做 thread 级记忆，会显著扩大改造面：

- 消息侧要持久化更多上下文字段
- 调度侧要知道 thread scope
- 存储层要支持群内多层 scope
- 检索和回写逻辑要区分群画像与 thread 画像

因此结论是：

- 首期先做 `group_scope_id`
- thread / topic scope 作为 Phase 2 或 Phase 3 扩展

## 6. 宿主生态侧核心研究结论

### 6.1 插件 KV 完全可以承接第一版长期记忆

AstrBot 已经提供插件级 KV：

- `put_kv_data`
- `get_kv_data`
- `delete_kv_data`

这意味着长期记忆第一版不需要引入新数据库。

但同时也有边界：

- 只适合 JSON 友好结构
- 不适合无限长单 key 写入
- 不提供复杂索引
- 不提供并发控制

因此要像当前 `IncrementalStore` 一样自行设计：

- 主体数据 key
- 索引 key
- 清理策略
- 分片策略

### 6.2 `plugin_data` 目录适合保存大快照或导出物

如果未来长期记忆需要：

- 调试快照
- 大型归档
- 导出文件
- 可能的 embedding 文件

则应当放到：

- `data/plugin_data/{plugin_name}/`

这与宿主规范一致，也有利于备份和迁移。

### 6.3 不应该再自己起一套新的 scheduler

AstrBot 已经有 `cron_manager`，其背后是：

- APScheduler
- DB-backed cron metadata
- 可追踪的执行状态
- 持久化的 next run 信息

因此长期记忆需要的：

- 每日 compact
- 每周深度重写
- 过期记忆清理

都应该挂到宿主 cron，而不是插件里再单独维护一个新定时器。

### 6.4 UMO / MessageSession / persona_manager 都可以复用

宿主已经提供：

- 标准 UMO 格式：`platform_id:message_type:session_id`
- `MessageSession`
- `persona_manager`
- `conversation_manager`

这意味着：

- 群记忆 scope 的主键应直接遵循 UMO 风格
- 总结时的人格选择逻辑不需要自造
- 记忆增强 prompt 应尊重当前会话对应的人格设定

### 6.5 SharedPreferences 不适合作为长期记忆主存储

这轮研究明确确认：

- SharedPreferences 更适合偏好设置
- 不适合作为长期记忆实体的主存储层

原因包括：

- 语义职责不匹配
- 有临时缓存清理机制
- 容易把配置型数据和记忆型数据混杂

正确做法应该是：

- 长期记忆主存储：插件 KV / plugin_data
- 会话人格、服务偏好等：继续走 SharedPreferences / persona_manager

## 7. 研究中沉淀出的主要风险

### 7.1 存储膨胀风险

如果每个群不断累积 episode 和记忆索引，KV 体积会不断扩大。

具体风险：

- episode 列表过长
- 成员画像过多
- 快照长期不重写
- 某些高活跃群写入频率过高

因此 compact 不是优化项，而是必要功能。

### 7.2 并发竞争风险

当前插件已经有较复杂的调度和增量分析流程。

如果长期记忆写入与增量批次写入同时发生，可能出现：

- 同 scope 下索引竞争
- 批次成功但记忆写入失败
- 定时清理与写入冲突

因此 MemoryStore 必须引入自己的 scope 级锁，不能裸写 KV。

### 7.3 画像过拟合风险

如果只用单日或少量消息更新长期画像，容易导致：

- 短期异常被错误固化
- 某次玩梗变成“长期角色”
- 某天沉默被误判为风格变化

因此需要：

- 候选记忆区
- 置信度机制
- 稳定画像与近期 delta 分离

### 7.4 集成链路复杂度风险

长期记忆如果直接改动所有 analyzer，会迅速扩大工程复杂度。

所以首期最稳妥的方案应限制在：

- 只增强最终总结
- 不强制所有分析模块都接入长期记忆

## 8. 研究后形成的关键修订

基于本轮 review，原始提案需要做以下收敛：

### 8.1 目标收敛

原始目标：

- 群级记忆
- 成员长期画像
- 事件记忆
- 多层作用域
- 安全治理
- 遗忘
- 复杂检索

修订后首期目标：

- 群级长期画像
- 成员轻量长期画像
- episode 事件记忆
- 群级作用域
- 基础 compact
- 最终总结增强

### 8.2 技术路线收敛

原始路线允许多种可能：

- KV
- 文件
- 向量库
- 图结构

修订后首期路线明确为：

- 主存储：插件 KV
- 大快照：plugin_data
- 不引入向量库
- 不引入图数据库

### 8.3 集成范围收敛

原始设想偏全链路增强。

修订后：

- 首期只动增量分析后、最终总结前后这三个接入点
- 首期不强行改造所有 analyzer
- 首期以 memory digest 注入最终总结为主

## 9. 当前最合理的 Phase 1 方向

研究后，我们认为最合理的第一阶段是：

### 9.1 做什么

- 按 `group_scope_id` 构建群级记忆空间
- 从 `IncrementalBatch` 抽取 episode 和记忆候选
- 维护 `GroupProfile`
- 维护 `MemberProfileLite`
- 最终总结前检索记忆摘要并增强 prompt
- 定时 compact 和记忆淘汰

### 9.2 不做什么

- 不做 thread/topic scope
- 不做复杂关系图谱
- 不做 embedding 检索
- 不做跨群用户统一画像
- 不做高风险人格推断

## 10. 对后续开发的直接指导

### 10.1 必须优先做的事情

1. 设计 `MemoryStore`
2. 设计 `memory` 配置组
3. 确定 `memory_digest` 在总结链路中的传递方式
4. 定义首期 `MemberProfileLite` 的字段边界

### 10.2 应优先避免的事情

- 一开始就追求“非常聪明”的画像系统
- 让长期记忆深度侵入所有 LLM analyzer
- 引入新的数据库依赖
- 在插件内重复造 scheduler

## 11. 结论

本轮研究最终得到的结论是：

- 群聊记忆模块在当前插件与 AstrBot 生态中是可执行的。
- 现有的增量批次、插件 KV、UMO、人格管理和宿主 cron 都为该方案提供了现实基础。
- 但原始提案的范围偏大，若直接照单全做，工程风险会明显上升。

因此更可取的路线是：

- 保留原提案的长期方向
- 用本轮研究结论收敛首期范围
- 先交付一版“真正能跑、能演化、能清理”的群级记忆系统

后续文档将基于本文的研究结果，给出修订后的 Phase 1 方案。
