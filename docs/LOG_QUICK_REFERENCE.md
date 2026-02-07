# TraceID 日志增强指南 + AstrBot 日志查看

> **核心观点**：`contextvars + logging.Filter` 方案是对 AstrBot logger 的增强，不是替换。日志仍通过 AstrBot 输出，只是自动注入 trace_id。

---

## 🔍 日志查看入口（三种方式）

### 1️⃣ 控制台输出（最简单，开发环境推荐）

**启动 AstrBot 后，直接在终端看日志**

```bash
python main.py

# 输出示例：
[10:30:45] [Plug] [INFO ] [group_daily:45]: [123456789-1707292800] 开始分析群
[10:30:46] [Plug] [INFO ] [group_daily:46]: [123456789-1707292800] 获取 256 条消息
[10:30:47] [Plug] [INFO ] [group_daily:47]: [123456789-1707292800] 话题分析完成
[10:30:48] [Plug] [ERROR] [group_daily:50]: [123456789-1707292800] LLM 超时
                                            ↑
                                      TraceID（自动注入）
```

**优点**：
- ✅ 零配置，启动即可看
- ✅ 实时显示，彩色输出
- ✅ 容易识别错误

### 2️⃣ 日志文件（生产环境标配）

**在 `astrbot_config.yml` 中启用文件日志**

```yaml
log_file_enable: true
log_file_path: "logs/astrbot.log"    # 日志文件路径
log_file_max_mb: 20                  # 文件大小限制（轮转）
```

**查看方式**

```bash
# Linux/Mac 实时查看
tail -f logs/astrbot.log

# Windows PowerShell 实时查看
Get-Content -Path logs/astrbot.log -Wait

# 搜索特定群的所有日志
grep "123456789" logs/astrbot.log

# 查看最后 100 行
tail -100 logs/astrbot.log
```

**优点**：
- ✅ 永久保存
- ✅ 支持搜索和分析
- ✅ 生产环境必须

### 3️⃣ AstrBot Dashboard（最舒服，Web 界面）

**方式 A：AstrBot 内置 Dashboard（如果启用了）**

```
访问：http://localhost:8000
→ 日志 / Logs 菜单
→ 可看实时日志流
```

**方式 B：Astrbot-dashboard 独立工具**

```bash
# 安装独立的 dashboard 包
pip install astrbot-dashboard

# 启动（连接本地 AstrBot）
astrbot-dashboard

# 浏览器打开
# http://localhost:6185/#/console
```

**优点**：
- ✅ Web 界面直观
- ✅ 实时流式显示
- ✅ 支持过滤和搜索

---

## ✅ 为什么使用 contextvars + logging.Filter？

### 核心原因：**自动 TraceID 注入**

```
现状问题：                          使用 contextvars 后：
────────────────────────────────────────────────────
logger.info("开始")                logger.info("开始")
logger.info("获取消息")     →      logger.info("获取消息")
logger.error("超时")               logger.error("超时")

输出：                              输出：
[INFO] 开始                        [trace_id:123] [INFO] 开始
[INFO] 获取消息                    [trace_id:123] [INFO] 获取消息
[ERROR] 超时                       [trace_id:123] [ERROR] 超时

❌ 100 个群并发时看不出            ✅ 清晰看出所有日志属于
谁的日志在哪里                     同一个分析任务！
```

### 有没有利用 AstrBot 现有日志？

**完全利用了！** 这是在 AstrBot logger 上添加一层装饰器：

```
你的代码: logger.info("message")
        ↓
    [TraceIDFilter]（新增）← 自动注入 trace_id
        ↓
    [AstrBot Logger]（已有）
        ├─ ColoredFormatter
        ├─ StreamHandler（控制台）
        └─ RotatingFileHandler（文件）
```

### 代码实现（简化版）

```python
# src/utils/trace.py
import contextvars
import logging
from astrbot.api import logger

# 全局 ContextVar
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar('trace_id', default='')

# 自定义 Filter
class TraceIDFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = _trace_id.get('') or 'no-trace'
        return True

# 注册到 AstrBot logger（在插件初始化时）
logger.addFilter(TraceIDFilter())

# 使用（在分析开始处）
async def analyze_group(group_id: str):
    import time
    
    # 设置 trace_id
    _trace_id.set(f"{group_id}-{int(time.time())}")
    
    try:
        logger.info("开始分析")  # 自动包含 trace_id
        # ... 分析逻辑
    finally:
        _trace_id.set('')  # 清理
```

