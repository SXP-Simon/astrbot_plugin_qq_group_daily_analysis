# AstrBot 日志查看方式研究报告

## 概述

本文档详细说明了 AstrBot 的日志系统架构、查看方式、以及如何在代码中集成日志查看功能。

---

## 1. 日志文件默认位置

### 1.1 日志文件存储位置

根据配置，AstrBot 的日志文件存储在以下位置：

| 日志类型 | 默认位置 | 配置键 | 说明 |
|---------|--------|-------|------|
| **普通日志** | `data/logs/astrbot.log` | `log_file_path` | 主应用日志，记录应用运行信息 |
| **Trace 日志** | `data/logs/astrbot.trace.log` | `trace_log_path` | 链路追踪日志，记录请求跨度信息 |

### 1.2 日志文件配置参数

```python
# 配置文件位置: astrbot/core/config/default.py
DEFAULT_CONFIG = {
    "log_level": "INFO",                    # 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    "log_file_enable": False,               # 是否启用文件日志（默认禁用）
    "log_file_path": "logs/astrbot.log",   # 日志文件相对路径（相对于 data/ 目录）
    "log_file_max_mb": 20,                  # 单个日志文件最大大小（MB）
    "trace_enable": False,                  # 是否启用 Trace 记录
    "trace_log_enable": False,              # 是否启用 Trace 文件日志
    "trace_log_path": "logs/astrbot.trace.log",  # Trace 日志文件路径
    "trace_log_max_mb": 20,                 # Trace 日志文件最大大小
}
```

### 1.3 日志目录基路径

- **根数据目录**: `data/`
- **日志目录**: `data/logs/`
- **获取方法**（Python 代码）:
  ```python
  from astrbot.core.utils.astrbot_path import get_astrbot_data_path
  log_dir = os.path.join(get_astrbot_data_path(), "logs")
  ```

### 1.4 日志文件轮转配置

当启用文件日志时，AstrBot 使用 `RotatingFileHandler`：
- 最大单个文件大小：`log_file_max_mb`（默认 20MB）
- 备份文件数量：3 个
- 超过大小后自动轮转：`astrbot.log.1`, `astrbot.log.2`, `astrbot.log.3`

---

## 2. Dashboard 中的日志查看功能

### 2.1 Dashboard 路由和 API

AstrBot Dashboard 提供以下日志相关的 REST API（代码位置：`astrbot/dashboard/routes/log.py`）：

| API 端点 | 方法 | 功能 | 说明 |
|---------|------|------|------|
| `/api/live-log` | GET | 实时日志流 | Server-Sent Events (SSE) 连接，推送实时日志 |
| `/api/log-history` | GET | 日志历史 | 获取缓存的日志历史（JSON 格式） |
| `/api/trace/settings` | GET | Trace 设置查询 | 获取当前 Trace 启用状态 |
| `/api/trace/settings` | POST | Trace 设置更新 | 更新 Trace 启用/禁用状态 |

### 2.2 实时日志流（SSE）

#### 连接方式

**前端代码**（Vue.js，位置：`dashboard/src/stores/common.js`）：

```javascript
fetch('/api/live-log', {
  method: 'GET',
  headers: {
    'Content-Type': 'multipart/form-data',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  cache: 'no-cache',
}).then(response => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  // 处理流式数据...
})
```

#### SSE 消息格式

后端返回的 SSE 消息格式（`astrbot/dashboard/routes/log.py`）：

```
id: {timestamp}
data: {json_object}

```

JSON 对象结构：
```json
{
  "type": "log",
  "level": "INFO",
  "data": "[12:34:56] [Core] [INFO] [file.py:123]: Log message",
  "time": 1697787296.123456,
  "uuid": "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
}
```

#### 日志缓存和重放

- **缓存大小**: 最多 500 条日志（常量 `CACHED_SIZE = 500`）
- **缓存数据结构**: `deque(maxlen=500)`（环形缓冲区）
- **浏览器断网重连**: 发送 `Last-Event-ID` 请求头，服务端根据时间戳重放缺失的日志

