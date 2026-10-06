# 日志与链路追踪 (TraceContext) 架构与使用指南

> **核心设计理念**：基于 **透明代理模式 (PluginLogger)** + **轻量上下文变量 (TraceContext)**，在严格遵守 AstrBot 插件市场规范（**仅从 `astrbot.api` 导入 `logger`，完全不依赖 Python 内置 `logging` 模块**）的前提下，实现全链路 TraceID 自动注入、调用栈精准回溯、内存环形缓冲 (PluginLogBuffer) 与插件 WebUI 控制台 SSE 实时推流。

---

## 🔍 日志查看入口（三种方式）

### 1️⃣ 插件 WebUI 控制台（最直观，推荐）

访问 AstrBot WebUI 插件专属控制台：
```
http://localhost:6185/#/plugin-page/astrbot_plugin_qq_group_daily_analysis
→ 点击「运行日志」标签页
```

**特性**：
- ✅ **实时推流**：基于 SSE (Server-Sent Events) 长连接秒级同步，支持「实时自动刷新」开关
- ✅ **链路追踪关联**：点击任意日志条目的 `[TraceID]` 标签，可一键过滤全链路生命周期
- ✅ **多维过滤**：支持关键词全文检索、日志级别 (DEBUG/INFO/WARN/ERROR) 与功能分类筛选
- ✅ **快捷操作**：支持单键复制过滤后日志与清空视图

### 2️⃣ 终端控制台（开发调试推荐）

直接启动 AstrBot 即可在终端查看彩色结构化输出：

```bash
uv run main.py

# 输出示例：
[10:30:45] [Core] [INFO] [astrbot_plugin_qq_group_daily_analysis.main:205]: [群分析插件] 插件初始化完成
[10:30:46] [astrbot_plugin_qq_group_daily_analysis] [INFO] [topic_analysis_service:88]: [c478a610] [群分析插件] 话题聚合完成: 共 12 个话题
[10:30:48] [astrbot_plugin_qq_group_daily_analysis] [ERRO] [llm_client:120]: [c478a610] [群分析插件] LLM 调用超时，准备重试
                                                                             ↑
                                                                       TraceID (自动注入)
```

### 3️⃣ 日志文件（生产持久化归档）

AstrBot 主程序运行日志保存于 `data/logs/astrbot.log`，所有插件日志均统一汇聚在此：

```bash
# Linux/macOS 实时查看
tail -f data/logs/astrbot.log

# PowerShell 实时查看
Get-Content -Path data/logs/astrbot.log -Wait

# 检索特定群或 TraceID 的日志
grep "c478a610" data/logs/astrbot.log
```

---

## 🏗️ 插件日志系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     插件代码 (Plugin Codebase)                          │
│                                                                         │
│   with TraceContext(trace_id="c478a610"):                               │
│       logger.info("开始生成日报")                                       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             src.utils.logger.PluginLogger (统一代理层)                  │
│                                                                         │
│  1. 自动从 TraceContext 获取当前协程的 trace_id                         │
│  2. 格式化前缀: "[trace_id] [群分析插件] 消息"                          │
│  3. 调用栈回溯: 精准获取实际调用方代码位置 (如 topic_service.py:45)      │
└───────────────────┬─────────────────────────────────┬───────────────────┘
                    │                                 │
                    ▼                                 ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────┐
│     astrbot.api.logger (宿主通道)    │  │ PluginLogBuffer (插件环形队列)│
│                                      │  │                               │
│  - 控制台格式化与标准输出 (stdout)   │  │  - 纯 Python 内存环形缓冲区    │
│  - 宿主主日志文件写入 (data/logs/)   │  │  - maxlen=500 自动 FIFO 淘汰   │
│  - AstrBot 全局 Dashboard 日志广播   │  │  - 订阅者队列 (Subscriber)     │
└──────────────────────────────────────┘  └───────────────┬───────────────┘
                                                          │
                                                          ▼ SSE 实时推送
                                          ┌───────────────────────────────┐
                                          │ 插件控制台「运行日志」WebUI    │
                                          └───────────────────────────────┘
```

---

## 💻 插件开发中如何使用

### 1. 常规日志输出

在插件内部任何模块中，直接从 `src.utils.logger` 导入 `logger` 即可：

```python
from src.utils.logger import logger

logger.debug("调试数据: payload=%s", payload)
logger.info("群配置已更新: group_id=%s", group_id)
logger.warning("发现网络波动，准备重试: attempt=2")
logger.error("生成群日报失败: %s", exc)
```

> **注意**：禁止直接使用 `import logging` 或 `logging.getLogger()`。统一使用 `src.utils.logger.logger` 以确保日志能被 WebUI 捕获并携带统一前缀。

### 2. 注入与管理 TraceID（链路追踪）

使用 `TraceContext` 上下文管理器，在其范围内的所有日志、异步协程与子任务调用都将**自动携带相同的 TraceID**：

```python
from src.shared.trace_context import TraceContext
from src.utils.logger import logger

async def run_daily_analysis(group_id: str):
    # 生成或指定 8 位短 TraceID / ULID
    trace_id = "c478a610"
    
    with TraceContext(trace_id=trace_id):
        logger.info("开始群分析任务")        # 输出: [c478a610] [群分析插件] 开始群分析任务
        await step_fetch_messages(group_id) # 子调用中 logger 输出同样自动携带 [c478a610]
        await step_generate_report()       # 无需在每个函数中显式传递 trace_id 参数
        logger.info("群分析任务完成")        # 输出: [c478a610] [群分析插件] 群分析任务完成
```

### 3. 上下文透传与多协程边界

`TraceContext` 基于 Python 标准 `contextvars.ContextVar` 实现，天生支持 `asyncio` 协程环境隔离。
在创建后台并发任务时，`asyncio.create_task` 会自动继承当前上下文变量：

```python
# 父协程
with TraceContext("task-1001"):
    # 子协程 task 将自动继承 "task-1001"
    asyncio.create_task(background_work())
```

---

## 🛡️ 上架合规与性能设计

1. **零内置 logging 依赖**：
   - 彻底废弃早期设计中的 `logging.Filter` 与 `logging.Handler` 继承，插件运行时 100% 仅依赖 `astrbot.api.logger`，完全符合 AstrBot 市场安全审查。
2. **有界内存与零内存泄露**：
   - `PluginLogBuffer` 严格限定最大容量（默认 500 条），新日志推入时超限记录自动从队首逐出，绝不占用多余内存。
3. **鉴权日志去重缓存 (FIFO)**：
   - `BotManager` 鉴权针对高频消息判定采用 LRU/FIFO 去重，同一群组与规则仅在状态变更或首次判定时记录 1 次 DEBUG 日志，杜绝高并发消息刷屏。

---

*最后更新：2026年10月 | 适配 AstrBot v4.27+ 与插件市场安全规范*