### 输出效果

```bash
$ tail -f logs/astrbot.log | grep trace_id

[123456789-1707292800] [10:30:45] [Plug] [INFO ] [group_daily:45]: 开始分析群
[123456789-1707292800] [10:30:46] [Plug] [INFO ] [group_daily:46]: 获取 256 条消息
[123456789-1707292800] [10:30:47] [Plug] [INFO ] [group_daily:47]: 话题分析完成
[123456789-1707292800] [10:30:48] [Plug] [ERROR] [group_daily:50]: LLM 超时
```

---

## 🏗️ 架构流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    AstrBot 应用                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  核心组件/插件                                                │
│  │                                                            │
│  ├─→ logger.info("message")                                 │
│      └─→ logger.error("error")                              │
│                                                               │
│          ▼                                                    │
│  ┌──────────────────────────────────────┐                   │
│  │  LogQueueHandler (日志处理器)        │                   │
│  │  接收 logging.LogRecord              │                   │
│  └──────────────────────────────────────┘                   │
│          ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         LogBroker (日志代理)                          │   │
│  │  - log_cache: deque(maxlen=500)  [环形缓冲区]       │   │
│  │  - subscribers: List[Queue]      [订阅者队列]       │   │
│  │                                                       │   │
│  │  publish(log_entry):                                │   │
│  │    1. 添加到 log_cache                             │   │
│  │    2. 分发给所有 subscribers                       │   │
│  └──────────────────────────────────────────────────────┘   │
│          │                                                    │
│          ├──────────────────┬─────────────────────────────┐  │
│          ▼                  ▼                             ▼  │
│   ┌─────────────┐  ┌───────────────┐    ┌──────────────┐   │
│   │ Dashboard   │  │ Trace Logger  │    │ 其他订阅者   │   │
│   │ SSE 连接    │  │ (可选)        │    │ (可选)       │   │
│   │ (实时推送)  │  │ (文件/内存)   │    │              │   │
│   └─────────────┘  └───────────────┘    └──────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 数据输出                                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ 1. Dashboard UI (/:console)                                 │
│    - 实时日志显示                                            │
│    - 级别过滤                                               │
│                                                               │
│ 2. 日志文件 (可选)                                           │
│    - data/logs/astrbot.log                                 │
│    - data/logs/astrbot.trace.log                           │
│                                                               │
│ 3. 浏览器 Memory                                            │
│    - SSE 缓存 (断网重连补发)                               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 文件位置速查

| 类型 | 位置 | 启用方式 |
|------|------|--------|
| **普通日志** | `data/logs/astrbot.log` | `log_file_enable: true` |
| **Trace 日志** | `data/logs/astrbot.trace.log` | `trace_log_enable: true` |
| **配置文件** | `data/cmd_config.json` | 直接编辑 |
| **数据目录** | `data/` | 环境变量 `ASTRBOT_ROOT` |

---

## 🔧 配置项清单

### 日志配置（最常用）

```json
{
  "log_level": "INFO",                           // DEBUG|INFO|WARNING|ERROR|CRITICAL
  "log_file_enable": false,                      // 启用文件日志
  "log_file_path": "logs/astrbot.log",          // 相对于 data/ 目录
  "log_file_max_mb": 20,                         // 单个文件最大大小
  
  "trace_enable": false,                         // 启用 Trace 记录
  "trace_log_enable": false,                     // 启用 Trace 文件日志
  "trace_log_path": "logs/astrbot.trace.log",   // Trace 文件位置
  "trace_log_max_mb": 20
}
```

---

## 💻 代码使用速查

### 记录日志（最常用）

```python
from astrbot.core import logger

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")
```

### Trace 追踪（链路追踪）

```python
from astrbot.core.utils.trace import TraceSpan

span = TraceSpan(
    name="operation_name",
    sender_name="ComponentA",
    message_outline="Brief description"
)

span.record("stage1", key1="value1")
span.record("stage2", key2="value2")
```

### 订阅日志流（高级）

```python
import asyncio

async def listen_logs(log_broker):
    queue = log_broker.register()
    try:
        while True:
            log_entry = await queue.get()
            print(f"{log_entry['level']}: {log_entry['data']}")
    finally:
        log_broker.unregister(queue)
```

---

## 🚀 常见操作

### ❓ 如何启用文件日志？

1. 打开 `data/cmd_config.json`
2. 修改：
   ```json
   "log_file_enable": true,
   "log_file_path": "logs/astrbot.log"
   ```
