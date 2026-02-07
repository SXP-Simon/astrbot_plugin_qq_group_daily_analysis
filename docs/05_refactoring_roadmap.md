# 05. 重构路线图 (Refactoring Roadmap - Pragmatic Edition)

> **注**: 本路线图采用渐进式重构策略，优先解决稳定性问题，逐步对齐框架。

## Phase 1: 轻量级增强 (Lightweight Enhancements)
**目标**: 不动架构，仅通过装饰器和 ContextVar 增强系统的可观测性和稳定性。
**预估工期**: 1 周

1.  **TraceID 注入**:
    -   实现 `TraceContext` (contextvars)。
    -   在 `main.py` 和 `auto_scheduler` 入口处埋点。
    -   配置 `logging.Filter`。

2.  **LLM 熔断与限流**:
    -   实现 `CircuitBreaker` 类。
    -   在 `src/utils/llm_utils.py` 的 `call_provider_with_retry` 中集成熔断器和全局 `Semaphore`。

3.  **修复已知 Bug**:
    -   修复 `_send_image_message` 中的双重 `return False` 问题。

**验收标准**:
- 日志中包含 `[trace_id]`。
- 模拟 LLM 故障时，系统能快速失败并恢复。

## Phase 2: 核心职责提取 (Core Extraction)
**目标**: 将 `AutoScheduler` 的核心逻辑剥离为独立模块。
**预估工期**: 1.5 周

1.  **提取 `MessageSender`**:
    -   创建 `src/core/message_sender.py`。
    -   迁移图片/文本发送逻辑，实现 URL->Base64 降级。
    -   在 `main.py` 中替换原有发送逻辑。

2.  **提取 `ReportDispatcher`**:
    -   创建 `src/reports/dispatcher.py`。
    -   迁移报告生成和分发逻辑。

3.  **增强 `BotManager`**:
    -   合并群组发现 (`_get_all_groups`) 逻辑。

**验收标准**:
- `AutoScheduler` 代码行数减少 40% 以上。
- 发送文本和图片功能在各种网络环境下依然稳定。

## Phase 3: 框架完全对齐 (Framework Alignment)
**目标**: 移除自定义调度循环，完全复用 AstrBot 能力。
**预估工期**: 1 周

1.  **对接 `Context.task_scheduler`**:
    -   移除 `_scheduler_loop`。
    -   使用 `context.task_scheduler.add_job` 注册定时任务。

2.  **生命周期钩子**:
    -   使用 `OnPlatformLoaded` 事件替代冷启动 sleep。

3.  **配置清理**:
    -   确保所有配置变更向后兼容。

**验收标准**:
- 插件启动无硬编码等待。
- 定时任务准确触发。
