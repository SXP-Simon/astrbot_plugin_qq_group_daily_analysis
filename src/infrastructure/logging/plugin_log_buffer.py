"""
群分析插件专用内存日志缓冲与标签提取器
提供高性能环形队列日志存储、语义化标签提取与多维度筛选能力。
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PluginLogEntry:
    id: str
    timestamp: float
    time_str: str
    level: str
    logger_name: str
    trace_id: str | None
    stage: str | None
    tag: str
    message: str
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PluginLogBuffer(logging.Handler):
    """
    专用插件日志处理器，挂载到 logging 捕获群分析插件全链路日志
    """

    TAG_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
        (
            "LLM",
            "大模型调用",
            re.compile(
                r"(llm|analyzer|prompt|openai|deepseek|claude|qwen|gpt|token)", re.I
            ),
        ),
        (
            "Album",
            "群相册",
            re.compile(r"(album|相册|qun_album|group_album)", re.I),
        ),
        (
            "OneBot",
            "OneBot协议",
            re.compile(r"(onebot|napcat|llonebot|aiocqhttp|gocq)", re.I),
        ),
        (
            "QQOfficial",
            "QQ官方机器人",
            re.compile(r"(qq_official|botpy|c2c|guild)", re.I),
        ),
        ("Telegram", "Telegram平台", re.compile(r"(telegram|telethon)", re.I)),
        ("Discord", "Discord平台", re.compile(r"(discord|discord_bot)", re.I)),
        (
            "Scheduler",
            "定时与调度",
            re.compile(r"(scheduler|cron|job|timer|incremental)", re.I),
        ),
        (
            "Resilience",
            "容错与重试",
            re.compile(r"(resilience|retry|limiter|circuit|lock|reaper)", re.I),
        ),
        (
            "Comic",
            "群漫画",
            re.compile(
                r"(comic|漫画|分镜|drawing|storyboard|grok2api|big_banana)", re.I
            ),
        ),
        (
            "Render",
            "报告与长图",
            re.compile(r"(render|template|html|image|report|playwright|canvas)", re.I),
        ),
        (
            "WebUI",
            "控制台交互",
            re.compile(r"(webui|bridge|api_|dashboard|route)", re.I),
        ),
        ("Trace", "链路追踪", re.compile(r"(trace|span|context_metric)", re.I)),
    ]

    STAGE_NAMES = {
        "FETCH_MESSAGES": "拉取聊天记录",
        "CLEAN_MESSAGES": "消息清洗过滤",
        "STATS_ANALYSIS": "基础统计分析",
        "LLM_ANALYSIS": "大模型话题与画像分析",
        "SAVE_SUMMARY": "历史记录持久化",
        "RENDER_REPORT": "报告图片渲染与发送",
        "COMIC_STORYBOARD": "漫画分镜提示词提取",
        "COMIC_DRAWING": "漫画长图生成与投递",
        "CRASH_RECOVERY": "异常终止恢复",
    }

    def __init__(self, max_capacity: int = 2000):
        super().__init__()
        self.max_capacity = max_capacity
        self._buffer: deque[PluginLogEntry] = deque(maxlen=max_capacity)
        self._counter = 0
        self._listeners: set[Any] = set()

    def register_listener(self, listener: Any) -> None:
        """注册日志实时推送监听器"""
        self._listeners.add(listener)

    def unregister_listener(self, listener: Any) -> None:
        """注销日志实时推送监听器"""
        self._listeners.discard(listener)

    def record_log(
        self,
        level: str,
        msg: str,
        trace_id: str | None = None,
        logger_name: str = "plugin",
    ) -> PluginLogEntry:
        """主动记录日志条目并实时推送给前端监听器"""
        self._counter += 1
        now = time.time()
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        msecs = int((now - int(now)) * 1000)
        full_time_str = f"{time_str}.{msecs:03d}"

        # 解析 TraceID：优先从参数取，其次从 TraceContext 上下文取，最后从日志文本中提取
        if not trace_id:
            try:
                from ...shared.trace_context import TraceContext

                ctx = TraceContext.current()
                if ctx and ctx.trace_id:
                    trace_id = ctx.trace_id
            except Exception:
                pass

        if not trace_id:
            trace_match = re.search(
                r"\[(manual|incr|group|web_manual|report|[a-zA-Z0-9_\-]+)_[a-zA-Z0-9_\-]+\]",
                msg,
            )
            if trace_match:
                trace_id = trace_match.group(0).strip("[]")

        # 语义化标签分类
        tag = "General"
        for tag_key, _, pattern in self.TAG_PATTERNS:
            if pattern.search(msg) or pattern.search(logger_name):
                tag = tag_key
                break

        # 阶段解析
        stage = None
        for stage_code, stage_label in self.STAGE_NAMES.items():
            if stage_code in msg or stage_label in msg:
                stage = stage_label
                break

        entry = PluginLogEntry(
            id=f"log_{self._counter}",
            timestamp=now,
            time_str=full_time_str,
            level=level.upper(),
            logger_name=logger_name,
            trace_id=trace_id,
            stage=stage,
            tag=tag,
            message=msg,
            raw=f"[{full_time_str}] [{level.upper()}] [{logger_name}]: {msg}",
        )
        self._buffer.append(entry)

        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception:
                pass

        return entry

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            logger_name = record.name

            # 仅捕获群分析插件内部日志或带标识日志
            is_plugin_log = (
                "astrbot_plugin_qq_group_daily_analysis" in logger_name
                or "daily_analysis" in logger_name
                or "[群分析插件]" in msg
                or hasattr(record, "trace_id")
            )
            if not is_plugin_log:
                return

            trace_id = getattr(record, "trace_id", None)
            self.record_log(
                level=record.levelname,
                msg=msg,
                trace_id=trace_id,
                logger_name=logger_name.split(".")[-1]
                if "." in logger_name
                else logger_name,
            )
        except Exception:
            self.handleError(record)

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        level: str | None = None,
        trace_id: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """按条件多维度筛选日志列表（按时间倒序）"""
        results: list[PluginLogEntry] = []
        target_level = level.upper().strip() if level else None
        target_trace = trace_id.strip() if trace_id else None
        target_tag = tag.strip() if tag else None
        search_kw = search.strip().lower() if search else None

        for entry in reversed(self._buffer):
            if target_level and entry.level != target_level:
                continue
            if target_trace and entry.trace_id != target_trace:
                continue
            if target_tag and entry.tag.lower() != target_tag.lower():
                continue
            if search_kw:
                if (
                    search_kw not in entry.message.lower()
                    and search_kw not in (entry.trace_id or "").lower()
                    and search_kw not in entry.logger_name.lower()
                ):
                    continue
            results.append(entry)

        total = len(results)
        paged = results[offset : offset + limit]
        return [e.to_dict() for e in paged], total

    def get_trace_logs(self, trace_id: str) -> list[dict[str, Any]]:
        """获取特定 TraceID 的全部日志记录"""
        return [
            e.to_dict()
            for e in self._buffer
            if e.trace_id == trace_id or (trace_id and trace_id in e.message)
        ]

    def clear(self) -> None:
        """清空内存缓冲"""
        self._buffer.clear()


# 全局单例日志缓冲器
global_log_buffer = PluginLogBuffer()
