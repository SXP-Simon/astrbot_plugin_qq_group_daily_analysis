# 04. 基础设施层设计 (Infrastructure Layer - Improved)

## 1. 链路追踪 (TraceContext)

使用 `contextvars` 实现零侵入的链路追踪，确保所有日志都能关联到具体的分析任务。

### 1.1 实现方案

```python
import contextvars
from astrbot.api import logger

_trace_id_ctx = contextvars.ContextVar("trace_id", default="")

class TraceContext:
    @staticmethod
    def set(trace_id: str):
        return _trace_id_ctx.set(trace_id)

    @staticmethod
    def get() -> str:
        return _trace_id_ctx.get()

class TraceLogFilter(logging.Filter):
    def filter(self, record):
        trace_id = _trace_id_ctx.get()
        if trace_id:
            record.msg = f"[{trace_id}] {record.msg}"
        return True

# 在插件初始化时挂载 Filter
logger.addFilter(TraceLogFilter())
```

## 2. LLM 客户端增强 (Resilient LLM)

在现有的 `call_provider_with_retry` 基础上，增加 **熔断 (Circuit Breaker)** 和 **限流 (Rate Limiter)**。

### 2.1 熔断器 (Circuit Breaker)

防止单点故障拖垮整个流程。

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_failure_time = time.time()

    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True
```

### 2.2 全局限流 (Global Rate Limiter)

使用 `asyncio.Semaphore` 控制并发 LLM 请求数。

```python
# src/core/llm/limiter.py
global_llm_semaphore = asyncio.Semaphore(3) # 最大并发 3

async def call_llm_with_limit(...):
    async with global_llm_semaphore:
        return await call_provider_with_retry(...)
```

## 3. 消息发送增强 (MessageSender)

### 3.1 统一发送接口

```python
class MessageSender:
    def __init__(self, context: Context):
        self.context = context

    async def send_image(self, group_id: str, url: str):
        # 1. 尝试 URL 发送
        # 2. 失败 -> 尝试 Base64 发送
        # 3. 失败 -> 发送文本回退
        pass
```

### 3.2 离线任务支持

对于定时任务触发的场景，此时没有 `AstrMessageEvent`。需要手动构建 Session 或使用 `PlatformManager` 获取 Bot 实例直接发送。

```python
# 获取 Bot 实例
bot = self.context.platform_manager.get_inst(platform_id)
# 构造虚拟 Session
session = Session(bot, group_id=group_id)
# 发送
await self.context.send_message(session, chain)
```