### 2.3 Dashboard 前端界面

#### 控制台页面（Console）

**路由**: `/console`  
**组件**: [ConsolePage.vue](dashboard/src/views/ConsolePage.vue)

功能：
- ✅ 实时日志显示（通过 SSE 连接）
- ✅ 日志级别过滤（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- ✅ 自动滚动开关
- ✅ pip 包安装界面

日志样式：
```
[12:34:56] [Core] [INFO] [astrbot.py:123]: AstrBot started successfully
[12:34:57] [Plug] [WARN] [plugin.py:45]: Missing dependency
[12:35:00] [Core] [ERRO] [error.py:78]: Connection timeout [v4.14.4]
```

#### 链路追踪页面（Trace）

**路由**: `/trace`  
**组件**: [TracePage.vue](dashboard/src/views/TracePage.vue)

功能：
- ✅ 实时链路追踪显示
- ✅ Trace 启用/禁用开关
- ✅ Trace 事件详细信息展示

#### 日志显示器组件

**组件**: [ConsoleDisplayer.vue](dashboard/src/components/shared/ConsoleDisplayer.vue)

特性：
- 日志级别色彩标记
- ANSI 颜色代码转换为 HTML 样式
- 日志缓存最多保留 1000 条（configurable）
- 自动滚动到最新日志

---

## 3. LogBroker 架构（发布-订阅模式）

### 3.1 LogBroker 类设计

**位置**: `astrbot/core/log.py`

```python
class LogBroker:
    """日志代理类, 用于缓存和分发日志消息"""

    def __init__(self):
        self.log_cache = deque(maxlen=CACHED_SIZE)  # 环形缓冲区
        self.subscribers: list[Queue] = []          # 订阅者列表

    def register(self) -> Queue:
        """注册新的订阅者，返回一个队列用于接收日志"""
        q = Queue(maxsize=CACHED_SIZE + 10)
        self.subscribers.append(q)
        return q

    def unregister(self, q: Queue):
        """取消订阅"""
        self.subscribers.remove(q)

    def publish(self, log_entry: dict):
        """发布日志到所有订阅者（非阻塞方式）"""
        self.log_cache.append(log_entry)
        for q in self.subscribers:
            try:
                q.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass  # 订阅者队列满，丢弃该日志
```

### 3.2 工作流程图

```
日志记录器 (logger)
    ↓
LogQueueHandler (日志处理器)
    ↓
LogBroker.publish(log_entry)
    ├→ 添加到 log_cache（环形缓冲区）
    └→ 分发给所有订阅者的队列
         ├→ Dashboard SSE 连接
         ├→ Trace 日志记录器
         └→ 其他订阅者
```

### 3.3 日志项结构

```python
log_entry = {
    "level": "INFO",           # 日志级别
    "time": 1697787296.123,   # Unix 时间戳
    "data": "Log message text", # 格式化的日志文本
}
```

### 3.4 在代码中集成 LogBroker

#### 启动应用时初始化

```python
# main.py 或 cmd_run.py
from astrbot.core import LogBroker, LogManager, logger

# 创建日志代理
log_broker = LogBroker()

# 将日志处理器连接到 LogBroker
LogManager.set_queue_handler(logger, log_broker)

# 传递给应用初始化器
core_lifecycle = InitialLoader(db, log_broker)
```

#### 在 Dashboard 中使用

```python
# dashboard/routes/log.py
class LogRoute(Route):
    def __init__(self, context: RouteContext, log_broker: LogBroker) -> None:
        self.log_broker = log_broker
        # 注册 API 路由...

    async def log(self) -> QuartResponse:
        """SSE 日志流"""
        queue = self.log_broker.register()  # 注册订阅者
        try:
            while True:
                message = await queue.get()  # 等待日志
                yield _format_log_sse(message, current_ts)
        finally:
            self.log_broker.unregister(queue)  # 取消订阅
```

---

## 4. Trace 日志系统

### 4.1 Trace 概念

Trace 日志用于记录**请求的整个链路**，包括：
- 跨度信息（span_id）
- 请求发起者（sender_name）
- 操作阶段（action）
- 自定义字段（fields）

