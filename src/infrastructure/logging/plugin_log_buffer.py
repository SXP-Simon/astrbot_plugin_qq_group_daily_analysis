"""
群分析插件专用内存日志缓冲与标签提取器
提供高性能环形队列日志存储、语义化标签提取与多维度筛选能力。
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, ClassVar

from ...shared.constants import AnalysisStage

if TYPE_CHECKING:
    from collections.abc import Callable


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
    location: str | None = None
    function_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PluginLogBuffer:
    """专用插件日志处理器，捕获群分析插件全链路日志并提供内存环形队列缓冲"""

    # 先按明确的调用模块分类，避免正文里的模型名、群名或错误详情改变所属功能。
    SOURCE_TAGS: ClassVar[dict[str, re.Pattern[str]]] = {
        key: re.compile(pattern, re.I)
        for key, pattern in {
            "Resources": r"(typst_fonts|template_resources|template_asset_catalog|avatar_service|image_cache|template_resource_routes)",
            "Typst": r"typst_.*",
            "T2I": r"(custom_t2i_.*|t2i_.*|image_rendering)",
            "Comic": r"(comic_.*|drawing_.*|external_drawing_adapter)",
            "Album": r".*album.*",
            "Satori": r"satori_.*",
            "Discord": r"discord_.*",
            "Telegram": r"telegram_.*",
            "QQOfficial": r"(qq_official_.*|qq_markdown_images)",
            "OneBot": r"(onebot_.*|napcat_.*|llbot_driver|standard_driver|driver_factory)",
            "Platform": r"(bot_manager|command_prefix|stop_signal)",
            "Config": r"(config_manager|config_migrator|config_routes|settings_command_handler|upgrade_.*)",
            "Storage": r"(.*_store|history_manager|history_repository|astrbot_history_writer|data_management_routes)",
            "Messages": r"(message_processing_service|.*message_converter)",
            "Incremental": r"incremental_.*",
            "Scheduler": r"(auto_scheduler|target_resolver)",
            "Resilience": r"(resilience|task_guard|crash_recovery_service)",
            "Tasks": r"(analysis_application_service|analysis_recovery_service|analysis_trigger_service|analysis_command_handler|pipeline_context|active_task_manager|task_routes)",
            "Dispatch": r"(message_sender|dispatcher|group_file_manager)",
            "LLM": r"(.*analyzer|llm_utils|json_utils)",
            "Trace": r"(trace_context|render_trace|trace_routes)",
            "Render": r"(generators|templates|template_installer|template_utils|render_.*|markdown_report_generator|profile_mappings|report_routes|template_routes)",
            "WebUI": r"(plugin_page_bridge|log_routes)",
        }.items()
    }

    # 没有明确来源的旧日志按关键词兜底；通用项只用于展示筛选入口。
    TAG_PATTERNS: ClassVar[list[tuple[str, str, re.Pattern[str]]]] = [
        (key, label, re.compile(pattern, re.I))
        for key, label, pattern in [
            (
                "Resources",
                "字体与素材",
                r"(字体|字库|素材|头像|\bfonts?\b|\bcdn\b|template_resources|avatar)",
            ),
            ("Typst", "Typst 本地排版", r"typst"),
            ("T2I", "T2I 网页转图片", r"(t2i|text2img|文生图|截图超时)"),
            (
                "Comic",
                "群漫画",
                r"(comic|漫画|分镜|drawing|storyboard|grok2api|big_banana)",
            ),
            ("Album", "群相册", r"(album|相册)"),
            ("Satori", "Satori 平台", r"satori"),
            ("Discord", "Discord 平台", r"discord"),
            ("Telegram", "Telegram 平台", r"(telegram|telethon)"),
            (
                "QQOfficial",
                "QQ 官方机器人",
                r"(qq_official|qqofficial|QQ官方|botpy|\bc2c\b)",
            ),
            ("OneBot", "OneBot 协议", r"(onebot|napcat|llonebot|aiocqhttp|gocq)"),
            ("Platform", "平台连接与鉴权", r"(BotManager|平台连接|平台鉴权|平台实例)"),
            ("Config", "配置与升级", r"(config|配置|升级保护)"),
            (
                "Storage",
                "历史与存储",
                r"(sqlite|checkpoint|检查点|持久化|历史存储|备份)",
            ),
            (
                "Messages",
                "消息采集与清洗",
                r"(消息采集|消息清洗|消息过滤|缓存消息|message_processing|message_converter)",
            ),
            ("Incremental", "增量分析", r"(incremental|增量)"),
            ("Scheduler", "定时与调度", r"(scheduler|cron|timer|定时|调度)"),
            (
                "Resilience",
                "容错与重试",
                r"(resilience|retry|limiter|circuit|\block\b|reaper|重试|熔断|限流|互斥)",
            ),
            ("Tasks", "任务执行与恢复", r"(任务|续跑|恢复分析|取消分析|停止分析)"),
            ("Dispatch", "消息发送与上传", r"(dispatch|投递|发送报告|上传群文件)"),
            (
                "LLM",
                "大模型调用",
                r"(llm|analyzer|prompt|openai|deepseek|claude|qwen|gpt|token|提示词)",
            ),
            (
                "Render",
                "报告与模板",
                r"(render|template|html|image|report|playwright|canvas|报告|模板|渲染)",
            ),
            ("WebUI", "控制台交互", r"(webui|bridge|api_|dashboard|route|控制台)"),
            ("Trace", "链路追踪", r"(trace|span|context_metric)"),
            ("General", "通用日志", r"(?!)"),
        ]
    ]

    STAGE_NAMES: ClassVar[dict[str, str]] = {
        AnalysisStage.FETCH_MESSAGES.value: "拉取聊天记录",
        AnalysisStage.CLEAN_MESSAGES.value: "消息清洗过滤",
        AnalysisStage.STATS_ANALYSIS.value: "基础统计分析",
        AnalysisStage.LLM_ANALYSIS.value: "大模型话题与画像分析",
        AnalysisStage.SAVE_SUMMARY.value: "历史记录持久化",
        AnalysisStage.RENDER_REPORT.value: "报告图片渲染与发送",
        AnalysisStage.DISPATCH_REPORT.value: "群聊消息投递与分发",
        AnalysisStage.COMIC_STORYBOARD.value: "漫画分镜提示词提取",
        AnalysisStage.COMIC_DRAWING.value: "漫画长图生成与投递",
        "CRASH_RECOVERY": "异常终止恢复",
    }

    def __init__(self, max_capacity: int = 2000):
        super().__init__()
        self.max_capacity = max_capacity
        self._buffer: deque[PluginLogEntry] = deque(maxlen=max_capacity)
        self._counter = 0
        self._listeners: set[Callable[[PluginLogEntry], object]] = set()

    def register_listener(self, listener: Callable[[PluginLogEntry], object]) -> None:
        """注册日志实时推送监听器"""
        self._listeners.add(listener)

    def unregister_listener(self, listener: Callable[[PluginLogEntry], object]) -> None:
        """注销日志实时推送监听器"""
        self._listeners.discard(listener)

    def record_log(
        self,
        level: str,
        msg: str,
        trace_id: str | None = None,
        logger_name: str = "plugin",
        location: str | None = None,
        function_name: str | None = None,
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

        # 先移除追踪前缀，群名或任务编号中的关键字不参与功能归类。
        clean_msg = msg
        if trace_id and clean_msg.startswith(f"[{trace_id}] "):
            clean_msg = clean_msg[len(f"[{trace_id}] ") :]

        source = (
            location.rsplit(":", 1)[0]
            .replace("\\", "/")
            .rsplit("/", 1)[-1]
            .removesuffix(".py")
            if location
            else logger_name.rsplit(".", 1)[-1]
        )
        tag = next(
            (
                key
                for key, pattern in self.SOURCE_TAGS.items()
                if pattern.fullmatch(source)
            ),
            "General",
        )
        if tag == "General":
            for tag_key, _, pattern in self.TAG_PATTERNS:
                if pattern.search(clean_msg) or pattern.search(logger_name):
                    tag = tag_key
                    break

        # 阶段解析
        stage = None
        for stage_code, stage_label in self.STAGE_NAMES.items():
            if stage_code in msg or stage_label in msg:
                stage = stage_label
                break

        loc_label = f"[{location}]" if location else f"[{logger_name}]"
        if function_name:
            loc_label += f" [{function_name}]"
        raw = f"[{full_time_str}] [{level.upper()}] {loc_label}: {clean_msg}"

        entry = PluginLogEntry(
            id=f"log_{self._counter}",
            timestamp=now,
            time_str=full_time_str,
            level=level.upper(),
            logger_name=logger_name,
            trace_id=trace_id,
            stage=stage,
            tag=tag,
            message=clean_msg,
            raw=raw,
            location=location,
            function_name=function_name,
        )
        self._buffer.append(entry)

        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception:
                pass

        return entry

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        level: str | None = None,
        trace_id: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
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
            if search_kw and (
                search_kw not in entry.message.lower()
                and search_kw not in (entry.trace_id or "").lower()
                and search_kw not in entry.logger_name.lower()
                and search_kw not in (entry.location or "").lower()
                and search_kw not in (entry.function_name or "").lower()
            ):
                continue
            results.append(entry)

        total = len(results)
        paged = results[offset : offset + limit]
        return [e.to_dict() for e in paged], total

    def get_trace_logs(self, trace_id: str) -> list[dict[str, object]]:
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
