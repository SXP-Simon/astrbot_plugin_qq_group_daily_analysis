# 03. 领域模型设计 (Domain Model - Pragmatic Edition)

> **注**: 本文档已根据 Review 意见简化，移除了复杂的 DDD 聚合根，保留轻量级的数据结构和必要的配置管理。

## 1. 核心数据结构 (Data Structures)

保持现有 `src/models/data_models.py` 的精简风格，按需增强。

### 1.1 `AnalysisContext` (New)
用于在一次分析流程中传递上下文信息，替代之前的 `AnalysisTask` 聚合根。
*   `trace_id: str`: 链路追踪 ID。
*   `group_id: str`: 目标群号。
*   `start_time: float`: 开始时间。
*   `is_manual: bool`: 是否为手动触发。

### 1.2 `GroupStatistics` (Enhanced)
增强现有的统计模型，支持追踪和部分失败记录。
*   `trace_id: str`: **[New]** 关联的 TraceID。
*   `partial_failures: List[str]`: **[New]** 记录分析过程中失败的模块 (e.g., ["golden_quote"])。
*   `...` (Existing fields: message_count, emoji_stats, etc.)

### 1.3 `LLMRequest` (Value Object)
用于规范化 LLM 请求，支持模块化配置。
*   `module_tag: str`: 业务模块标签 (e.g., "topic", "summary")。
*   `prompt: str`: 提示词。
*   `system_prompt: str`: 系统提示词。
*   `trace_id: str`: 追踪 ID。

## 2. 配置管理 (Configuration)

不引入新的 Entity，直接使用增强后的 `ConfigManager`。

### 2.1 `ConfigManager` (Enhanced)
*   **LLM Configuration**:
    *   `get_provider_config(module_tag: str) -> dict`: 获取特定模块的 Provider 配置 (Platform, Model, Token)。
    *   支持回退策略: Module config -> Global config -> Default config。
*   **Feature Flags**:
    *   `is_module_enabled(module_tag: str) -> bool`: 检查模块开关。

## 3. 基础设施抽象 (Infrastructure Abstractions)

仅保留必要的接口定义，避免过度抽象。

### 3.1 `IMessageSender` (Interface)
*   `send_msg(group_id: str, message: list | str)`: 统一发送接口。

### 3.2 `IReportRenderer` (Interface)
*   `render(data: AnalysisResult, template: str) -> bytes | str`: 渲染接口。

## 4. 链路追踪 (Traceability)

使用 Python 标准库 `contextvars` 实现。

```python
# src/utils/trace_context.py
import contextvars

trace_id_var = contextvars.ContextVar("trace_id", default="N/A")

def get_trace_id() -> str:
    return trace_id_var.get()

def set_trace_id(trace_id: str):
    trace_id_var.set(trace_id)
```