### 4.2 Trace 启用配置

**配置项**：
```python
"trace_enable": False,              # 启用 Trace 记录
"trace_log_enable": False,          # 启用 Trace 文件日志
"trace_log_path": "logs/astrbot.trace.log",  # Trace 日志文件路径
```

**Dashboard 设置**: `/api/trace/settings` 端点可动态启用/禁用 Trace

### 4.3 使用 TraceSpan 记录链路

**代码位置**: `astrbot/core/utils/trace.py`

```python
from astrbot.core.utils.trace import TraceSpan

# 创建 Trace 跨度
span = TraceSpan(
    name="group_analysis",
    umo="qq_group",
    sender_name="QQGroup:123456789",
    message_outline="Daily analysis request"
)

# 记录不同阶段的操作
span.record("start", step="initialization")
span.record("process", data_count=1000)
span.record("end", result_code=200)
```

### 4.4 Trace 日志格式

**发布到 LogBroker**：
```json
{
  "type": "trace",
  "level": "TRACE",
  "time": 1697787296.123,
  "span_id": "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx",
  "name": "group_analysis",
  "umo": "qq_group",
  "sender_name": "QQGroup:123456789",
  "message_outline": "Daily analysis request",
  "action": "start",
  "fields": {"step": "initialization"}
}
```

**写入文件**（JSON 格式，每行一条）：
```json
[2024-01-01 12:34:56] {"type":"trace","span_id":"...","name":"group_analysis",...}
```

### 4.5 Trace 查询方式

1. **Dashboard UI** (`/trace` 路由)
   - 实时查看所有 Trace 事件
   - 可启用/禁用 Trace 记录

2. **日志文件查询**
   - 文件位置：`data/logs/astrbot.trace.log`
   - 使用 `jq` 或 Python 解析 NDJSON 格式

3. **span_id 查询** - 用于追踪单个请求
   ```bash
   grep "span_id.*abc123" data/logs/astrbot.trace.log
   ```

---

## 5. 日志访问方式总结

### 5.1 实时日志查看

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| **Dashboard Console** | 浏览器访问 `http://localhost:6185/#/console` | 实时监控、界面友好 |
| **REST API SSE** | `GET /api/live-log`（Server-Sent Events） | 集成第三方系统 |
| **文件直接查看** | `tail -f data/logs/astrbot.log` | 服务器终端查看 |

### 5.2 历史日志查看

| 方式 | 说明 | 命令/代码 |
|------|------|---------|
| **Dashboard History** | `GET /api/log-history` 返回缓存的日志 | 返回最近 500 条 |
| **文件查询** | 日志文件存储在 `data/logs/astrbot.log` | `grep` 或编辑器打开 |
| **日志分析** | Python/shell 脚本处理日志文件 | 自定义分析 |

### 5.3 Trace 日志查看

| 方式 | 说明 | 对应 API |
|------|------|---------|
| **Dashboard Trace** | 实时追踪链路，浏览器访问 `/trace` | SSE 推送 |
| **Trace 文件** | `data/logs/astrbot.trace.log`（NDJSON 格式） | 离线分析 |
| **span_id 查询** | 按 span_id 追踪单个请求 | `grep` 搜索 |

---

## 6. 插件/群分析日志集成示例

### 6.1 为群分析日志添加 Trace ID

对于"QQ 群日常分析插件"（`astrbot_plugin_qq_group_daily_analysis`），可以这样集成日志追踪：

```python
# main.py 或分析模块
from astrbot import logger
from astrbot.core.utils.trace import TraceSpan

class GroupAnalyzer:
    def analyze_group(self, group_id: str):
        # 创建追踪跨度
        span = TraceSpan(
            name="group_daily_analysis",
            umo="qq_group",
            sender_name=f"QQGroup:{group_id}",
            message_outline=f"Daily analysis for group {group_id}"
        )
        
        try:
            span.record("start", group_id=group_id)
            logger.info(f"[GroupAnalysis] Starting analysis for group: {group_id}")
            
            # 分析逻辑...
            data = self._fetch_messages(group_id)
            span.record("fetch_complete", message_count=len(data))
            
            # 处理数据...
            result = self._process_data(data)
            span.record("process_complete", result_code=200)
            
            logger.info(f"[GroupAnalysis] Analysis complete for {group_id}")
            return result
            
        except Exception as e:
            span.record("error", error_type=type(e).__name__, error_msg=str(e))
            logger.error(f"[GroupAnalysis] Error analyzing group {group_id}: {e}")
            raise
```

