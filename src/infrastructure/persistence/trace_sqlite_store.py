"""
Trace 持久化仓储 - 基于 SQLite 的轻量级嵌入式存储
负责存储链路快照、细粒度 Span 耗时、dsh-context 风格的上下文演进指标与 Token 消耗审计。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class TraceSQLiteStore:
    """基于 SQLite 的 Trace 链路持久化仓储"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取启用了 WAL 模式和外键支持的数据库连接"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """初始化数据库表结构与索引"""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_traces (
                    trace_id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    group_name TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    trigger_type TEXT DEFAULT 'manual',
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    completed_at REAL,
                    duration_ms REAL,
                    error_stage TEXT,
                    error_message TEXT,
                    stack_trace TEXT,
                    extra_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS trace_spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    duration_ms REAL,
                    stage_payload_json TEXT DEFAULT '{}',
                    FOREIGN KEY (trace_id) REFERENCES analysis_traces(trace_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS context_metrics (
                    trace_id TEXT PRIMARY KEY,
                    raw_message_count INTEGER DEFAULT 0,
                    cleaned_message_count INTEGER DEFAULT 0,
                    compression_ratio REAL DEFAULT 0.0,
                    incremental_batches INTEGER DEFAULT 0,
                    window_size INTEGER DEFAULT 0,
                    FOREIGN KEY (trace_id) REFERENCES analysis_traces(trace_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS token_usage (
                    trace_id TEXT PRIMARY KEY,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    estimated_cost REAL DEFAULT 0.0,
                    per_analyzer_tokens_json TEXT DEFAULT '{}',
                    FOREIGN KEY (trace_id) REFERENCES analysis_traces(trace_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_traces_started_at ON analysis_traces(started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_traces_group_id ON analysis_traces(group_id);
                CREATE INDEX IF NOT EXISTS idx_traces_status ON analysis_traces(status);
                CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON trace_spans(trace_id);
                """
            )

    def save_trace(self, trace_dict: dict[str, Any]) -> None:
        """保存或全量更新 Trace 链路及其关联的 Spans、ContextMetrics、TokenUsage"""
        trace_id = trace_dict.get("trace_id", "")
        if not trace_id:
            return

        with self._get_connection() as conn:
            # 1. 写入主表前，合并既有的 extra_json（特别是 report_files 产物列表）
            extra_payload = dict(trace_dict.get("extra", {}))
            meta = trace_dict.get("metadata", {})
            if isinstance(meta, dict):
                for k, v in meta.items():
                    if k not in extra_payload:
                        extra_payload[k] = v
                    elif isinstance(v, dict) and isinstance(extra_payload.get(k), dict):
                        extra_payload[k].update(v)
                    elif isinstance(v, list) and isinstance(extra_payload.get(k), list):
                        extra_payload[k] = v

            existing_row = conn.execute(
                "SELECT extra_json FROM analysis_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if existing_row and existing_row[0]:
                try:
                    old_extra = json.loads(existing_row[0])
                    merged_rfiles = list(old_extra.get("report_files", []))
                    seen_filenames = {
                        rf.get("filename")
                        for rf in merged_rfiles
                        if isinstance(rf, dict) and rf.get("filename")
                    }
                    for rf in extra_payload.get("report_files", []):
                        if isinstance(rf, dict):
                            fn = rf.get("filename")
                            if fn and fn not in seen_filenames:
                                seen_filenames.add(fn)
                                merged_rfiles.append(rf)
                    extra_payload["report_files"] = merged_rfiles

                    # 保留历史已记录的 prompts 与 attempts
                    if (
                        "llm_prompts" not in extra_payload
                        and "llm_prompts" in old_extra
                    ):
                        extra_payload["llm_prompts"] = old_extra["llm_prompts"]
                    if (
                        "llm_attempts" not in extra_payload
                        and "llm_attempts" in old_extra
                    ):
                        extra_payload["llm_attempts"] = old_extra["llm_attempts"]
                except Exception:
                    pass

            conn.execute(
                """
                INSERT INTO analysis_traces (
                    trace_id, group_id, group_name, platform, trigger_type,
                    status, started_at, completed_at, duration_ms,
                    error_stage, error_message, stack_trace, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    group_id=CASE WHEN excluded.group_id != '' THEN excluded.group_id ELSE analysis_traces.group_id END,
                    group_name=CASE WHEN excluded.group_name != '' AND excluded.group_name != '未知群' THEN excluded.group_name ELSE analysis_traces.group_name END,
                    platform=CASE WHEN excluded.platform != '' AND excluded.platform NOT IN ('auto', 'default', 'all') THEN excluded.platform ELSE analysis_traces.platform END,
                    status=excluded.status,
                    completed_at=excluded.completed_at,
                    duration_ms=excluded.duration_ms,
                    error_stage=excluded.error_stage,
                    error_message=excluded.error_message,
                    stack_trace=excluded.stack_trace,
                    extra_json=excluded.extra_json;
                """,
                (
                    trace_id,
                    str(trace_dict.get("group_id", "")),
                    str(trace_dict.get("group_name", "")),
                    str(trace_dict.get("platform", "")),
                    str(trace_dict.get("trigger_type", "manual")),
                    str(trace_dict.get("status", "running")),
                    float(trace_dict.get("started_at", time.time())),
                    trace_dict.get("completed_at"),
                    trace_dict.get("duration_ms"),
                    trace_dict.get("error_stage"),
                    trace_dict.get("error_message"),
                    trace_dict.get("stack_trace"),
                    json.dumps(extra_payload, ensure_ascii=False),
                ),
            )

            # 2. 写入 Spans (增量覆写)
            spans = trace_dict.get("spans", [])
            for span in spans:
                conn.execute(
                    """
                    INSERT INTO trace_spans (
                        span_id, trace_id, stage_name, status, started_at, duration_ms, stage_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(span_id) DO UPDATE SET
                        status=excluded.status,
                        duration_ms=excluded.duration_ms,
                        stage_payload_json=excluded.stage_payload_json;
                    """,
                    (
                        span.get("span_id", f"{trace_id}_{span.get('stage_name')}"),
                        trace_id,
                        span.get("stage_name", ""),
                        span.get("status", "success"),
                        float(span.get("started_at", time.time())),
                        span.get("duration_ms"),
                        json.dumps(span.get("payload", {}), ensure_ascii=False),
                    ),
                )

            # 3. 写入 Context Metrics
            context_metrics = trace_dict.get("context_metrics")
            if context_metrics:
                conn.execute(
                    """
                    INSERT INTO context_metrics (
                        trace_id, raw_message_count, cleaned_message_count,
                        compression_ratio, incremental_batches, window_size
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trace_id) DO UPDATE SET
                        raw_message_count=excluded.raw_message_count,
                        cleaned_message_count=excluded.cleaned_message_count,
                        compression_ratio=excluded.compression_ratio,
                        incremental_batches=excluded.incremental_batches,
                        window_size=excluded.window_size;
                    """,
                    (
                        trace_id,
                        int(context_metrics.get("raw_message_count", 0)),
                        int(context_metrics.get("cleaned_message_count", 0)),
                        float(context_metrics.get("compression_ratio", 0.0)),
                        int(context_metrics.get("incremental_batches", 0)),
                        int(context_metrics.get("window_size", 0)),
                    ),
                )

            # 4. 写入 Token Usage
            token_usage = trace_dict.get("token_usage")
            if token_usage:
                conn.execute(
                    """
                    INSERT INTO token_usage (
                        trace_id, prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost, per_analyzer_tokens_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trace_id) DO UPDATE SET
                        prompt_tokens=excluded.prompt_tokens,
                        completion_tokens=excluded.completion_tokens,
                        total_tokens=excluded.total_tokens,
                        estimated_cost=excluded.estimated_cost,
                        per_analyzer_tokens_json=excluded.per_analyzer_tokens_json;
                    """,
                    (
                        trace_id,
                        int(token_usage.get("prompt_tokens", 0)),
                        int(token_usage.get("completion_tokens", 0)),
                        int(token_usage.get("total_tokens", 0)),
                        float(token_usage.get("estimated_cost", 0.0)),
                        json.dumps(
                            token_usage.get("per_analyzer", {}), ensure_ascii=False
                        ),
                    ),
                )

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """获取单个 Trace 的完整树状结构（包含 Spans、ContextMetrics、TokenUsage）"""
        with self._get_connection() as conn:
            trace_row = conn.execute(
                "SELECT * FROM analysis_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if not trace_row:
                return None

            trace_data = dict(trace_row)
            try:
                trace_data["extra"] = json.loads(trace_data.pop("extra_json") or "{}")
            except Exception:
                trace_data["extra"] = {}

            # 查询 Spans
            spans_rows = conn.execute(
                "SELECT * FROM trace_spans WHERE trace_id = ? ORDER BY started_at ASC",
                (trace_id,),
            ).fetchall()
            spans = []
            extra_prompts = trace_data.get("extra", {}).get("llm_prompts", {})
            extra_attempts = trace_data.get("extra", {}).get("llm_attempts", [])
            for r in spans_rows:
                s = dict(r)
                try:
                    s["payload"] = json.loads(s.pop("stage_payload_json") or "{}")
                except Exception:
                    s["payload"] = {}
                if s.get("stage_name") == "LLM_ANALYSIS":
                    if extra_prompts and not s["payload"].get("prompts"):
                        s["payload"]["prompts"] = extra_prompts
                    if extra_attempts and not s["payload"].get("llm_attempts"):
                        s["payload"]["llm_attempts"] = extra_attempts
                spans.append(s)
            trace_data["spans"] = spans

            # 查询 Context Metrics
            cm_row = conn.execute(
                "SELECT * FROM context_metrics WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            trace_data["context_metrics"] = dict(cm_row) if cm_row else None

            # 查询 Token Usage
            token_row = conn.execute(
                "SELECT * FROM token_usage WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if token_row:
                t_data = dict(token_row)
                try:
                    t_data["per_analyzer"] = json.loads(
                        t_data.pop("per_analyzer_tokens_json") or "{}"
                    )
                except Exception:
                    t_data["per_analyzer"] = {}
                trace_data["token_usage"] = t_data
            else:
                trace_data["token_usage"] = None

            raw_rfiles = trace_data.get("extra", {}).get("report_files", [])
            seen_rfiles = set()
            deduped_rfiles = []
            for rf in raw_rfiles:
                fn = rf.get("filename") if isinstance(rf, dict) else None
                if fn and fn not in seen_rfiles:
                    seen_rfiles.add(fn)
                    deduped_rfiles.append(rf)

            # 额外扫描磁盘 reports 目录，聚合文件名中明确带有 trace_id 的产物文件（如换模板重绘/续跑生成的文件）
            try:
                reports_dir = self.db_path.parent / "reports"
                if reports_dir.is_dir():
                    for p in reports_dir.iterdir():
                        if (
                            p.is_file()
                            and trace_id in p.name
                            and p.name not in seen_rfiles
                        ):
                            seen_rfiles.add(p.name)
                            is_html = p.suffix.lower() in (".html", ".htm")
                            is_comic = p.name.lower().startswith(
                                "comic_"
                            ) or p.name.startswith("漫画_")
                            stat = p.stat()
                            deduped_rfiles.append(
                                {
                                    "filename": p.name,
                                    "path": str(p.resolve()),
                                    "format": "html" if is_html else "image",
                                    "report_type": "comic" if is_comic else "daily",
                                    "size_bytes": stat.st_size,
                                    "created_at": stat.st_mtime,
                                }
                            )
            except Exception:
                pass

            # 按生成时间降序排序，最新生成的报告排在前面
            deduped_rfiles.sort(
                key=lambda x: x.get("created_at", 0) if isinstance(x, dict) else 0,
                reverse=True,
            )
            trace_data["report_files"] = deduped_rfiles
            return trace_data

    def get_report_trace_map(self) -> dict[str, str]:
        """获取已生成的报告文件名与 trace_id 的双向映射"""
        mapping: dict[str, str] = {}
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT trace_id, extra_json FROM analysis_traces WHERE extra_json LIKE '%report_files%'"
            ).fetchall()
            for r in rows:
                t_id = str(r["trace_id"])
                try:
                    extra = json.loads(r["extra_json"] or "{}")
                    for rf in extra.get("report_files", []):
                        fn = rf.get("filename")
                        if fn:
                            mapping[fn] = t_id
                except Exception:
                    pass
        return mapping

    def reconcile_crashed_traces_on_startup(self) -> int:
        """开机对账扫描：将上次因系统异常终止/重启而未正常收尾的 running 任务标记为 aborted。"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE analysis_traces
                SET status = 'aborted',
                    error_stage = 'CRASH_RECOVERY',
                    error_message = 'AstrBot/容器在任务执行期间异常终止，开机已自动回收',
                    completed_at = strftime('%s', 'now')
                WHERE status = 'running'
                """
            )
            reconciled_count = cursor.rowcount
            return reconciled_count

    def get_distinct_groups(self) -> list[dict[str, str]]:
        """获取所有有历史分析记录的唯一群组列表（按 group_id 分组，取每个群最新一次运行的群名与平台标识）"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                WITH ranked_traces AS (
                    SELECT group_id,
                           group_name,
                           platform,
                           started_at,
                           ROW_NUMBER() OVER (PARTITION BY group_id ORDER BY started_at DESC) AS rn
                    FROM analysis_traces
                    WHERE group_id != ''
                )
                SELECT r.group_id,
                       COALESCE(
                           NULLIF(r.group_name, ''),
                           NULLIF(r.group_name, '未知群'),
                           (SELECT group_name FROM analysis_traces WHERE group_id = r.group_id AND group_name != '' AND group_name != '未知群' ORDER BY started_at DESC LIMIT 1),
                           r.group_id
                       ) AS group_name,
                       r.platform,
                       r.started_at AS last_seen
                FROM ranked_traces r
                WHERE r.rn = 1
                ORDER BY r.started_at DESC;
                """
            ).fetchall()
            return [
                {
                    "group_id": str(r["group_id"]),
                    "group_name": str(r["group_name"]),
                    "platform": str(r["platform"] or ""),
                }
                for r in rows
            ]

    def list_traces(
        self,
        limit: int = 20,
        offset: int = 0,
        group_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        sort_by: str = "started_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """分页筛选查询 Trace 列表（支持按群组、状态、关键词、时间范围筛选与排序）"""
        conditions = []
        params: list[Any] = []

        if group_id:
            conditions.append("t.group_id = ?")
            params.append(str(group_id))
        if status:
            conditions.append("t.status = ?")
            params.append(status)
        if start_time is not None:
            conditions.append("t.started_at >= ?")
            params.append(float(start_time))
        if end_time is not None:
            conditions.append("t.started_at <= ?")
            params.append(float(end_time))
        if search:
            conditions.append(
                "(t.trace_id LIKE ? OR t.group_id LIKE ? OR t.group_name LIKE ?)"
            )
            like_pattern = f"%{search}%"
            params.extend([like_pattern, like_pattern, like_pattern])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 排序字段白名单校验
        allowed_sort_fields = {
            "started_at": "t.started_at",
            "duration_ms": "t.duration_ms",
            "total_tokens": "tu.total_tokens",
            "compression_ratio": "cm.compression_ratio",
        }
        order_field = allowed_sort_fields.get(sort_by, "t.started_at")
        order_direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        with self._get_connection() as conn:
            # 查询总数
            count_sql = f"SELECT COUNT(*) FROM analysis_traces t {where_clause}"
            total_count = conn.execute(count_sql, params).fetchone()[0]

            # 查询列表与关联 Token 汇总
            query_sql = f"""
                SELECT
                    t.*,
                    tu.total_tokens,
                    tu.estimated_cost,
                    cm.raw_message_count,
                    cm.cleaned_message_count,
                    cm.compression_ratio
                FROM analysis_traces t
                LEFT JOIN token_usage tu ON t.trace_id = tu.trace_id
                LEFT JOIN context_metrics cm ON t.trace_id = cm.trace_id
                {where_clause}
                ORDER BY {order_field} {order_direction}
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

            traces = []
            for r in rows:
                item = dict(r)
                try:
                    item["extra"] = json.loads(item.pop("extra_json") or "{}")
                except Exception:
                    item["extra"] = {}
                traces.append(item)

            return traces, total_count

    def get_metrics_summary(self) -> dict[str, Any]:
        """获取控制台顶部 KPI 指标与聚合数据"""
        now = time.time()
        local_tm = time.localtime(now)
        # 本地时间今日零点时间戳
        start_of_today = time.mktime(
            (local_tm.tm_year, local_tm.tm_mon, local_tm.tm_mday, 0, 0, 0, 0, 0, -1)
        )

        with self._get_connection() as conn:
            # 1. 总体概况
            overview = conn.execute(
                """
                SELECT
                    COUNT(*) as total_traces,
                    SUM(CASE WHEN status IN ('succeeded', 'warning') THEN 1 ELSE 0 END) as succeeded_count,
                    SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) as warning_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    AVG(CASE WHEN status IN ('succeeded', 'warning') THEN duration_ms ELSE NULL END) as avg_duration_ms
                FROM analysis_traces;
                """
            ).fetchone()

            # 2. 今日数据
            today_data = conn.execute(
                """
                SELECT
                    COUNT(*) as today_traces,
                    COUNT(DISTINCT group_id) as today_active_groups
                FROM analysis_traces
                WHERE started_at >= ?;
                """,
                (start_of_today,),
            ).fetchone()

            # 3. Token 累计总数与成本
            token_stats = conn.execute(
                """
                SELECT
                    SUM(total_tokens) as total_tokens_spent,
                    SUM(estimated_cost) as total_cost_spent
                FROM token_usage;
                """
            ).fetchone()

            # 4. 今日 Token 消耗
            today_tokens = conn.execute(
                """
                SELECT
                    SUM(tu.total_tokens) as today_tokens_spent,
                    SUM(tu.estimated_cost) as today_cost_spent
                FROM token_usage tu
                JOIN analysis_traces t ON tu.trace_id = t.trace_id
                WHERE t.started_at >= ?;
                """,
                (start_of_today,),
            ).fetchone()

            return {
                "total_traces": overview["total_traces"] or 0,
                "succeeded_count": overview["succeeded_count"] or 0,
                "failed_count": overview["failed_count"] or 0,
                "success_rate": (
                    round(
                        (overview["succeeded_count"] or 0)
                        / max(1, overview["total_traces"] or 1)
                        * 100,
                        1,
                    )
                ),
                "avg_duration_ms": round(overview["avg_duration_ms"] or 0.0, 1),
                "today_traces": today_data["today_traces"] or 0,
                "today_active_groups": today_data["today_active_groups"] or 0,
                "total_tokens_spent": token_stats["total_tokens_spent"] or 0,
                "total_cost_spent": round(token_stats["total_cost_spent"] or 0.0, 4),
                "today_tokens_spent": today_tokens["today_tokens_spent"] or 0,
                "today_cost_spent": round(today_tokens["today_cost_spent"] or 0.0, 4),
                "trends": self.get_analytics_trends(granularity="day", range_count=14),
            }

    def get_analytics_trends(
        self, granularity: str = "day", range_count: int = 14
    ) -> dict[str, Any]:
        """获取时序趋势数据（支持小时 / 天维度切换，并提取服务商与模型消耗细粒度拆分）"""
        now = time.time()
        local_tm = time.localtime(now)

        points: list[dict[str, Any]] = []
        provider_map: dict[str, dict[str, Any]] = {}
        model_map: dict[str, dict[str, Any]] = {}

        if granularity == "hour":
            # 按小时划分（默认近 48 小时 / 2 天视野）
            hours = max(1, min(range_count, 168))  # 上限7天
            # 当前小时的整点时间戳
            cur_hour_start = time.mktime(
                (
                    local_tm.tm_year,
                    local_tm.tm_mon,
                    local_tm.tm_mday,
                    local_tm.tm_hour,
                    0,
                    0,
                    0,
                    0,
                    -1,
                )
            )
            start_timestamp = cur_hour_start - ((hours - 1) * 3600)

            trend_map: dict[str, dict[str, Any]] = {}
            for i in range(hours):
                h_ts = start_timestamp + (i * 3600)
                h_tm = time.localtime(h_ts)
                h_key = f"{h_tm.tm_year:04d}-{h_tm.tm_mon:02d}-{h_tm.tm_mday:02d} {h_tm.tm_hour:02d}:00"
                display_date = f"{h_tm.tm_mon}/{h_tm.tm_mday} {h_tm.tm_hour:02d}:00"
                trend_map[h_key] = {
                    "date": display_date,
                    "date_full": h_key,
                    "timestamp": h_ts,
                    "request_count": 0,
                    "succeeded_count": 0,
                    "failed_count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                }

            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        strftime('%Y-%m-%d %H:00', datetime(t.started_at, 'unixepoch', 'localtime')) as hour_str,
                        COUNT(t.trace_id) as request_count,
                        SUM(CASE WHEN t.status IN ('succeeded', 'warning') THEN 1 ELSE 0 END) as succeeded_count,
                        SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                        COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                        COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                        COALESCE(SUM(tu.estimated_cost), 0.0) as estimated_cost
                    FROM analysis_traces t
                    LEFT JOIN token_usage tu ON t.trace_id = tu.trace_id
                    WHERE t.started_at >= ?
                    GROUP BY hour_str;
                    """,
                    (start_timestamp,),
                ).fetchall()

                for r in rows:
                    h_str = r["hour_str"]
                    if h_str in trend_map:
                        trend_map[h_str]["request_count"] = r["request_count"] or 0
                        trend_map[h_str]["succeeded_count"] = r["succeeded_count"] or 0
                        trend_map[h_str]["failed_count"] = r["failed_count"] or 0
                        trend_map[h_str]["prompt_tokens"] = r["prompt_tokens"] or 0
                        trend_map[h_str]["completion_tokens"] = (
                            r["completion_tokens"] or 0
                        )
                        trend_map[h_str]["total_tokens"] = r["total_tokens"] or 0
                        trend_map[h_str]["estimated_cost"] = round(
                            r["estimated_cost"] or 0.0, 4
                        )

            points = list(trend_map.values())
        else:
            # 按天划分（支持 7 天、14 天、30 天等视野）
            days = max(1, min(range_count, 90))
            today_start = time.mktime(
                (
                    local_tm.tm_year,
                    local_tm.tm_mon,
                    local_tm.tm_mday,
                    0,
                    0,
                    0,
                    0,
                    0,
                    -1,
                )
            )
            start_timestamp = today_start - ((days - 1) * 86400)

            trend_map = {}
            for i in range(days):
                day_ts = start_timestamp + (i * 86400)
                d_tm = time.localtime(day_ts)
                day_key = f"{d_tm.tm_year:04d}-{d_tm.tm_mon:02d}-{d_tm.tm_mday:02d}"
                display_date = f"{d_tm.tm_mon}/{d_tm.tm_mday}"
                trend_map[day_key] = {
                    "date": display_date,
                    "date_full": day_key,
                    "timestamp": day_ts,
                    "request_count": 0,
                    "succeeded_count": 0,
                    "failed_count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                }

            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        date(t.started_at, 'unixepoch', 'localtime') as day_str,
                        COUNT(t.trace_id) as request_count,
                        SUM(CASE WHEN t.status IN ('succeeded', 'warning') THEN 1 ELSE 0 END) as succeeded_count,
                        SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                        COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                        COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                        COALESCE(SUM(tu.estimated_cost), 0.0) as estimated_cost
                    FROM analysis_traces t
                    LEFT JOIN token_usage tu ON t.trace_id = tu.trace_id
                    WHERE t.started_at >= ?
                    GROUP BY day_str;
                    """,
                    (start_timestamp,),
                ).fetchall()

                for r in rows:
                    day_str = r["day_str"]
                    if day_str in trend_map:
                        trend_map[day_str]["request_count"] = r["request_count"] or 0
                        trend_map[day_str]["succeeded_count"] = (
                            r["succeeded_count"] or 0
                        )
                        trend_map[day_str]["failed_count"] = r["failed_count"] or 0
                        trend_map[day_str]["prompt_tokens"] = r["prompt_tokens"] or 0
                        trend_map[day_str]["completion_tokens"] = (
                            r["completion_tokens"] or 0
                        )
                        trend_map[day_str]["total_tokens"] = r["total_tokens"] or 0
                        trend_map[day_str]["estimated_cost"] = round(
                            r["estimated_cost"] or 0.0, 4
                        )

            points = list(trend_map.values())

        # 提取该时间范围内的服务商 (Provider) 与模型 (Model) 维度消耗分布
        with self._get_connection() as conn:
            traces_with_usage = conn.execute(
                """
                SELECT
                    t.extra_json,
                    COALESCE(tu.total_tokens, 0) as total_tokens,
                    COALESCE(tu.prompt_tokens, 0) as prompt_tokens,
                    COALESCE(tu.completion_tokens, 0) as completion_tokens,
                    COALESCE(tu.per_analyzer_tokens_json, '{}') as per_analyzer
                FROM analysis_traces t
                LEFT JOIN token_usage tu ON t.trace_id = tu.trace_id
                WHERE t.started_at >= ?;
                """,
                (start_timestamp,),
            ).fetchall()

            invalid_provider_names = {
                "default",
                "default_provider",
                "quality_provider_id",
                "none",
                "",
            }
            invalid_model_names = {"default", "default_model", "none", ""}

            for tw in traces_with_usage:
                try:
                    extra = json.loads(tw["extra_json"] or "{}")
                except Exception:
                    extra = {}

                llm_prompts = (
                    extra.get("llm_prompts", {}) if isinstance(extra, dict) else {}
                )

                # 收集有效 provider_id
                providers_in_trace: set[str] = set()
                models_in_trace: set[str] = set()

                if isinstance(llm_prompts, dict):
                    for _, p_info in llm_prompts.items():
                        if isinstance(p_info, dict):
                            p_id = str(p_info.get("provider_id", "")).strip()
                            if p_id and p_id.lower() not in invalid_provider_names:
                                providers_in_trace.add(p_id)
                            m_id = str(p_info.get("model", "")).strip()
                            if m_id and m_id.lower() not in invalid_model_names:
                                models_in_trace.add(m_id)

                if not providers_in_trace:
                    fallback_p = str(extra.get("provider_id", "")).strip()
                    if fallback_p and fallback_p.lower() not in invalid_provider_names:
                        providers_in_trace.add(fallback_p)
                    else:
                        providers_in_trace.add("默认会话服务商")

                if not models_in_trace:
                    fallback_m = str(
                        extra.get("model") or extra.get("model_id") or ""
                    ).strip()
                    if fallback_m and fallback_m.lower() not in invalid_model_names:
                        models_in_trace.add(fallback_m)
                    else:
                        models_in_trace.add("默认会话模型")

                tot_tok = int(tw["total_tokens"] or 0)
                tokens_per_p = tot_tok // max(1, len(providers_in_trace))
                for pid in providers_in_trace:
                    if pid not in provider_map:
                        provider_map[pid] = {
                            "name": pid,
                            "total_tokens": 0,
                            "request_count": 0,
                        }
                    provider_map[pid]["total_tokens"] += tokens_per_p
                    provider_map[pid]["request_count"] += 1

                tokens_per_m = tot_tok // max(1, len(models_in_trace))
                for mid in models_in_trace:
                    if mid not in model_map:
                        model_map[mid] = {
                            "name": mid,
                            "total_tokens": 0,
                            "request_count": 0,
                        }
                    model_map[mid]["total_tokens"] += tokens_per_m
                    model_map[mid]["request_count"] += 1

        provider_breakdown = [
            p
            for p in sorted(
                provider_map.values(),
                key=lambda x: x["total_tokens"],
                reverse=True,
            )
            if p["total_tokens"] > 0 or p["request_count"] > 0
        ]
        model_breakdown = [
            m
            for m in sorted(
                model_map.values(),
                key=lambda x: x["total_tokens"],
                reverse=True,
            )
            if m["total_tokens"] > 0 or m["request_count"] > 0
        ]

        return {
            "granularity": granularity,
            "range_count": range_count,
            "points": points,
            "provider_breakdown": provider_breakdown,
            "model_breakdown": model_breakdown,
        }

    def cleanup_old_traces(self, days: int = 30, max_count: int = 20000) -> int:
        """根据保留天数（默认30天）或最大条数上限清理旧的 Trace 数据，防止 SQLite 无限增长"""
        cutoff_time = time.time() - (days * 86400)
        deleted_count = 0

        with self._get_connection() as conn:
            # 1. 按过期时间清理
            cursor = conn.execute(
                "DELETE FROM analysis_traces WHERE started_at < ?", (cutoff_time,)
            )
            deleted_count += cursor.rowcount

            # 2. 按最大数量上限清理多余数据
            total_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_traces"
            ).fetchone()[0]
            if total_count > max_count:
                excess = total_count - max_count
                conn.execute(
                    """
                    DELETE FROM analysis_traces
                    WHERE trace_id IN (
                        SELECT trace_id FROM analysis_traces
                        ORDER BY started_at ASC LIMIT ?
                    );
                    """,
                    (excess,),
                )
                deleted_count += excess

        return deleted_count
