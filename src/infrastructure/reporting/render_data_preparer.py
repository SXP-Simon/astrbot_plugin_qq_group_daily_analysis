"""
渲染数据准备器 (Render Data Preparer)

负责组装 Jinja2 模板渲染所需的完整数据字典，包括：
- 用户身份信息脱敏（支持 hide_user_names 与导出 JSON 净化）
- 用户引用气泡胶囊与纯头像渲染
- 话题、金句、称号与聊天质量数据的上下文格式化
- 图表数据与 CDN 镜像静态资源的路径注入
"""

from __future__ import annotations

import asyncio
import copy
import html
import json
import re
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from markupsafe import Markup

from ...utils.logger import logger
from .avatar_service import AvatarService
from .profile_mappings import resolve_profile_info

if TYPE_CHECKING:
    from ..visualization.activity_charts import ActivityVisualizer
    from .templates import HTMLTemplates

DEFAULT_MIKU_ASSETS_CDN_URL = "https://jsd.onmicrosoft.cn/gh/SXP-Simon/daily_analysis_assets@assets/miku_assets/assets"
DEFAULT_NPM_CDN_URL = "https://jsd.onmicrosoft.cn/npm"
DEFAULT_ASSETS_CDN_URL = (
    "https://jsd.onmicrosoft.cn/gh/SXP-Simon/daily_analysis_assets@assets"
)