### 6.2 查询特定群的日志

**在 Dashboard 中**：
1. 打开 `/console` 页面
2. 输入日志过滤器（或查看所有日志）
3. 搜索 `GroupAnalysis` 或特定的 group_id

**通过命令行**：
```bash
# 查找特定群的日志
grep "QQGroup:123456789" data/logs/astrbot.log

# 或查找 Trace 日志
grep "group_id.*123456789" data/logs/astrbot.trace.log
```

### 6.3 日志格式确保

在日志中需要包含：
- **时间戳**: 自动添加（格式 `HH:MM:SS`）
- **日志级别**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **来源标记**: [Core] 或 [Plug]
- **文件和行号**: 自动添加
- **消息内容**: 手动添加

**示例日志行**：
```
[12:34:56] [Plug] [INFO] [group_analyzer.py:145]: [GroupAnalysis] Analysis complete for QQGroup:123456789
```

---

## 7. LogManager 高级配置

### 7.1 配置日志级别

```python
from astrbot.core import LogManager, logger

# 根据配置设置日志级别
config = {
    "log_level": "DEBUG",
    "log_file_enable": True,
    "log_file_path": "logs/astrbot.log",
    "log_file_max_mb": 50,
}

LogManager.configure_logger(logger, config)
```

### 7.2 配置 Trace 日志

```python
# 启用 Trace 日志文件
config = {
    "trace_enable": True,
    "trace_log_enable": True,
    "trace_log_path": "logs/astrbot.trace.log",
    "trace_log_max_mb": 30,
}

LogManager.configure_trace_logger(config)
```

### 7.3 日志过滤器

LogManager 自动添加以下过滤器：

| 过滤器 | 功能 | 输出示例 |
|-------|------|--------|
| **PluginFilter** | 标记日志来源（Core/Plug） | `[Core]` 或 `[Plug]` |
| **FileNameFilter** | 修改文件名格式 | `folder.filename` |
| **LevelNameFilter** | 4 字母缩写 | `DBUG`, `INFO`, `WARN`, `ERRO`, `CRIT` |
| **AstrBotVersionTagFilter** | 在 WARNING 及以上追加版本 | `[v4.14.4]` |

---

## 8. 日志配置管理

### 8.1 配置文件路径

- **配置文件**: `data/cmd_config.json`
- **默认配置**: `astrbot/core/config/default.py`
- **编辑方式**: 
  1. 直接编辑 JSON 文件
  2. 通过 Dashboard 管理面板修改（未来功能）

### 8.2 配置更新

配置更改后，需要重启应用以生效（或通过 API 动态更新）。

### 8.3 环境变量支持

**根目录自定义**（可选）：
```bash
export ASTRBOT_ROOT=/path/to/root
# 数据目录将为 /path/to/root/data
```

---

## 9. 代码示例汇总

### 9.1 获取日志记录器

```python
from astrbot.core import logger

# 已配置的全局日志记录器
logger.info("Message")
logger.debug("Debug message")
logger.warning("Warning")
logger.error("Error")
logger.critical("Critical error")
```

### 9.2 创建自定义日志记录器

```python
from astrbot.core import LogManager

# 获取命名日志记录器
plugin_logger = LogManager.GetLogger("my_plugin")
plugin_logger.info("Plugin message")
```

### 9.3 发起 Trace 追踪

```python
from astrbot.core.utils.trace import TraceSpan

span = TraceSpan(
    name="custom_operation",
    umo="custom_type",
    sender_name="CustomOperator",
    message_outline="Operation description"
)

span.record("stage1", param1="value1")
span.record("stage2", param2="value2", status="success")
```

