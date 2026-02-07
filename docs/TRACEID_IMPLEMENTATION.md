# TraceID 实现代码示例

这个文件展示如何在插件中实现 contextvars + logging.Filter 方案。

## 文件结构

```
astrbot_plugin_qq_group_daily_analysis/
├── src/
│   ├── utils/
│   │   ├── trace.py          # ← 新增：TraceID 相关
│   │   └── helpers.py
│   ├── core/
│   │   └── config.py
│   └── ...
├── main.py                     # ← 需要修改：注册 Filter
└── ...
```

## 1. 新增文件：src/utils/trace.py

```python
"""
TraceID 追踪工具模块
提供分布式追踪的 trace_id 上下文管理
"""

import contextvars
import logging
import time
from astrbot.api import logger

# ============ ContextVar 定义 ============
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'trace_id',
    default=''
)


# ============ Filter 实现 ============
class TraceIDFilter(logging.Filter):
    """
    将 trace_id 自动注入到日志记录
    
    使用方式：
        logger.addFilter(TraceIDFilter())
        # 之后所有日志的 record 对象都会有 trace_id 属性
    """

    def filter(self, record):
        """添加 trace_id 到日志记录"""
        trace_id = _trace_id.get('')
        record.trace_id = trace_id if trace_id else 'no-trace'
        return True


# ============ 接口函数 ============
def set_trace_id(group_id: str, timestamp: int = None) -> str:
    """
    设置当前协程的 trace_id
    
    Args:
        group_id: 群 ID
        timestamp: 时间戳（如果为 None 则使用当前时间）
    
    Returns:
        生成的 trace_id 字符串
    
    Example:
        >>> trace_id = set_trace_id("123456789")
        >>> logger.info("分析开始")  # 日志自动包含 trace_id
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    trace_id = f"{group_id}-{timestamp}"
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> str:
    """获取当前协程的 trace_id"""
    return _trace_id.get('no-trace')


def clear_trace_id():
    """清理当前协程的 trace_id"""
    _trace_id.set('')


def with_trace_id(group_id: str):
    """
    上下文管理器：自动管理 trace_id 的生命周期
    
    Example:
        >>> from src.utils.trace import with_trace_id
        >>> 
        >>> async def analyze_group(group_id: str):
        ...     with with_trace_id(group_id):
        ...         logger.info("开始分析")  # 自动包含 trace_id
        ...         # ...
        ...         logger.info("分析完成")
        ...     # 退出时自动清理 trace_id
    """
    class TraceContextManager:
        def __init__(self, group_id):
            self.group_id = group_id
            self.trace_id = None
        
        def __enter__(self):
            self.trace_id = set_trace_id(self.group_id)
            return self.trace_id
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            clear_trace_id()
            return False
    
    return TraceContextManager(group_id)


# ============ 初始化函数 ============
def setup_trace_logging():
    """
    初始化 TraceID 日志追踪
    
    在插件启动时调用一次即可：
        from src.utils.trace import setup_trace_logging
        setup_trace_logging()
    """
    # 注册 Filter 到 AstrBot logger
    trace_filter = TraceIDFilter()
    
    # 检查是否已注册（避免重复注册）
    for existing_filter in logger.filters:
        if isinstance(existing_filter, TraceIDFilter):
            return  # 已经注册过了
    
    logger.addFilter(trace_filter)
    logger.info("[Trace] TraceID 日志追踪已启用")
```

## 2. 修改文件：main.py（插件主文件）

在 `__init__` 方法中添加初始化：

```python
# main.py
from src.utils.trace import setup_trace_logging

class QQGroupDailyAnalysis(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # ... 其他初始化代码 ...
        
        # ← 新增：初始化 TraceID 追踪
        setup_trace_logging()
        
        # ... 其他初始化代码 ...
```

## 3. 修改文件：src/scheduler/auto_scheduler.py

在群分析方法中使用 TraceID：

```python
# auto_scheduler.py
from src.utils.trace import set_trace_id, clear_trace_id, with_trace_id

class AutoScheduler:
    # ... 其他方法 ...
    
    async def _perform_auto_analysis_for_group(self, group_id: str):
        """为指定群执行自动分析"""
        
        # ← 方案 1：使用上下文管理器（推荐）
        with with_trace_id(group_id):
            try:
                logger.info(f"开始为群 {group_id} 执行自动分析")
                # ... 分析逻辑，所有 logger 调用都自动包含 trace_id ...
            except Exception as e:
                logger.error(f"群 {group_id} 自动分析失败: {e}")
        
        # ← 方案 2：手动设置/清理（传统方式）
        # set_trace_id(group_id)
        # try:
        #     logger.info(f"开始为群 {group_id} 执行自动分析")
        #     # ... 分析逻辑 ...
        # finally:
        #     clear_trace_id()
```

