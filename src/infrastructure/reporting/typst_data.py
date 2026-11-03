"""从领域结果准备 Typst 数据，保留结构化用户引用，不经过 HTML。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ...shared.report_language import format_report_date, resolve_report_language
from .profile_mappings import resolve_profile_info
from .typst_identity import TypstIdentityResolver

if TYPE_CHECKING:
    from ...domain.value_objects import AnalysisResultPayload, QualityReview
    from ..config.config_manager import ConfigManager
    from .avatar_service import AvatarService
    from .typst_contracts import (
        TypstIdentityOptions,
        TypstPortrait,
        TypstQuote,
        TypstReportData,
        TypstReview,
        TypstTopic,
    )
    from .typst_resources import TypstAssets


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
        self.identity = TypstIdentityResolver(avatars, assets, result, identity)
        self.result = self.identity.result

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
                    "title": self.identity.plain(topic.topic),
                    "detail": await self.identity.rich_text(topic.detail),
                    "contributors": await self.identity.rich_text(
                        "、".join(topic.contributors)
                    ),
                }
            )
        portraits = await self._prepare_portraits(profile_manifest, cdn_base_url, theme)
        quotes: list[TypstQuote] = []
        for quote in stats.golden_quotes[: config.get_max_golden_quotes()]:
            quotes.append(
                {
                    "sender": "" if self.identity.hide_names else quote.sender,
                    "content": await self.identity.rich_text(quote.content),
                    "reason": await self.identity.rich_text(quote.reason),
                    "avatar": await self.identity.avatar(str(quote.user_id or "")),
                }
            )
        review = result.get("chat_quality_review") or stats.chat_quality_review
        quality = await self._prepare_review(review)
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
            "peak": self.identity.plain(stats.most_active_period),
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
                    "name": "" if self.identity.hide_names else portrait.name,
                    "title": self.identity.plain(portrait.title),
                    "profile": self.identity.plain(str(profile["profile_display"])),
                    "mbti": self.identity.plain(portrait.mbti),
                    "reason": [
                        {"text": self.identity.plain(portrait.reason), "avatar": ""}
                    ],
                    "avatar": await self.identity.avatar(
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

    async def _prepare_review(self, review: QualityReview | None) -> TypstReview | None:
        """Prepare review text and validate its visual values independently.

        Args:
            review: Domain review shared with the HTML report.

        Returns:
            Sanitized native review or None when absent.
        """
        if not review:
            return None
        return {
            "title": self.identity.plain(review.title),
            "subtitle": self.identity.plain(review.subtitle),
            "summary": await self.identity.rich_text(review.summary),
            "dimensions": [
                {
                    "name": self.identity.plain(dim.name),
                    "percentage": max(0.0, min(100.0, dim.percentage)),
                    "comment": await self.identity.rich_text(dim.comment),
                    "color": dim.color
                    if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", dim.color)
                    else "#607d8b",
                }
                for dim in review.dimensions
            ],
        }