class RenderDataPreparer:
    """模板渲染数据准备与安全脱敏服务。"""

    def __init__(
        self,
        config_manager: Any,
        avatar_service: AvatarService,
        html_templates: HTMLTemplates,
        activity_visualizer: ActivityVisualizer,
        profile_asset_manifest: dict[str, dict] | None = None,
    ):
        """初始化渲染数据准备器。

        Args:
            config_manager: 配置管理器。
            avatar_service: 用户头像处理服务。
            html_templates: HTML 模板引擎。
            activity_visualizer: 活跃度图表生成器。
            profile_asset_manifest: 人格静态资源清单。
        """
        self.config_manager = config_manager
        self.avatar_service = avatar_service
        self.html_templates = html_templates
        self.activity_visualizer = activity_visualizer
        self.profile_asset_manifest = profile_asset_manifest or {}

    def get_profile_mapping_overrides(self) -> dict[str, dict]:
        """解析用户配置的人格映射覆盖项。"""
        raw = (
            self.config_manager.get_profile_mapping_config()
            if hasattr(self.config_manager, "get_profile_mapping_config")
            else ""
        )
        if not raw:
            return {}

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"人格映射配置 JSON 解析失败，已回退到默认映射: {e}")
        return {}

    def sanitize_analysis_result_for_export(
        self, analysis_result: dict
    ) -> dict[str, Any]:
        """导出 HTML Sidecar JSON 前脱敏敏感身份信息。

        Args:
            analysis_result: 原始分析结果字典。

        Returns:
            脱敏后的纯净数据字典。
        """
        sanitized = self.to_plain_export_data(copy.deepcopy(analysis_result))
        sanitized["user_analysis"] = {}
        for topic in sanitized.get("topics", []):
            if not isinstance(topic, dict):
                continue
            topic["contributors"] = []
            topic["contributor_ids"] = []
        for title in sanitized.get("user_titles", []):
            if not isinstance(title, dict):
                continue
            title["name"] = ""
            title["user_id"] = ""
        stats = sanitized.get("statistics")
        if isinstance(stats, dict):
            for golden_quote in stats.get("golden_quotes", []) or []:
                if not isinstance(golden_quote, dict):
                    continue
                golden_quote["sender"] = ""
                golden_quote["user_id"] = ""

            activity_visualization = stats.get("activity_visualization")
            if isinstance(activity_visualization, dict):
                activity_visualization["user_activity_ranking"] = []

        for golden_quote in sanitized.get("golden_quotes", []) or []:
            if not isinstance(golden_quote, dict):
                continue
            golden_quote["sender"] = ""
            golden_quote["user_id"] = ""

        return self.sanitize_export_identity_text(sanitized, analysis_result)  # type: ignore[return-type]

    @classmethod
    def to_plain_export_data(cls, value: Any) -> Any:
        """递归转换领域模型为普通字典与列表。

        Args:
            value: 任意输入对象。

        Returns:
            JSON 兼容的纯原生结构。
        """
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return cls.to_plain_export_data(value.to_dict())
        if is_dataclass(value) and not isinstance(value, type):
            return cls.to_plain_export_data(asdict(value))
        if isinstance(value, dict):
            return {key: cls.to_plain_export_data(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls.to_plain_export_data(item) for item in value]
        return value

    def sanitize_export_identity_text(self, value: Any, analysis_result: dict) -> Any:
        """从导出的文本字段中去除用户名称与 ID。

        Args:
            value: 输入的文本或容器。
            analysis_result: 包含用户名单的原始分析字典。

        Returns:
            去除用户标识后的结构。
        """
        if isinstance(value, str):
            return self.sanitize_identity_text(value, analysis_result, True)
        if isinstance(value, dict):
            return {
                key: self.sanitize_export_identity_text(item, analysis_result)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self.sanitize_export_identity_text(item, analysis_result)
                for item in value
            ]
        return value

    async def prepare_render_data(
        self,
        analysis_result: dict,
        template_theme: str | None = None,
        chart_template: str = "activity_chart.html",
        avatar_url_getter: Callable | None = None,
        nickname_getter: Callable | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
    ) -> dict:
        """组装模板引擎所需的完整数据字典。

        Args:
            analysis_result: 分析结果对象字典。
            template_theme: 模板主题名称。
            chart_template: 活跃度图表子模板。
            avatar_url_getter: 头像 URL 异步获取回调。
            nickname_getter: 用户昵称异步获取回调。
            avatar_cache_namespace: 平台隔离的头像缓存命名空间。
            hide_user_names: 是否匿名化渲染（纯头像模式）。
            allow_alphanumeric_user_ids: 是否允许字母数字用户 ID 识别。

        Returns:
            dict: 包含全量模板渲染变量的字典。
        """
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]
        activity_viz = stats.activity_visualization

        max_topics = self.config_manager.get_max_topics()
        topics_list = []
        user_analysis = analysis_result.get("user_analysis")
        avatar_reuse_registry: dict[str, str] = {}
        avatar_reuse_aliases: dict[str, str] = {}

        avatar_user_ids: set[str] = set()
        known_user_ids = {
            str(user_id).strip()
            for user_id in (user_analysis or {})
            if str(user_id).strip()
        }
        max_user_titles = self.config_manager.get_max_user_titles()
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        for title in user_titles[:max_user_titles]:
            user_id = str(getattr(title, "user_id", "") or "").strip()
            if user_id:
                avatar_user_ids.add(user_id)
        for golden_quote in stats.golden_quotes[:max_golden_quotes]:
            user_id = str(getattr(golden_quote, "user_id", "") or "").strip()
            if user_id:
                avatar_user_ids.add(user_id)
        mention_sources = []
        for topic in topics[:max_topics]:
            if hide_user_names:
                avatar_user_ids.update(
                    str(user_id).strip()
                    for user_id in (getattr(topic, "contributor_ids", []) or [])
                    if str(user_id).strip()
                )
            mention_sources.append(str(getattr(topic, "detail", "") or ""))
        mention_sources.extend(
            str(getattr(golden_quote, "reason", "") or "")
            for golden_quote in stats.golden_quotes[:max_golden_quotes]
        )
        if hide_user_names:
            mention_sources.extend(
                str(getattr(title, "reason", "") or "")
                for title in user_titles[:max_user_titles]
            )
        for source in mention_sources:
            avatar_user_ids.update(
                matched_user_id
                for matched_user_id in re.findall(r"\[([A-Za-z0-9_-]{1,128})\]", source)
                if matched_user_id in known_user_ids
            )
        if avatar_user_ids:
            await asyncio.gather(
                *(
                    self.avatar_service.get_user_avatar(
                        user_id, avatar_url_getter, avatar_cache_namespace
                    )
                    for user_id in avatar_user_ids
                )
            )

        for i, topic in enumerate(topics[:max_topics], 1):
            processed_detail = await self.render_mentions(
                topic.detail,
                avatar_url_getter,
                nickname_getter,
                user_analysis,
                avatar_cache_namespace,
                avatar_reuse_registry,
                avatar_reuse_aliases,
                hide_user_names=hide_user_names,
                allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
            )
            if hide_user_names:
                contributors = await self.render_avatar_only_ids(
                    getattr(topic, "contributor_ids", []) or [],
                    avatar_url_getter,
                    avatar_cache_namespace,
                    avatar_reuse_registry,
                    avatar_reuse_aliases,
                )
            else:
                contributors = "、".join(topic.contributors)
            topics_list.append(
                {
                    "index": i,
                    "topic": {
                        "topic": self.sanitize_identity_text(
                            topic.topic, analysis_result, hide_user_names
                        )
                    },
                    "contributors": contributors,
                    "detail": processed_detail,
                }
            )

        common_context = {
            "hide_user_names": hide_user_names,
            "t2i_font_source": self.config_manager.get_t2i_font_source(),
            "t2i_google_fonts_mirror": (
                self.config_manager.get_t2i_google_fonts_mirror()
            ),
            "t2i_gstatic_mirror": self.config_manager.get_t2i_gstatic_mirror(),
            "t2i_atri_font_mirror": (self.config_manager.get_t2i_atri_font_mirror()),
            "t2i_miku_assets_mirror": DEFAULT_MIKU_ASSETS_CDN_URL,
            "t2i_npm_mirror": DEFAULT_NPM_CDN_URL,
            "cdn_assets_base": DEFAULT_ASSETS_CDN_URL,
        }

        topics_html = (
            self.html_templates.render_template(
                "topic_item.html",
                template_theme=template_theme,
                topics=topics_list,
                **common_context,
            )
            if topics_list
            else ""
        )
        logger.debug(f"话题HTML生成完成，长度: {len(topics_html)}")

        titles_list = []
        profile_mode = self.config_manager.get_profile_display_mode()
        profile_mapping_overrides = self.get_profile_mapping_overrides()
        for title in user_titles[:max_user_titles]:
            user_id = str(title.user_id)
            avatar_data = await self.avatar_service.get_user_avatar(
                user_id, avatar_url_getter, avatar_cache_namespace
            )
            self.avatar_service.register_reusable_avatar(
                avatar_data,
                avatar_reuse_registry,
                avatar_reuse_aliases,
                avatar_key=self.avatar_service.get_avatar_cache_key(
                    user_id, avatar_cache_namespace
                ),
            )
            profile_info = resolve_profile_info(
                title.mbti,
                profile_mode,
                profile_mapping_overrides,
                self.profile_asset_manifest,
                self.config_manager,
            )
            title_reason = title.reason
            if hide_user_names:
                title_reason = await self.render_mentions(
                    title.reason,
                    avatar_url_getter,
                    nickname_getter,
                    user_analysis,
                    avatar_cache_namespace,
                    avatar_reuse_registry,
                    avatar_reuse_aliases,
                    hide_user_names=True,
                    allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
                )
            title_data = {
                "name": "" if hide_user_names else title.name,
                "title": title.title,
                "mbti": title.mbti,
                "reason": title_reason,
                "avatar_data": avatar_data,
            }
            title_data.update(profile_info)
            titles_list.append(title_data)

        titles_html = (
            self.html_templates.render_template(
                "user_title_item.html",
                template_theme=template_theme,
                titles=titles_list,
                **common_context,
            )
            if titles_list
            else ""
        )
        logger.debug(f"用户称号HTML生成完成，长度: {len(titles_html)}")

        quotes_list = []
        for golden_quote in stats.golden_quotes[:max_golden_quotes]:
            quote_user_id = str(golden_quote.user_id) if golden_quote.user_id else None
            avatar_url = (
                await self.avatar_service.get_user_avatar(
                    quote_user_id,
                    avatar_url_getter,
                    avatar_cache_namespace,
                )
                if quote_user_id
                else None
            )
            if quote_user_id:
                self.avatar_service.register_reusable_avatar(
                    avatar_url,
                    avatar_reuse_registry,
                    avatar_reuse_aliases,
                    avatar_key=self.avatar_service.get_avatar_cache_key(
                        quote_user_id, avatar_cache_namespace
                    ),
                )
            processed_reason = await self.render_mentions(
                golden_quote.reason,
                avatar_url_getter,
                nickname_getter,
                user_analysis,
                avatar_cache_namespace,
                avatar_reuse_registry,
                avatar_reuse_aliases,
                hide_user_names=hide_user_names,
                allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
            )
            quotes_list.append(
                {
                    "content": self.sanitize_identity_text(
                        golden_quote.content, analysis_result, hide_user_names
                    ),
                    "sender": "" if hide_user_names else golden_quote.sender,
                    "reason": processed_reason,
                    "avatar_url": avatar_url,
                }
            )

        quotes_html = (
            self.html_templates.render_template(
                "quote_item.html",
                template_theme=template_theme,
                quotes=quotes_list,
                **common_context,
            )
            if quotes_list
            else ""
        )
        logger.debug(f"金句HTML生成完成，长度: {len(quotes_html)}")

        chart_data = self.activity_visualizer.get_hourly_chart_data(
            activity_viz.hourly_activity
        )
        hourly_chart_html = self.html_templates.render_template(
            chart_template,
            template_theme=template_theme,
            chart_data=chart_data,
            **common_context,
        )
        logger.debug(f"活跃度图表HTML生成完成，长度: {len(hourly_chart_html)}")

        chat_quality_html = ""
        chat_quality_review = analysis_result.get("chat_quality_review")
        if not chat_quality_review and hasattr(stats, "chat_quality_review"):
            chat_quality_review = stats.chat_quality_review

        if chat_quality_review:
            if hasattr(chat_quality_review, "dimensions"):
                review_data = {
                    "title": chat_quality_review.title,
                    "subtitle": chat_quality_review.subtitle,
                    "dimensions": [
                        {
                            "name": d.name,
                            "percentage": d.percentage,
                            "comment": d.comment,
                            "color": d.color,
                        }
                        for d in chat_quality_review.dimensions
                    ],
                    "summary": chat_quality_review.summary,
                }
            else:
                review_data = chat_quality_review

            if hide_user_names and isinstance(review_data, dict):
                review_data = {
                    **review_data,
                    "title": self.sanitize_identity_text(
                        review_data.get("title", ""), analysis_result, True
                    ),
                    "subtitle": self.sanitize_identity_text(
                        review_data.get("subtitle", ""), analysis_result, True
                    ),
                    "summary": self.sanitize_identity_text(
                        review_data.get("summary", ""), analysis_result, True
                    ),
                    "dimensions": [
                        {
                            **dimension,
                            "name": self.sanitize_identity_text(
                                dimension.get("name", ""), analysis_result, True
                            ),
                            "comment": self.sanitize_identity_text(
                                dimension.get("comment", ""),
                                analysis_result,
                                True,
                            ),
                        }
                        for dimension in review_data.get("dimensions", [])
                        if isinstance(dimension, dict)
                    ],
                }

            chat_quality_html = self.html_templates.render_template(
                "chat_quality_item.html",
                template_theme=template_theme,
                **review_data,
                **common_context,
            )
            logger.debug(f"聊天质量锐评HTML生成完成，长度: {len(chat_quality_html)}")

        render_data = {
            "t2i_font_source": self.config_manager.get_t2i_font_source(),
            "t2i_google_fonts_mirror": (
                self.config_manager.get_t2i_google_fonts_mirror()
            ),
            "t2i_gstatic_mirror": self.config_manager.get_t2i_gstatic_mirror(),
            "t2i_atri_font_mirror": (self.config_manager.get_t2i_atri_font_mirror()),
            "t2i_miku_assets_mirror": DEFAULT_MIKU_ASSETS_CDN_URL,
            "t2i_npm_mirror": DEFAULT_NPM_CDN_URL,
            "cdn_assets_base": DEFAULT_ASSETS_CDN_URL,
            "current_date": datetime.now().strftime("%Y年%m月%d日"),
            "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": stats.message_count,
            "participant_count": stats.participant_count,
            "total_characters": stats.total_characters,
            "emoji_count": stats.emoji_count,
            "most_active_period": stats.most_active_period,
            "topics_html": topics_html,
            "titles_html": titles_html,
            "quotes_html": quotes_html,
            "hourly_chart_html": hourly_chart_html,
            "chat_quality_html": chat_quality_html,
            "total_tokens": (
                stats.token_usage.total_tokens if stats.token_usage.total_tokens else 0
            ),
            "prompt_tokens": (
                stats.token_usage.prompt_tokens
                if stats.token_usage.prompt_tokens
                else 0
            ),
            "completion_tokens": (
                stats.token_usage.completion_tokens
                if stats.token_usage.completion_tokens
                else 0
            ),
            "avatar_reuse_registry": avatar_reuse_registry,
            "avatar_reuse_aliases": avatar_reuse_aliases,
        }

        logger.debug(f"渲染数据准备完成，包含 {len(render_data)} 个字段")
        return render_data

    async def render_avatar_only_ids(
        self,
        user_ids: list[str],
        avatar_url_getter: Callable | None,
        avatar_cache_namespace: str | None,
        avatar_reuse_registry: dict[str, str] | None,
        avatar_reuse_aliases: dict[str, str] | None,
    ) -> Markup:
        """渲染纯头像图标列表。

        Args:
            user_ids: 用户 ID 列表。
            avatar_url_getter: 头像获取回调。
            avatar_cache_namespace: 平台隔离的头像缓存命名空间。
            avatar_reuse_registry: 头像 Base64 复用注册表。
            avatar_reuse_aliases: 头像别名映射表。

        Returns:
            Markup: 渲染好的头像 HTML 片段。
        """
        avatars: list[Markup] = []
        for raw_user_id in user_ids:
            user_id = str(raw_user_id or "").strip()
            if not user_id:
                continue
            avatar_url = await self.avatar_service.get_user_avatar(
                user_id, avatar_url_getter, avatar_cache_namespace
            )
            avatar_ref = self.avatar_service.register_reusable_avatar(
                avatar_url,
                avatar_reuse_registry,
                avatar_reuse_aliases,
                avatar_key=self.avatar_service.get_avatar_cache_key(
                    user_id, avatar_cache_namespace
                ),
            )
            style = (
                "width:24px;height:24px;border-radius:50%;display:inline-block;"
                "vertical-align:middle;margin:0 2px;background-size:cover;"
                "background-position:center;background-repeat:no-repeat;"
            )
            if avatar_ref:
                avatars.append(
                    Markup(
                        f'<span class="user-capsule-avatar" '
                        f'data-avatar-ref="{html.escape(avatar_ref, quote=True)}" '
                        f'style="{style}"></span>'
                    )
                )
            else:
                avatars.append(
                    Markup(
                        f'<img src="{html.escape(avatar_url, quote=True)}" '
                        f'style="{style}">'
                    )
                )
        return Markup("").join(avatars)

    async def render_mentions(
        self,
        text: str,
        avatar_url_getter: Callable | None,
        nickname_getter: Callable | None = None,
        user_analysis: dict | None = None,
        avatar_cache_namespace: str | None = None,
        avatar_reuse_registry: dict[str, str] | None = None,
        avatar_reuse_aliases: dict[str, str] | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
    ) -> Markup:
        """将文本中的用户引用替换为头像气泡胶囊。

        Args:
            text: 包含 [123456] 形式用户引用的原始文本。
            avatar_url_getter: 头像获取回调。
            nickname_getter: 昵称获取回调。
            user_analysis: 领域用户活跃度与昵称字典。
            avatar_cache_namespace: 平台隔离的头像缓存命名空间。
            avatar_reuse_registry: 头像 Base64 复用注册表。
            avatar_reuse_aliases: 头像别名映射表。
            hide_user_names: 是否匿名化。
            allow_alphanumeric_user_ids: 是否允许非纯数字 ID。

        Returns:
            Markup: 替换后的安全 HTML Markup。
        """
        if not text:
            return Markup("")

        known_ids = {
            str(user_id).strip()
            for user_id in (user_analysis or {})
            if str(user_id).strip()
        }
        source_text = str(text)
        supports_extended_ids = hide_user_names or allow_alphanumeric_user_ids
        if supports_extended_ids:
            for user_id in sorted(known_ids, key=len, reverse=True):
                source_text = re.sub(
                    rf"(?<!\[)(?<![A-Za-z0-9_-]){re.escape(user_id)}"
                    rf"(?![A-Za-z0-9_-])(?!\])",
                    f"[{user_id}]",
                    source_text,
                )

        pattern = (
            r"\[([A-Za-z0-9_-]{1,128})\]" if supports_extended_ids else r"\[(\d+)\]"
        )

        matches = list(re.finditer(pattern, source_text))
        if not matches:
            return self.escape_text_segment(source_text)

        async def render_capsule(match: re.Match[str]) -> Markup:
            uid = match.group(1)
            if supports_extended_ids and uid not in known_ids:
                return Markup(html.escape(f"[{uid}]", quote=True))
            url = await self.avatar_service.get_user_avatar(
                uid, avatar_url_getter, avatar_cache_namespace
            )

            name = None
            if user_analysis and uid in user_analysis:
                stats = user_analysis[uid]
                name = stats.get("nickname") or stats.get("name")
                if self.is_placeholder_display_name(name, uid):
                    name = None

            if not name and nickname_getter:
                try:
                    name = await nickname_getter(uid)
                    if self.is_placeholder_display_name(name, uid):
                        name = None
                except Exception as e:
                    logger.warning(f"获取昵称失败 {uid}: {e}")

            capsule_style = (
                "display:inline-flex;align-items:center;background:rgba(0,0,0,0.05);"
                "padding:2px 6px 2px 2px;border-radius:12px;margin:0 2px;"
                "vertical-align:middle;border:1px solid rgba(0,0,0,0.1);text-decoration:none;"
            )
            img_style = (
                "width:18px;height:18px;border-radius:50%;"
                f"margin-right:{'0' if hide_user_names else '4px'};display:block;"
            )
            name_style = "font-size:0.85em;color:inherit;font-weight:500;line-height:1;"

            final_url = url if url else self.avatar_service.get_default_avatar_base64()
            final_name = (
                name
                if (name and not self.is_placeholder_display_name(name, uid))
                else ("群友" if allow_alphanumeric_user_ids else str(uid))
            )

            avatar_ref = self.avatar_service.register_reusable_avatar(
                final_url,
                avatar_reuse_registry,
                avatar_reuse_aliases,
                avatar_key=self.avatar_service.get_avatar_cache_key(
                    uid, avatar_cache_namespace
                ),
            )
            if avatar_ref:
                avatar_html = (
                    f'<span class="user-capsule-avatar" '
                    f'data-avatar-ref="{html.escape(avatar_ref, quote=True)}" '
                    f'style="{img_style}background-size:cover;background-position:center;'
                    'background-repeat:no-repeat;flex-shrink:0;"></span>'
                )
            else:
                avatar_html = (
                    f'<img src="{html.escape(final_url, quote=True)}" '
                    f'style="{img_style}">'
                )

            name_html = (
                ""
                if hide_user_names
                else (f'<span style="{name_style}">{html.escape(final_name)}</span>')
            )
            return Markup(
                f'<span class="user-capsule" style="{capsule_style}">'
                f"{avatar_html}{name_html}</span>"
            )

        result: list[Markup | str] = []
        last_end = 0
        for match in matches:
            result.append(
                self.escape_text_segment(source_text[last_end : match.start()])
            )
            result.append(await render_capsule(match))
            last_end = match.end()

        result.append(self.escape_text_segment(source_text[last_end:]))
        return Markup("").join(result)

    @staticmethod
    def sanitize_identity_text(
        text: str, analysis_result: dict, hide_user_names: bool
    ) -> str:
        """从字符串中消除用户标识。

        Args:
            text: 待处理文本。
            analysis_result: 包含用户名单的原始分析字典。
            hide_user_names: 是否开启匿名。

        Returns:
            处理后的脱敏文本。
        """
        if not hide_user_names:
            return str(text)
        sanitized = str(text)
        user_analysis = analysis_result.get("user_analysis") or {}
        known_ids = {
            str(user_id).strip() for user_id in user_analysis if str(user_id).strip()
        }
        known_names = set()
        for stats in user_analysis.values():
            if not isinstance(stats, dict):
                continue
            for key in ("nickname", "name"):
                value = str(stats.get(key, "") or "").strip()
                if value:
                    known_names.add(value)
        for identity in sorted(known_ids | known_names, key=len, reverse=True):
            sanitized = sanitized.replace(identity, "")
        return re.sub(r"\[\s*\]", "", sanitized)

    @staticmethod
    def escape_text_segment(text: str) -> Markup:
        """转义文本并转换换行符为 `<br>`。

        Args:
            text: 纯文本片段。

        Returns:
            Markup: HTML 转义后的片段。
        """
        return Markup(html.escape(text, quote=False).replace("\n", "<br>"))

    @staticmethod
    def is_placeholder_display_name(name: str | None, user_id: str) -> bool:
        """判断展示名称是否为占位值。

        Args:
            name: 待判断的昵称字符串。
            user_id: 用户唯一标识。

        Returns:
            bool: 是否为占位名称。
        """
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {
            "unknown",
            "none",
            "null",
            "nil",
            "undefined",
        }:
            return True
        return normalized == str(user_id).strip()