3. 重启应用

### ❓ 如何查看特定群的日志？

```bash
# 方式 1: Dashboard 中搜索 group_id
http://localhost:6185/#/console

# 方式 2: 命令行查询
grep "QQGroup:123456789" data/logs/astrbot.log
```

### ❓ 如何用 span_id 追踪完整请求？

```bash
# Trace 日志包含 span_id，可追踪单个请求的全生命周期
grep "span_id.*abc-123-def" data/logs/astrbot.trace.log

# 或在 Dashboard 的 /trace 页面实时查看
```

### ❓ 日志缓存大小是多少？

- **内存缓存**: 最近 500 条日志（deque with maxlen=500）
- **Dashboard 前端缓存**: 最近 1000 条日志
- **文件日志**: 单个文件 20MB，自动轮转（3 个备份）

### ❓ 日志是否会自动删除？

- **内存缓存**: 自动淘汰（先进先出，保持最近 500 条）
- **文件日志**: 不自动删除，需手动管理或配置轮转
- **Dashboard 前端**: 页面关闭后清空

---

## 📊 日志格式示例

### Console 日志输出

```
[12:34:56] [Core] [INFO] [astrbot.py:123]: Application started successfully
[12:34:57] [Plug] [WARN] [plugin.py:45]: Missing dependency: requests
[12:35:00] [Core] [ERRO] [error.py:78]: Connection timeout to server [v4.14.4]
```

格式：`[时间] [来源] [级别] [文件:行号]: 消息`

### Trace JSON 日志

```json
[2024-01-01 12:34:56] {"type":"trace","span_id":"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx","name":"group_analysis","sender_name":"QQGroup:123456789","action":"start","fields":{"group_id":"123456789","step":"initialization"}}
```

---

## 🎨 日志级别和颜色

| 级别 | 缩写 | 颜色 | 含义 |
|------|------|------|------|
| DEBUG | DBUG | 🟢 绿色 | 调试信息 |
| INFO | INFO | 🔵 青色 | 一般信息 |
| WARNING | WARN | 🟡 黄色 | 警告信息 |
| ERROR | ERRO | 🔴 红色 | 错误信息 |
| CRITICAL | CRIT | 🟣 紫色 | 严重错误 |

---

## 📈 性能指标

| 项目 | 值 | 说明 |
|------|-----|------|
| 日志缓存大小 | 500 条 | 环形缓冲区 |
| Dashboard 前端缓存 | 1000 条 | 浏览器内存 |
| SSE 队列大小 | 510 条 | maxsize = CACHED_SIZE + 10 |
| 日志文件大小 | 20MB | 单个文件，可配置 |
| 备份文件数 | 3 个 | 自动轮转 |
| SSE 连接超时 | None | 永不超时 |

---

## 🔐 安全相关

### 日志中的敏感信息

```python
# ❌ 不要直接记录密钥
logger.info(f"API key: {api_key}")

# ✅ 使用脱敏
logger.info(f"API key: {api_key[:8]}...")

# ✅ 或使用占位符
logger.info(f"Using API key: ***")
```

### Dashboard 访问认证

- 默认用户名：`astrbot`
- 默认密码：（MD5 哈希，需在配置中修改）
- JWT Token：用于 API 认证

---

## 🔗 相关链接

| 资源 | 位置 |
|------|------|
| 完整文档 | `LOG_VIEWING_RESEARCH.md` |
| 日志实现 | `astrbot/core/log.py` |
| Trace 系统 | `astrbot/core/utils/trace.py` |
| Dashboard API | `astrbot/dashboard/routes/log.py` |
| 前端组件 | `dashboard/src/components/shared/ConsoleDisplayer.vue` |
| 默认配置 | `astrbot/core/config/default.py` |

---

## ✅ 检查清单

### 开发调试

- [ ] Dashboard 可以实时看到日志
- [ ] 日志级别设置为 DEBUG
- [ ] Trace 追踪已启用（if needed）

### 生产部署

- [ ] 日志级别设置为 INFO
- [ ] 文件日志已启用（for persistence）
- [ ] 日志轮转已配置
- [ ] 监控系统已连接

### 问题诊断

- [ ] 日志中包含 span_id（for tracing）
- [ ] 时间戳正确（for correlation）
- [ ] 日志级别适当（not too verbose）

---

*最后更新：2024年 | AstrBot v4.14.4*