## 4. 修改文件：src/utils/helpers.py

在 `MessageAnalyzer` 中使用 TraceID：

```python
# helpers.py
from src.utils.trace import with_trace_id

class MessageAnalyzer:
    async def analyze_messages(
        self, 
        messages: list[dict], 
        group_id: str, 
        unified_msg_origin: str = None
    ) -> dict:
        """完整的消息分析流程"""
        
        with with_trace_id(group_id):
            try:
                logger.info("开始消息分析")
                
                # 基础统计
                statistics = await asyncio.to_thread(...)
                logger.info(f"统计完成：{len(messages)} 条消息")
                
                # LLM 分析
                topics, user_titles, golden_quotes, token_usage = \
                    await self.llm_analyzer.analyze_all_concurrent(...)
                logger.info(f"LLM 分析完成")
                
                return {
                    "statistics": statistics,
                    "topics": topics,
                    "user_titles": user_titles,
                }
            except Exception as e:
                logger.error(f"消息分析失败: {e}")
                return None
```

## 5. 日志输出效果

启动后，日志会自动包含 trace_id：

```bash
$ python main.py

[10:30:45] [Plug] [INFO ] [auto_scheduler:100]: [123456789-1707292800] 开始为群 123456789 执行自动分析
[10:30:45] [Plug] [INFO ] [message_handler:50]: [123456789-1707292800] 开始获取消息
[10:30:46] [Plug] [INFO ] [message_handler:100]: [123456789-1707292800] 获取成功，共 256 条消息
[10:30:47] [Plug] [INFO ] [helpers:200]: [123456789-1707292800] 开始消息分析
[10:30:48] [Plug] [INFO ] [llm_analyzer:300]: [123456789-1707292800] 开始 LLM 分析
[10:30:50] [Plug] [INFO ] [llm_analyzer:350]: [123456789-1707292800] LLM 分析完成
[10:30:51] [Plug] [INFO ] [report_generator:400]: [123456789-1707292800] 报告生成中
[10:30:53] [Plug] [INFO ] [auto_scheduler:450]: [123456789-1707292800] 分析完成，耗时 8s
```

## 6. 查看日志

### 终端实时查看

```bash
# 看所有日志
tail -f logs/astrbot.log

# 看特定群的日志
tail -f logs/astrbot.log | grep "123456789"

# 或使用 grep 搜索
grep "123456789-1707292800" logs/astrbot.log
```

### 按 TraceID 追踪完整链路

```bash
# 获取某个 trace_id 的所有日志
grep "123456789-1707292800" logs/astrbot.log

# 按时间戳统计分析耗时
# trace_id 格式 {group_id}-{start_timestamp}
# 可从日志时间戳对比，计算耗时
```

## 7. 成本统计

| 项目 | 工作量 | 难度 |
|------|--------|------|
| 新增 trace.py | ~80 行 | 低 |
| 修改 main.py | 3 行 | 低 |
| 修改 auto_scheduler.py | ~10 行 | 低 |
| 修改 helpers.py | ~5 行 | 低 |
| 修改其他文件 | 可选（向后兼容） | 低 |
| **总计** | **~100 行** | **低** |

## 8. 向后兼容性

✅ **完全向后兼容**

- 现有代码无需改动
- 新增代码仅在初始化时注册 Filter
- 所有日志输出不变，仅在 record 对象中添加 trace_id 字段
- 如果日志格式未修改，trace_id 不会显示，但在代码中可以访问

## 9. 扩展应用

### 应用 1：性能分析

```python
from src.utils.trace import get_trace_id
import time

start = time.time()
# ... 某个操作 ...
elapsed = time.time() - start
logger.info(f"操作耗时 {elapsed:.2f}s")
# 日志自动包含 trace_id，可后续统计所有群的平均耗时
```

### 应用 2：错误统计

```bash
# 找出所有失败的 trace_id
grep "ERROR" logs/astrbot.log | awk -F'[]' '{print $2}' | sort | uniq -c

# 输出：
#    3 123456789-1707292800
#    2 987654321-1707292801
# → 表示这两个分析任务各失败了 3 次和 2 次
```

### 应用 3：分布式追踪

如果以后扩展到分布式部署，trace_id 可以传递到其他服务：

```python
# 跨服务调用时传递 trace_id
async def call_external_service(url, data):
    headers = {"X-Trace-ID": get_trace_id()}
    return await http_client.post(url, json=data, headers=headers)
```

