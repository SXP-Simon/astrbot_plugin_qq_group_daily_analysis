# 01. 需求分析与现状评估 (Pragmatic Refactoring Edition)

> **注**: 本文档基于 `06_review.md` 的反馈进行了大幅修正，从"理想化DDD重构"转向"务实框架对齐重构"。

## 1. 当前现状与实际问题

经过对代码和 AstrBot 框架的深度对比分析，我们重新定义了核心问题：

### 1.1 核心架构冲突
- **重复造轮子**: 插件内部实现了简陋的定时循环 (`_scheduler_loop`)，而忽视了框架提供的 `Context.task_scheduler` (APScheduler)。
- **绕过抽象层**: 大量直接调用 `bot.api.call_action`，导致代码与 OneBot v11 协议强耦合，未利用 AstrBot 的 `Context.send_message` 和 `PlatformManager` 抽象。
- **上帝类 (God Class)**: `AutoScheduler` (1000+行) 确实职责过重，但问题不在于缺乏 EventBus，而在于缺乏合理的模块拆分（如 `MessageSender`, `ReportDispatcher`）。

### 1.2 稳定性痛点 (Confirmed)
- **多群并发冲击**: 确实存在，但通过 `asyncio.Semaphore` 已有基础控制，缺的是**全局速率限制**。
- **LLM 可靠性**: 现有代码已实现多 Provider 和重试，但缺乏**熔断机制 (Circuit Breaker)**，导致单点故障可能拖累整体。
- **发送可靠性**: 图片发送失败是高频问题，虽然有 URL/Base64 降级，但逻辑重复散落在各处。

### 1.3 可观测性缺失
- **日志混乱**: 多群并发分析时，日志交织在一起，无法通过 TraceID 串联单次分析的全过程。

## 2. 重构目标 (Pragmatic Goals)

本次重构的核心原则是：**回归框架，做减法，补短板**。

### 2.1 架构对齐 (Alignment)
- **废弃**自建的定时循环，转用 `Context.task_scheduler`。
- **废弃**直接的 API 调用，尽可能使用 `Context.send_message` 和 `StarTools`。
- **利用**框架生命周期钩子 (`OnPlatformLoaded`) 替代硬编码的 `sleep(30)`。

### 2.2 职责拆分 (Refactoring)
不是引入新架构，而是将 `AutoScheduler` 的代码剥离到独立模块：
- **`MessageSender`**: 统一处理文本、图片、PDF、合并转发发送，封装 URL->Base64 降级逻辑。
- **`ReportDispatcher`**: 负责协调 分析 -> 生成 -> 发送 的流程。
- **`BotManager`**: 增强群组发现和 Session 管理能力。

### 2.3 稳定性增强 (Robustness)
- **TraceID**: 使用 `contextvars` 实现零侵入的链路追踪。
- **Circuit Breaker**: 在 LLM 调用层增加简单的熔断器（失败计数+冷却）。
- **Global Rate Limit**: 全局控制并发请求数。

## 3. 预期收益
- **代码量减少**: 预计减少 ~30% 冗余代码 (主要是 Scheduler 和 Message 发送逻辑)。
- **稳定性提升**: 消除 API 超频风险，提升网络抖动时的恢复能力。
- **维护性提升**: 遵循框架规范，降低后续 AstrBot 升级带来的兼容性风险。
