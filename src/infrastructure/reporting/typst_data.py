"""从领域结果准备 Typst 数据，保留结构化用户引用，不经过 HTML。"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from ...shared.report_language import format_report_date, resolve_report_language
from .profile_mappings import resolve_profile_info
from .render_data_preparer import RenderDataPreparer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
    mbti: str
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
    color: str


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


@dataclass(frozen=True, slots=True)
class TypstIdentityOptions:
    """只在准备阶段使用的平台回调与身份展示选项。

    Args:
        avatar_getter: 平台头像地址查询。
        nickname_getter: 平台昵称查询。
        namespace: 平台缓存命名空间。
        hide_names: 是否隐藏群友身份。
        extended_ids: 是否允许字母数字身份编号。
    """

    avatar_getter: Callable[[str, int | None], Awaitable[str | None]] | None = None
    nickname_getter: Callable[[str], Awaitable[str | None]] | None = None
    namespace: str | None = None
    hide_names: bool = False
    extended_ids: bool = False


class TypstDataPreparer:
    """为各主题复用身份净化、昵称和头像能力，生成原生 Typst 数据。"""

    def __init__(
        self,
        config: ConfigManager,
        avatars: AvatarService,
        assets: TypstAssets,
        result: AnalysisResultPayload,
        identity: TypstIdentityOptions,
    ) -> None:
        """补齐结果中出现的成员，并固定本轮身份展示行为。

        Args:
            config: 内容展示上限与人格映射配置。
            avatars: 平台隔离头像服务。
            assets: 本次任务的图片本地化器。
            result: 原始领域分析结果，不在原地修改其用户映射。
            identity: 平台回调、匿名开关与身份编号规则。
        """
        self.config, self.avatars, self.assets = config, avatars, assets
        users = dict(result.get("user_analysis") or {})
        for portrait in result["user_titles"]:
            users.setdefault(str(portrait.user_id), {"nickname": portrait.name})
        for quote in result["statistics"].golden_quotes:
            if quote.user_id:
                users.setdefault(str(quote.user_id), {"nickname": quote.sender})
        self.result: AnalysisResultPayload = {**result, "user_analysis": users}
        self.hide_names, self.extended_ids = identity.hide_names, identity.extended_ids
        self.avatar_getter, self.nickname_getter, self.namespace = (
            identity.avatar_getter,
            identity.nickname_getter,
            identity.namespace,
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

    async def avatar(self, user_id: str, *, oval: bool = False) -> str:
        """通过平台隔离头像缓存获取并本地化头像。

        Args:
            user_id: 仅在准备阶段使用的身份编号。
            oval: 是否采用 Maria 椭圆肖像；正文提及仍使用圆形头像。

        Returns:
            本次编译目录内的头像路径。
        """
        if not user_id:
            return ""
        try:
            async with asyncio.timeout_at(self.assets.network_deadline):
                source = await self.avatars.get_user_avatar(
                    user_id, self.avatar_getter, self.namespace
                )
        except TimeoutError:
            self.assets.network_budget_exhausted = True
            return ""
        return await self.assets.localize(source, oval=oval)

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
            name = await self._user_name(uid)
            runs.append(
                {
                    "text": "" if self.hide_names else name,
                    "avatar": await self.avatar(uid),
                }
            )
            position = match.end()
        runs.append({"text": self.plain(source[position:]), "avatar": ""})
        return runs

    async def _user_name(self, uid: str) -> str:
        """在可选网络预算内查询昵称，超时仍保留原有身份占位规则。

        Args:
            uid: 当前提及的成员编号。

        Returns:
            可展示昵称，或原有的群友/编号占位文字。
        """
        stats = self.result["user_analysis"].get(uid)
        name = (
            str(stats.get("nickname") or stats.get("name") or "")
            if isinstance(stats, dict)
            else ""
        )
        if not name and self.nickname_getter and not self.hide_names:
            try:
                async with asyncio.timeout_at(self.assets.network_deadline):
                    name = str(await self.nickname_getter(uid) or "")
            except TimeoutError:
                self.assets.network_budget_exhausted = True
            except Exception:
                name = ""
        if RenderDataPreparer.is_placeholder_display_name(name, uid):
            return "群友" if self.extended_ids else uid
        return name

    async def prepare(
        self, profile_manifest: dict[str, dict], cdn_base_url: str, theme: str = ""
    ) -> TypstReportData:
        """按已有展示上限准备各主题共有的数据。

        Args:
            profile_manifest: 现有人格图片清单。
            cdn_base_url: 本轮资源镜像，供人格素材解析使用。
            theme: 本轮实际主题，用于保留主题固定的水印透明度。

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
        portraits = await self._prepare_portraits(profile_manifest, cdn_base_url, theme)
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
                        "color": dim.color
                        if re.fullmatch(
                            r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", dim.color
                        )
                        else "#607d8b",
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

    async def _prepare_portraits(
        self, profile_manifest: dict[str, dict], cdn_base_url: str, theme: str
    ) -> list[TypstPortrait]:
        """解析人格映射并本地化画像资源，保留主题固定的裁切和水印。

        Args:
            profile_manifest: 人格装饰清单。
            cdn_base_url: 本轮图片镜像。
            theme: 当前主题。

        Returns:
            已完成身份净化与图片准备的画像数据。
        """
        config = self.config
        raw_overrides = config.get_profile_mapping_config()
        overrides = (
            {str(k): v for k, v in raw_overrides.items() if isinstance(v, dict)}
            if isinstance(raw_overrides, dict)
            else {}
        )
        portraits: list[TypstPortrait] = []
        for portrait in self.result["user_titles"][: config.get_max_user_titles()]:
            profile = resolve_profile_info(
                portrait.mbti,
                config.get_profile_display_mode(),
                overrides,
                profile_manifest,
                config,
                cdn_base_url,
            )
            opacity = (
                0.18
                if theme == "maria"
                else min(1.0, max(0.0, float(profile["profile_image_opacity"])))
            )
            portraits.append(
                {
                    "name": "" if self.hide_names else portrait.name,
                    "title": self.plain(portrait.title),
                    "profile": self.plain(str(profile["profile_display"])),
                    "mbti": self.plain(portrait.mbti),
                    "reason": [{"text": self.plain(portrait.reason), "avatar": ""}],
                    "avatar": await self.avatar(
                        str(portrait.user_id), oval=theme == "maria"
                    ),
                    "image": await self.assets.localize(
                        str(profile["profile_image"]),
                        opacity,
                    ),
                    "image_fit": str(profile["profile_image_size_mode"]),
                    "opacity": opacity,
                }
            )
        return portraits