### 9.4 订阅日志流（自定义）

```python
import asyncio
from astrbot.core import LogBroker

# 从 LogBroker 获取日志队列
log_broker = app.log_broker  # 从应用上下文获取

async def listen_logs():
    queue = log_broker.register()
    try:
        while True:
            log_entry = await queue.get()
            print(f"[{log_entry['level']}] {log_entry['data']}")
    finally:
        log_broker.unregister(queue)

# 运行监听器
asyncio.run(listen_logs())
```

---

## 10. 常见问题和最佳实践

### 10.1 为什么文件日志默认禁用？

- 性能考虑（避免磁盘 I/O 开销）
- 容器环境中不需要持久化
- 大多数用户通过 Dashboard 查看日志

### 10.2 启用文件日志的步骤

1. 编辑 `data/cmd_config.json`：
   ```json
   {
     "log_file_enable": true,
     "log_file_path": "logs/astrbot.log",
     "log_file_max_mb": 50
   }
   ```
2. 重启 AstrBot 应用
3. 日志将写入 `data/logs/astrbot.log`

### 10.3 日志级别选择

- **DEBUG**: 开发调试，包含所有详细信息
- **INFO**: 生产环境推荐，记录重要事件
- **WARNING**: 只记录警告和错误
- **ERROR**: 仅记录错误
- **CRITICAL**: 仅记录严重错误

### 10.4 Trace ID 用于群分析追踪

对于"QQ 群日常分析"场景：
- 每个群的分析请求都有唯一的 `span_id`
- 可通过此 ID 追踪整个分析流程
- 涉及多群并发时日志清晰分离

**查询示例**：
```bash
# 查找 span_id 相关的所有日志
grep "span_id: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx" data/logs/astrbot.trace.log
```

### 10.5 性能考虑

- **日志缓存**: 最多 500 条，超出自动淘汰（先进先出）
- **SSE 连接**: 断网自动重连，支持日志补发
- **文件轮转**: 单个文件超过 20MB（可配置）自动轮转

---

## 11. 相关文件速查表

| 功能 | 文件路径 |
|------|--------|
| 日志核心逻辑 | `astrbot/core/log.py` |
| 日志管理器 | `astrbot/core/log.py` (LogManager 类) |
| Trace 系统 | `astrbot/core/utils/trace.py` |
| Dashboard API | `astrbot/dashboard/routes/log.py` |
| 默认配置 | `astrbot/core/config/default.py` |
| 路径工具 | `astrbot/core/utils/astrbot_path.py` |
| Dashboard Console UI | `dashboard/src/views/ConsolePage.vue` |
| 日志显示器组件 | `dashboard/src/components/shared/ConsoleDisplayer.vue` |
| Trace UI | `dashboard/src/views/TracePage.vue` |
| 公共 Store | `dashboard/src/stores/common.js` |

---

## 12. 总结

### 日志查看的完整流程

1. **应用启动**
   - LogBroker 初始化
   - LogQueueHandler 连接到日志记录器

2. **日志产生**
   - 应用或插件调用 `logger.info()` 等方法
   - LogQueueHandler 拦截日志记录

3. **日志分发**
   - LogBroker.publish() 添加到缓存
   - 分发给所有订阅者（Dashboard SSE、Trace 日志等）

4. **用户查看**
   - **Dashboard Console**: 实时看到日志
   - **REST API**: 获取历史日志或 SSE 流
   - **文件**: 直接查看 `data/logs/astrbot.log`

5. **Trace 追踪**
   - 创建 TraceSpan 记录请求链路
   - Dashboard `/trace` 实时查看
   - 或通过 span_id 在文件中查询

### 推荐使用方式

- **开发调试**: Dashboard `/console` 页面
- **生产监控**: 启用文件日志 + 日志收集系统
- **问题诊断**: 通过 span_id 追踪完整请求链路
- **群分析**: 在日志中包含 group_id，便于后续查询

---

*本文档基于 AstrBot v4.14.4 代码分析生成。*
