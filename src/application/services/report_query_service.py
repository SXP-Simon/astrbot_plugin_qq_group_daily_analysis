"""报告查询应用服务 - 应用层 (LLM Tool 专用)

实现“按需多维查询历史分析报告”核心用例，协调 CheckpointStore、HistoryManager、
TraceSQLiteStore 与群组权限校验，提供弹性日期解析、智能群目标解析与字段投影截断能力。
"""

from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING

from ...shared.constants import AnalysisStage

if TYPE_CHECKING:
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.checkpoint_store import CheckpointStore
    from ...infrastructure.persistence.history_manager import HistoryManager
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


class ReportQueryService:
    """报告查询应用服务。

    提供高效、无害、只读的历史群分析检索能力。
    """

    MAX_DATE_SPAN_DAYS = 30
    DEFAULT_MAX_CHARACTERS = 40000

    def __init__(
        self,
        config_manager: ConfigManager,
        checkpoint_store: CheckpointStore | None,
        history_manager: HistoryManager | None,
        trace_store: TraceSQLiteStore | None = None,
    ) -> None:
        """初始化报告查询服务。

        Args:
            config_manager: 插件配置管理器。
            checkpoint_store: 阶段检查点存储器（热轨）。
            history_manager: 历史摘要存储器（冷轨兜底）。
            trace_store: 追踪存储器（用于群名称反查）。
        """
        self.config_manager = config_manager
        self.checkpoint_store = checkpoint_store
        self.history_manager = history_manager
        self.trace_store = trace_store

    def resolve_target_group(
        self,
        group_input: str,
        current_event_group_id: str | None = None,
    ) -> tuple[str | None, str, list[dict[str, str]]]:
        """智能解析目标群聊标识（4级漏斗）。

        Args:
            group_input: 用户或模型传入的群聊标识（群号/群名/UMO/空字符串）。
            current_event_group_id: 当前会话事件所属的群号（若为群聊事件）。

        Returns:
            (target_group_id, matched_group_name, ambiguous_candidates)
            若存在歧义，返回 (None, "", candidates)
            若未找到或不合法，返回 (None, "", [])
        """
        clean_input = str(group_input or "").strip()

        # 1. 留空：默认继承当前群聊
        if not clean_input:
            if current_event_group_id:
                clean_gid = str(current_event_group_id).strip()
                return clean_gid, self._get_cached_group_name(clean_gid), []
            return None, "", []

        # 2. 剥离 UMO 前缀，检查是否为纯数字群号
        candidate_num = clean_input
        if ":" in candidate_num:
            candidate_num = candidate_num.rsplit(":", 1)[-1]
        if "#" in candidate_num:
            candidate_num = candidate_num.split("#", 1)[0]
        if "_" in candidate_num:
            candidate_num = candidate_num.split("_")[-1]

        candidate_num = candidate_num.strip()
        if candidate_num.isdigit() and len(candidate_num) >= 5:
            return candidate_num, self._get_cached_group_name(candidate_num), []

        # 3. 文本/群名称模糊匹配 (通过 trace_store)
        if self.trace_store:
            matches = self.trace_store.find_groups_by_name(clean_input, limit=5)
            if len(matches) == 1:
                single = matches[0]
                return str(single["group_id"]), str(single["group_name"]), []
            if len(matches) > 1:
                # 检查是否有完全相等的精准匹配
                exact_matches = [
                    m for m in matches if str(m["group_name"]).strip() == clean_input
                ]
                if len(exact_matches) == 1:
                    exact = exact_matches[0]
                    return str(exact["group_id"]), str(exact["group_name"]), []
                return None, "", matches

        return None, "", []

    def parse_date_range(self, date_range_input: str) -> tuple[str, str, str | None]:
        """弹性归一化日期或日期范围。

        Args:
            date_range_input: 日期输入字符串。

        Returns:
            (start_date, end_date, error_message)
            格式均为 YYYY-MM-DD，若出错返回包含 error_message 的三元组。
        """
        raw = str(date_range_input or "").strip()
        today = dt.date.today()

        if not raw or raw in {"最新", "当前", "today", "now"}:
            today_str = today.strftime("%Y-%m-%d")
            return "", "", None

        if raw in {"今天", "今日"}:
            today_str = today.strftime("%Y-%m-%d")
            return today_str, today_str, None

        if raw in {"昨天", "昨日", "yesterday"}:
            yesterday_str = (today - dt.timedelta(days=1)).strftime("%Y-%m-%d")
            return yesterday_str, yesterday_str, None

        if raw in {"前天", "前日"}:
            before_yesterday_str = (today - dt.timedelta(days=2)).strftime("%Y-%m-%d")
            return before_yesterday_str, before_yesterday_str, None

        # 分割范围: 支持 ~, 至, 到, ,, --
        delimiters = ["~", "至", "到", ",", "--"]
        parts = [raw]
        for d in delimiters:
            if d in raw:
                parts = [p.strip() for p in raw.split(d, 1)]
                break

        def _clean_date_str(val: str) -> dt.date | None:
            s = val.strip().replace("/", "-").replace(".", "-")
            m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
            if not m:
                return None
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return dt.date(year, month, day)
            except ValueError:
                return None

        if len(parts) == 1:
            d = _clean_date_str(parts[0])
            if not d:
                return "", "", f"无法解析的日期格式: '{parts[0]}'，请使用 YYYY-MM-DD"
            iso = d.strftime("%Y-%m-%d")
            return iso, iso, None

        # 范围格式
        d_start = _clean_date_str(parts[0])
        d_end = _clean_date_str(parts[1])
        if not d_start or not d_end:
            return (
                "",
                "",
                f"无法解析的日期范围: '{raw}'，请使用 YYYY-MM-DD~YYYY-MM-DD",
            )

        if d_end < d_start:
            return "", "", f"起始日期 ({d_start}) 不能晚于截止日期 ({d_end})"

        span_days = (d_end - d_start).days + 1
        if span_days > self.MAX_DATE_SPAN_DAYS:
            return (
                "",
                "",
                f"查询跨度为 {span_days} 天，超过了最大支持的 {self.MAX_DATE_SPAN_DAYS} 天范围，请缩小日期范围后重试",
            )

        return d_start.strftime("%Y-%m-%d"), d_end.strftime("%Y-%m-%d"), None

    async def query_reports(
        self,
        group_id: str,
        start_date: str,
        end_date: str,
        report_section: str = "全部",
    ) -> str:
        """执行群分析报告综合检索与文本组装。

        Args:
            group_id: 群号。
            start_date: 起始日期 (YYYY-MM-DD)，若为空表示查最新一份。
            end_date: 截止日期 (YYYY-MM-DD)。
            report_section: 模块筛选（话题、金句、用户称号、聊天质量分析、全部）。

        Returns:
            str: 格式化的 Markdown 结果文本。
        """
        group_name = self._get_cached_group_name(group_id)
        sections = self._parse_sections(report_section)

        # 1. 查询热轨：CheckpointStore (优先常规分析 LLM_ANALYSIS，若无则尝试按需分析 ON_DEMAND_ANALYSIS)
        reports_data: list[dict[str, object]] = []
        is_latest_query = not bool(start_date and end_date)

        if self.checkpoint_store:
            if is_latest_query:
                # 获取最新一份 Checkpoint (LLM_ANALYSIS 优先，兜底 ON_DEMAND_ANALYSIS)
                latest_cp = self._get_latest_checkpoint(
                    group_id, stage_name=AnalysisStage.LLM_ANALYSIS.value
                ) or self._get_latest_checkpoint(
                    group_id, stage_name=AnalysisStage.ON_DEMAND_ANALYSIS.value
                )
                if latest_cp:
                    reports_data.append(latest_cp)
            else:
                reports_data = self.checkpoint_store.get_checkpoints_by_date_range(
                    group_id=group_id,
                    start_date=start_date,
                    end_date=end_date,
                    stage_name=AnalysisStage.LLM_ANALYSIS.value,
                )
                if not reports_data:
                    reports_data = self.checkpoint_store.get_checkpoints_by_date_range(
                        group_id=group_id,
                        start_date=start_date,
                        end_date=end_date,
                        stage_name=AnalysisStage.ON_DEMAND_ANALYSIS.value,
                    )

        # 2. 检查单日临近探测 (若指定了单日但未命中任何报告)
        probe_notice = ""
        if not reports_data and start_date and start_date == end_date:
            nearby_cp = self._probe_nearby_checkpoint(group_id, start_date)
            if nearby_cp:
                reports_data.append(nearby_cp)
                probe_notice = (
                    f"（注：未找到 {start_date} 的归档记录，已为您自动匹配最临近于 "
                    f"{nearby_cp.get('date_str')} 生成的分析报告）\n\n"
                )

        # 3. 若热轨仍为空，尝试冷轨降级：HistoryManager (KV)
        if not reports_data and self.history_manager:
            kv_reports = await self._query_history_kv(
                group_id, start_date, end_date, is_latest_query
            )
            if kv_reports:
                reports_data.extend(kv_reports)

        if not reports_data:
            range_desc = f"{start_date} 至 {end_date}" if start_date else "近期"
            return (
                f"未检索到群聊 {group_name or group_id} 在 {range_desc} 的日常分析报告。\n"
                f"[可能原因]：该时段内群消息未达到分析阈值、Bot 未开启自动分析，或数据已过期清理。\n"
                f"通常报告会在设定的每日调度时间生成，亦可由管理员发送指令 `/群分析` 主动生成。"
            )

        # 4. 组装响应内容与字段投影
        return self._format_reports_output(
            group_id=group_id,
            group_name=group_name,
            reports=reports_data,
            sections=sections,
            probe_notice=probe_notice,
        )

    def _parse_sections(self, input_sections: str) -> set[str]:
        raw = str(input_sections or "").strip()
        if not raw or raw in {"全部", "all", "ALL"}:
            return {"topics", "golden_quotes", "user_titles", "chat_quality_review"}

        tokens = re.split(r"[,，、| +]+", raw)
        result = set()
        for tok in tokens:
            t = tok.strip().lower()
            if t in {"话题", "topic", "topics", "主题"}:
                result.add("topics")
            elif t in {"金句", "quote", "quotes", "语录", "名言"}:
                result.add("golden_quotes")
            elif t in {"用户称号", "称号", "头衔", "user_titles", "titles", "画像"}:
                result.add("user_titles")
            elif t in {"聊天质量分析", "质量", "质量分析", "氛围", "quality"}:
                result.add("chat_quality_review")
        return result or {
            "topics",
            "golden_quotes",
            "user_titles",
            "chat_quality_review",
        }

    def _get_latest_checkpoint(
        self,
        group_id: str,
        stage_name: str = "LLM_ANALYSIS",
    ) -> dict[str, object] | None:
        if not self.checkpoint_store:
            return None
        items, _total = self.checkpoint_store.list_all_checkpoints(
            limit=1,
            offset=0,
            group_id=group_id,
            stage_name=stage_name,
        )
        if not items:
            return None
        latest_summary = items[0]
        detail = self.checkpoint_store.get_checkpoint_detail(
            group_id=group_id,
            date_str=str(latest_summary.get("date_str", "")),
            stage_name=stage_name,
            trace_id=str(latest_summary.get("trace_id", "")),
        )
        if detail and detail.get("data"):
            return {
                "checkpoint_id": str(detail.get("checkpoint_id", "")),
                "group_id": str(detail.get("group_id", "")),
                "date_str": str(detail.get("date_str", "")),
                "stage_name": str(detail.get("stage_name", "")),
                "trace_id": str(detail.get("trace_id", "")),
                "created_at": float(detail.get("created_at", 0.0)),
                "created_at_formatted": str(detail.get("created_at_formatted", "")),
                "data": detail.get("data"),
            }
        return None

    def _probe_nearby_checkpoint(
        self, group_id: str, target_date_str: str
    ) -> dict[str, object] | None:
        if not self.checkpoint_store:
            return None
        try:
            target_date = dt.date.fromisoformat(target_date_str)
        except ValueError:
            return None

        # 探测 ±1 天，优先 LLM_ANALYSIS，兜底 ON_DEMAND_ANALYSIS
        prev_date = (target_date - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (target_date + dt.timedelta(days=1)).strftime("%Y-%m-%d")

        for stage in (
            AnalysisStage.LLM_ANALYSIS.value,
            AnalysisStage.ON_DEMAND_ANALYSIS.value,
        ):
            for d_str in (prev_date, next_date):
                detail = self.checkpoint_store.get_checkpoint_detail(
                    group_id=group_id,
                    date_str=d_str,
                    stage_name=stage,
                )
                if detail and detail.get("data"):
                    return {
                        "checkpoint_id": str(detail.get("checkpoint_id", "")),
                        "group_id": str(detail.get("group_id", "")),
                        "date_str": str(detail.get("date_str", "")),
                        "stage_name": str(detail.get("stage_name", "")),
                        "trace_id": str(detail.get("trace_id", "")),
                        "created_at": float(detail.get("created_at", 0.0)),
                        "created_at_formatted": str(
                            detail.get("created_at_formatted", "")
                        ),
                        "data": detail.get("data"),
                    }
        return None

    async def _query_history_kv(
        self,
        group_id: str,
        start_date: str,
        end_date: str,
        is_latest_query: bool,
    ) -> list[dict[str, object]]:
        if not self.history_manager:
            return []

        results: list[dict[str, object]] = []

        if is_latest_query:
            # 倒查最近 7 天的每日摘要，取最新命中
            today = dt.date.today()
            for offset in range(7):
                cur_date = (today - dt.timedelta(days=offset)).strftime("%Y-%m-%d")
                data = await self.history_manager.get_analysis(group_id, cur_date)
                if data:
                    results.append(
                        {
                            "checkpoint_id": f"kv_{group_id}_{cur_date}",
                            "group_id": group_id,
                            "date_str": cur_date,
                            "stage_name": "KV_SUMMARY",
                            "created_at": 0,
                            "created_at_formatted": str(data.get("generated_at", "")),
                            "data": data,
                        }
                    )
                    break
            return results

        # 日期范围查询：按日期区间逐日检索
        try:
            cur = dt.date.fromisoformat(start_date)
            end = dt.date.fromisoformat(end_date)
        except ValueError:
            cur = dt.date.today()
            end = cur

        while cur <= end:
            d_str = cur.strftime("%Y-%m-%d")
            data = await self.history_manager.get_analysis(group_id, d_str)
            if data:
                results.append(
                    {
                        "checkpoint_id": f"kv_{group_id}_{d_str}",
                        "group_id": group_id,
                        "date_str": d_str,
                        "stage_name": "KV_SUMMARY",
                        "created_at": 0,
                        "created_at_formatted": str(data.get("generated_at", "")),
                        "data": data,
                    }
                )
            cur += dt.timedelta(days=1)

        return results

    def _format_reports_output(
        self,
        group_id: str,
        group_name: str,
        reports: list[dict[str, object]],
        sections: set[str],
        probe_notice: str = "",
    ) -> str:
        header_lines = [
            "### 群聊日常分析报告",
            f"- 目标群聊: {group_name or group_id} ({group_id})",
            f"- 包含报告天数: {len(reports)} 天",
        ]
        if probe_notice:
            header_lines.append(probe_notice.strip())

        body_blocks: list[str] = ["\n".join(header_lines)]

        for r in reports:
            d_str = str(r.get("date_str", "未知日期"))
            data_obj = r.get("data")
            if not isinstance(data_obj, dict):
                continue

            day_block = [f"#### 📅 报告日期: {d_str}"]

            # 建立本报告中的 user_id -> 昵称映射字典，用于替换话题正文中的裸数字 ID 引用
            id_to_name: dict[str, str] = {}
            user_analysis = data_obj.get("user_analysis")
            if isinstance(user_analysis, dict):
                for uid, udata in user_analysis.items():
                    if isinstance(udata, dict):
                        for k in ("nickname", "name", "card"):
                            if udata.get(k):
                                id_to_name[str(uid).strip()] = str(udata[k]).strip()
                                break
            for ut in data_obj.get("user_titles") or []:
                if isinstance(ut, dict):
                    uid = str(ut.get("user_id") or "").strip()
                    uname = str(
                        ut.get("name")
                        or ut.get("user_name")
                        or ut.get("nickname")
                        or ""
                    ).strip()
                    if uid and uname and uname != uid:
                        id_to_name.setdefault(uid, uname)
            for gq in data_obj.get("golden_quotes") or []:
                if isinstance(gq, dict):
                    uid = str(gq.get("user_id") or "").strip()
                    uname = str(gq.get("sender") or gq.get("author") or "").strip()
                    if uid and uname and uname != uid:
                        id_to_name.setdefault(uid, uname)

            # 1. 话题提取
            if "topics" in sections:
                topics_raw = data_obj.get("topics")
                if isinstance(topics_raw, list) and topics_raw:
                    day_block.append("\n**【讨论话题】**")
                    for idx, t in enumerate(topics_raw, 1):
                        if isinstance(t, dict):
                            t_title = t.get("topic", "") or t.get("title", "")
                            t_desc = t.get("detail", "") or t.get("description", "")
                            t_heat = t.get("heat") or t.get("hot", "")
                            heat_suffix = f" (热度: {t_heat})" if t_heat else ""
                            # 替换详情中出现的裸 QQ 号为 昵称(QQ号)
                            t_desc_clean = (
                                self._replace_id_refs(str(t_desc), id_to_name)
                                if t_desc
                                else ""
                            )
                            day_block.append(f"{idx}. {t_title}{heat_suffix}")
                            if t_desc_clean:
                                day_block.append(f"   - 详情: {t_desc_clean}")

            # 2. 金句提取
            if "golden_quotes" in sections:
                quotes_raw = data_obj.get("golden_quotes") or (
                    data_obj.get("statistics", {}).get("golden_quotes")
                    if isinstance(data_obj.get("statistics"), dict)
                    else None
                )
                if isinstance(quotes_raw, list) and quotes_raw:
                    formatted_quotes = []
                    for q in quotes_raw:
                        if isinstance(q, dict):
                            quote_text = str(
                                q.get("quote", "")
                                or q.get("content", "")
                                or q.get("text", "")
                            ).strip()
                            if not quote_text:
                                continue
                            author = str(
                                q.get("author", "")
                                or q.get("sender", "")
                                or q.get("user", "")
                                or q.get("user_id", "")
                            ).strip()
                            ctx = str(
                                q.get("context", "") or q.get("reason", "")
                            ).strip()
                            author_desc = f" —— {author}" if author else ""
                            item_str = f'{len(formatted_quotes) + 1}. "{quote_text}"{author_desc}'
                            if ctx:
                                item_str += f"\n   - 语境/评述: {ctx}"
                            formatted_quotes.append(item_str)
                    if formatted_quotes:
                        day_block.append("\n**【群友金句】**")
                        day_block.extend(formatted_quotes)

            # 3. 用户称号
            if "user_titles" in sections:
                titles_raw = data_obj.get("user_titles")
                if isinstance(titles_raw, list) and titles_raw:
                    formatted_titles = []
                    for ut in titles_raw:
                        if isinstance(ut, dict):
                            uname = (
                                str(
                                    ut.get("user_name", "")
                                    or ut.get("name", "")
                                    or ut.get("nickname", "")
                                    or ut.get("user_id", "")
                                ).strip()
                            ) or "群友"
                            title = str(ut.get("title", "")).strip()
                            reason = str(ut.get("reason", "")).strip()
                            mbti = str(ut.get("mbti", "")).strip()
                            title_display = f"[{title}]" if title else ""
                            if mbti:
                                title_display = (
                                    f"[{title} | {mbti}]" if title else f"[{mbti}]"
                                )
                            item_str = f"{len(formatted_titles) + 1}. {uname}: {title_display}".rstrip()
                            if reason:
                                item_str += f"\n   - 理由: {reason}"
                            formatted_titles.append(item_str)
                    if formatted_titles:
                        day_block.append("\n**【群友称号画像】**")
                        day_block.extend(formatted_titles)

            # 4. 聊天质量分析
            if "chat_quality_review" in sections:
                quality_raw = data_obj.get("chat_quality_review")
                if isinstance(quality_raw, dict) and quality_raw:
                    summary = quality_raw.get("summary", "")
                    atmosphere = quality_raw.get("atmosphere", "")
                    depth = quality_raw.get("depth", "")
                    day_block.append("\n**【聊天氛围与质量总结】**")
                    if atmosphere:
                        day_block.append(f"- 交流氛围: {atmosphere}")
                    if depth:
                        day_block.append(f"- 讨论深度: {depth}")
                    if summary:
                        day_block.append(f"- 综合评述: {summary}")

            body_blocks.append("\n".join(day_block))

        full_content = "\n\n---\n\n".join(body_blocks)

        # Truncate content safely if exceeding threshold (strictly reserving suffix length)
        if len(full_content) > self.DEFAULT_MAX_CHARACTERS:
            suffix = (
                "\n\n[... 内容较长已自动截断，已返回前部分字符。"
                "建议通过缩小查询日期范围或指定特定模块（如 report_section='话题'）获取完整细节]"
            )
            avail_len = max(0, self.DEFAULT_MAX_CHARACTERS - len(suffix))
            truncated = full_content[:avail_len]
            return f"{truncated}{suffix}"

        return full_content

    def _get_cached_group_name(self, group_id: str) -> str:
        if not self.trace_store:
            return ""
        try:
            groups = self.trace_store.get_distinct_groups()
            for g in groups:
                if str(g.get("group_id", "")) == str(group_id):
                    return str(g.get("group_name", ""))
        except Exception:
            pass
        return ""

    @staticmethod
    def _replace_id_refs(text: str, id_to_name: dict[str, str]) -> str:
        """将文本中的裸用户 ID 引用 (如 [123456], [openid_xxx], @123456) 替换为 昵称(ID)。

        兼容多平台用户标识：支持纯数字 ID (QQ/Telegram) 及带字母下划线的 OpenID (QQ官方/Discord)。
        """
        if not text or not id_to_name:
            return text

        def _rep(m: re.Match[str]) -> str:
            uid = m.group(1) or m.group(2)
            if uid in id_to_name:
                return f"{id_to_name[uid]}({uid})"
            return m.group(0)

        # 匹配形如 [用户ID] 或 @用户ID，ID 长度 5~64 位字符
        return re.sub(r"\[([A-Za-z0-9_-]{5,64})\]|@([A-Za-z0-9_-]{5,64})", _rep, text)
