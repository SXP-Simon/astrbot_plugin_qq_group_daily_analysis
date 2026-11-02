"""从领域结果准备 Typst 数据，保留结构化用户引用，不经过 HTML。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from ...shared.report_language import format_report_date, resolve_report_language
from .profile_mappings import resolve_profile_info
from .render_data_preparer import RenderDataPreparer

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager
    from .avatar_service import AvatarService
    from .typst_resources import TypstAssets


class TextRun(TypedDict):
    """普通文本或带本地头像的用户引用。"""

    text: str
    avatar: str


class TypstTopic(TypedDict):
    title: str
    detail: list[TextRun]
    contributors: list[TextRun]


class TypstPortrait(TypedDict):
    name: str
    title: str
    profile: str
    reason: list[TextRun]
    avatar: str
    image: str
    image_fit: str
    opacity: float


class TypstQuote(TypedDict):
    sender: str
    content: list[TextRun]
    reason: list[TextRun]
    avatar: str


class TypstDimension(TypedDict):
    name: str
    percentage: float
    comment: list[TextRun]


class TypstReview(TypedDict):
    title: str
    subtitle: str
    summary: list[TextRun]
    dimensions: list[TypstDimension]


class TypstReportData(TypedDict):
    """可直接序列化的排版数据；不含 HTML、原始用户 ID 和外链图片。"""

    language: str
    font_language: str
    date: str
    generated_at: str
    message_count: int
    participant_count: int
    characters: int
    emoji_count: int
    peak: str
    hours: list[int]
    topics: list[TypstTopic]
    portraits: list[TypstPortrait]
    quotes: list[TypstQuote]
    review: TypstReview | None
    tokens: list[int]
    decorations: list[str]


class TypstDataPreparer:
    """为各主题复用身份净化、昵称和头像能力，生成原生 Typst 数据。"""

    def __init__(
        self,
        config: ConfigManager,
        avatars: AvatarService,
        assets: TypstAssets,
        result: AnalysisResultPayload,
        hide_names: bool,
        avatar_getter: Callable | None,
        nickname_getter: Callable | None,
        namespace: str | None,
        extended_ids: bool,
    ):
        self.config, self.avatars, self.assets = config, avatars, assets
        users = dict(result.get("user_analysis") or {})
        for portrait in result["user_titles"]:
            users.setdefault(str(portrait.user_id), {"nickname": portrait.name})
        for quote in result["statistics"].golden_quotes:
            if quote.user_id:
                users.setdefault(str(quote.user_id), {"nickname": quote.sender})
        self.result: AnalysisResultPayload = {**result, "user_analysis": users}
        self.hide_names, self.extended_ids = hide_names, extended_ids
        self.avatar_getter, self.nickname_getter, self.namespace = (
            avatar_getter,
            nickname_getter,
            namespace,
        )

    def plain(self, text: str) -> str:
        """净化标题、名称和多处正文片段中的身份信息。

        Args:
            text: 原始展示文本。

        Returns:
            匿名模式下移除已知身份的普通文本。
        """
        return RenderDataPreparer.sanitize_identity_text(
            text, self.result, self.hide_names
        )

    async def avatar(self, user_id: str) -> str:
        """通过平台隔离头像缓存获取并本地化头像。

        Args:
            user_id: 仅在准备阶段使用的身份编号。

        Returns:
            本次编译目录内的头像路径。
        """
        if not user_id:
            return ""
        source = await self.avatars.get_user_avatar(
            user_id, self.avatar_getter, self.namespace
        )
        return await self.assets.localize(source)

    async def rich_text(self, text: str) -> list[TextRun]:
        """将话题、金句和评价中的引用转为头像片段，不执行输入中的标记。

        Args:
            text: 含方括号用户引用或普通文本的内容。

        Returns:
            有顺序的普通文本与用户引用；匿名引用只保留头像。
        """
        users = self.result["user_analysis"]
        source = str(text)
        extended = self.hide_names or self.extended_ids
        if extended:
            for uid in sorted(users, key=len, reverse=True):
                source = re.sub(
                    rf"(?<!\[)(?<![A-Za-z0-9_-]){re.escape(uid)}(?![A-Za-z0-9_-])(?!\])",
                    f"[{uid}]",
                    source,
                )
        pattern = r"\[([A-Za-z0-9_-]{1,128})\]" if extended else r"\[(\d+)\]"
        runs: list[TextRun] = []
        position = 0
        for match in re.finditer(pattern, source):
            uid = match.group(1)
            if extended and uid not in users:
                continue
            runs.append(
                {"text": self.plain(source[position : match.start()]), "avatar": ""}
            )
            stats = users.get(uid)
            name = (
                str(stats.get("nickname") or stats.get("name") or "")
                if isinstance(stats, dict)
                else ""
            )
            if not name and self.nickname_getter and not self.hide_names:
                try:
                    name = str(await self.nickname_getter(uid) or "")
                except Exception:
                    name = ""
            if RenderDataPreparer.is_placeholder_display_name(name, uid):
                name = "群友" if self.extended_ids else uid
            runs.append(
                {
                    "text": "" if self.hide_names else name,
                    "avatar": await self.avatar(uid),
                }
            )
            position = match.end()
        runs.append({"text": self.plain(source[position:]), "avatar": ""})
        return runs

    async def prepare(
        self, profile_manifest: dict[str, dict], cdn_base_url: str
    ) -> TypstReportData:
        """按已有展示上限准备各主题共有的数据。

        Args:
            profile_manifest: 现有人格图片清单。
            cdn_base_url: 本轮资源镜像，供人格素材解析使用。

        Returns:
            无 HTML 和用户原始编号的报告数据。
        """
        result, config = self.result, self.config
        stats = result["statistics"]
        topics: list[TypstTopic] = []
        for topic in result["topics"][: config.get_max_topics()]:
            topics.append(
                {
                    "title": self.plain(topic.topic),
                    "detail": await self.rich_text(topic.detail),
                    "contributors": await self.rich_text("、".join(topic.contributors)),
                }
            )
        raw_overrides = config.get_profile_mapping_config()
        overrides = (
            {str(k): v for k, v in raw_overrides.items() if isinstance(v, dict)}
            if isinstance(raw_overrides, dict)
            else {}
        )
        portraits: list[TypstPortrait] = []
        for portrait in result["user_titles"][: config.get_max_user_titles()]:
            profile = resolve_profile_info(
                portrait.mbti,
                config.get_profile_display_mode(),
                overrides,
                profile_manifest,
                config,
                cdn_base_url,
            )
            portraits.append(
                {
                    "name": "" if self.hide_names else portrait.name,
                    "title": self.plain(portrait.title),
                    "profile": self.plain(str(profile["profile_display"])),
                    "reason": [{"text": self.plain(portrait.reason), "avatar": ""}],
                    "avatar": await self.avatar(str(portrait.user_id)),
                    "image": await self.assets.localize(
                        str(profile["profile_image"]),
                        min(1.0, max(0.0, float(profile["profile_image_opacity"]))),
                    ),
                    "image_fit": str(profile["profile_image_size_mode"]),
                    "opacity": min(
                        1.0, max(0.0, float(profile["profile_image_opacity"]))
                    ),
                }
            )
        quotes: list[TypstQuote] = []
        for quote in stats.golden_quotes[: config.get_max_golden_quotes()]:
            quotes.append(
                {
                    "sender": "" if self.hide_names else quote.sender,
                    "content": await self.rich_text(quote.content),
                    "reason": await self.rich_text(quote.reason),
                    "avatar": await self.avatar(str(quote.user_id or "")),
                }
            )
        review = result.get("chat_quality_review") or stats.chat_quality_review
        quality: TypstReview | None = None
        if review:
            quality = {
                "title": self.plain(review.title),
                "subtitle": self.plain(review.subtitle),
                "summary": await self.rich_text(review.summary),
                "dimensions": [
                    {
                        "name": self.plain(dim.name),
                        "percentage": max(0.0, min(100.0, dim.percentage)),
                        "comment": await self.rich_text(dim.comment),
                    }
                    for dim in review.dimensions
                ],
            }
        explicit_language = resolve_report_language(config)
        language = explicit_language or "zh-Hans"
        hourly = stats.activity_visualization.hourly_activity
        return {
            "language": language,
            "font_language": explicit_language
            or ("zh-Hant" if config.get_t2i_font_source() == "Overseas" else "zh-Hans"),
            "date": format_report_date(explicit_language, datetime.now()),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": stats.message_count,
            "participant_count": stats.participant_count,
            "characters": stats.total_characters,
            "emoji_count": stats.emoji_count,
            "peak": self.plain(stats.most_active_period),
            "hours": [
                max(0, int(hourly.get(hour, hourly.get(str(hour), 0))))
                for hour in range(24)
            ],
            "topics": topics,
            "portraits": portraits,
            "quotes": quotes,
            "review": quality,
            "tokens": [
                stats.token_usage.total_tokens,
                stats.token_usage.prompt_tokens,
                stats.token_usage.completion_tokens,
            ],
            "decorations": [],
        }
