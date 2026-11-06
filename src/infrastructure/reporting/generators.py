"""报告生成器模块

负责生成图片、HTML、纯文本等多种格式的群聊日常分析报告，协调模板引擎与渲染流。
"""

from __future__ import annotations

import asyncio
import html as html_module
import json
import os
import re
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from PIL import Image

from ...domain.repositories.report_repository import IReportGenerator
from ...shared.constants import (
    IMAGE_RENDER_TOTAL_TIMEOUT_SECONDS as _RENDER_TOTAL_TIMEOUT_SECONDS,
)
from ...shared.constants import (
    AnalysisStage,
)
from ...shared.trace_context import TraceContext
from ...shared.type_guards import is_object_list, is_string_mapping
from ...utils.logger import logger
from ..visualization.activity_charts import ActivityVisualizer
from .avatar_service import (
    AvatarService,
)
from .custom_t2i_client import render_custom_t2i
from .image_backends import CustomImageBackend, HostImageBackend, NativeImageBackend
from .image_preparation import ImageReportRequest
from .image_rendering import ImageReportSession
from .markdown_report_generator import (
    MarkdownReportGenerator,
)
from .profile_mappings import (
    build_profile_image_from_manifest_pattern,
    get_manifest_profile_item_by_mbti,
    load_profile_asset_manifest,
    resolve_profile_info,
)
from .render_data_preparer import RenderDataPreparer, RenderTemplateContext
from .render_diagnostics import (
    RenderAttemptRecord,
    build_safe_report_path,
    diagnose_non_image_payload,
    resolve_t2i_viewport_options,
    sanitize_path_component,
    summarize_render_error,
)
from .templates import HTMLTemplates
from .typst_contracts import TypstIdentityOptions
from .typst_renderer import TypstReportRenderer

# 产物内嵌追踪号的 meta 名称与匹配模式（注入与自愈共用同一套定义）
_TRACE_META_ATTR = "astrbot-trace-id"
_TRACE_META_PATTERN = re.compile(
    rf'<meta[^>]*\bname=["\']{_TRACE_META_ATTR}["\'][^>]*>',
    re.IGNORECASE,
)
_HTML_HEAD_PATTERN = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import aiohttp
    from markupsafe import Markup

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager
    from ..config.rendering_config import (
        FontMode,
        RenderingResourceConfig,
        ScreenshotOptions,
    )
    from ..persistence.kv_contracts import CacheAccess


class ReportGenerator(IReportGenerator):
    """报告生成器 - 负责全格式群聊分析报告的数据装配与渲染。"""

    config_manager: ConfigManager
    data_dir: Path
    activity_visualizer: ActivityVisualizer
    html_templates: HTMLTemplates | None
    _render_semaphore: asyncio.Semaphore
    _avatar_cache: CacheAccess | None = None
    _profile_asset_manifest: dict[str, dict[str, dict[str, object]]]
    _preparer: RenderDataPreparer
    _markdown_generator_inst: MarkdownReportGenerator | None = None
    _avatar_service_inst: AvatarService | None = None
    _avatar_session: aiohttp.ClientSession | None = None
    _avatar_session_lock: asyncio.Lock | None = None
    _avatar_session_concurrent_semaphore: asyncio.Semaphore | None = None
    _avatar_failure_cache: dict[str, float] | None = None

    def __init__(self, config_manager: ConfigManager, data_dir: Path) -> None:
        """初始化报告生成器。

        Args:
            config_manager: 配置管理器实例。
            data_dir: 插件数据主路径。
        """
        self.config_manager = config_manager
        self.data_dir = data_dir
        self.activity_visualizer = ActivityVisualizer()
        self.html_templates = HTMLTemplates(config_manager)
        max_concurrent = int(self.config_manager.get_t2i_max_concurrent() or 2)
        self._render_semaphore = asyncio.Semaphore(max_concurrent)
        self._markdown_generator_inst = MarkdownReportGenerator(
            config_manager,
            self.html_templates,
            self._render_semaphore,
            self.data_dir,
        )

        self._avatar_service_inst = AvatarService(self.data_dir)
        self._avatar_cache = self._avatar_service_inst.avatar_cache
        self._profile_asset_manifest = load_profile_asset_manifest()
        self._preparer = RenderDataPreparer(
            config_manager=self.config_manager,
            avatar_service=self._avatar_service_inst,
            html_templates=self.html_templates,
            activity_visualizer=self.activity_visualizer,
            profile_asset_manifest=self._profile_asset_manifest,
        )

    def _load_profile_asset_manifest(self) -> dict[str, dict[str, dict[str, object]]]:
        """加载人格资源清单（委托 profile_mappings 模块）。"""
        return load_profile_asset_manifest()

    def _get_profile_mapping_overrides(self) -> dict[str, dict[str, dict[str, object]]]:
        """解析用户配置的人格映射覆盖项。"""
        raw = self.config_manager.get_profile_mapping_config()
        if not raw:
            return {}

        try:
            data = json.loads(raw)
            if is_string_mapping(data):
                return {
                    mode: {
                        code: item
                        for code, item in entries.items()
                        if is_string_mapping(item)
                    }
                    for mode, entries in data.items()
                    if is_string_mapping(entries)
                }
        except Exception as e:
            logger.warning(f"人格映射配置 JSON 解析失败，已回退到默认映射: {e}")
        return {}

    def _build_profile_image_from_manifest_pattern(
        self, profile_mode: str, asset_code: str
    ) -> str:
        """从资源路径模式推导图片地址。"""
        return build_profile_image_from_manifest_pattern(
            self._profile_asset_manifest, profile_mode, asset_code
        )

    def _get_manifest_profile_item_by_mbti(
        self, profile_mode: str, mbti: str
    ) -> dict[str, object] | None:
        """按 MBTI 从 manifest 中寻找可用资源。"""
        return get_manifest_profile_item_by_mbti(
            self._profile_asset_manifest, profile_mode, mbti
        )

    def _resolve_profile_info(
        self,
        mbti: str,
        profile_mode: str,
        overrides: dict[str, dict[str, dict[str, object]]],
    ) -> dict[str, str | float]:
        """根据展示模式解析人格信息字典。"""
        return resolve_profile_info(
            mbti,
            profile_mode,
            overrides,
            self._profile_asset_manifest,
            self.config_manager,
        )

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        """路径组件安全消毒。"""
        return sanitize_path_component(name)

    def _build_safe_report_path(
        self,
        output_dir: Path,
        filename_format: str,
        group_id: str,
        date: str,
        trace_id: str | None = None,
    ) -> Path:
        """构建安全的报告输出文件路径。"""
        return build_safe_report_path(
            output_dir, filename_format, group_id, date, trace_id
        )

    @staticmethod
    def _inject_trace_id_meta(html_content: str, trace_id: str) -> str:
        """在 HTML 产物头部注入不可见的追踪号元数据。

        文件名格式可由用户自定义（例如 ${group_id}/${date}.html），此时文件名不再携带
        追踪号，产物一旦脱离数据库或日志，就难以反查属于哪次分析任务。因此把追踪号写入
        HTML 头部 meta，配合 grep 即可在原文件上定位任务。

        Args:
            html_content: 渲染完成的 HTML 文本。
            trace_id: 本次分析的链路追踪 ID。

        Returns:
            注入元数据后的 HTML 文本；追踪号为空、模板无 head 时原样返回；已存在同名 meta 时
            按追踪号自愈（值相同则原样返回，值不同则改写为当前追踪号）。
        """
        if not trace_id:
            return html_content
        escaped_trace_id = html_module.escape(trace_id, quote=True)
        meta = f'<meta name="{_TRACE_META_ATTR}" content="{escaped_trace_id}">'

        existing = _TRACE_META_PATTERN.search(html_content)
        if existing:
            if f'content="{escaped_trace_id}"' in existing.group(0):
                return html_content
            return (
                html_content[: existing.start()] + meta + html_content[existing.end() :]
            )

        head_match = _HTML_HEAD_PATTERN.search(html_content)
        if not head_match:
            logger.debug("模板未包含 head 节点，跳过追踪号元数据注入")
            return html_content
        return (
            html_content[: head_match.end()]
            + f"\n    {meta}"
            + html_content[head_match.end() :]
        )

    @staticmethod
    def resolve_t2i_viewport_options(
        html_content: str, image_options: ScreenshotOptions
    ) -> tuple[ScreenshotOptions, str]:
        """解析 T2I 渲染视口选项。"""
        return resolve_t2i_viewport_options(html_content, image_options)

    def render_prepared_html(
        self,
        template_file: str,
        template_theme: str | None,
        payload: RenderTemplateContext,
    ) -> str:
        """渲染主模板并复用头像，供图片首轮、资源回退和 HTML 导出共用。

        Args:
            template_file: 图片或网页主模板文件名。
            template_theme: 本次报告的主题。
            payload: 当前资源环境下已准备的数据。

        Returns:
            完成头像去重处理的 HTML。

        Raises:
            无。模板渲染失败时由模板引擎记录原因并返回空字符串。
        """
        if self.html_templates is None:
            return ""
        content = self.html_templates.render_template(
            template_file, template_theme=template_theme, **payload
        )
        return self._reuse_avatars_in_final_html(
            content,
            payload.get("avatar_reuse_registry"),
            payload.get("avatar_reuse_aliases"),
        )

    @staticmethod
    def _diagnose_non_image_payload(data: bytes) -> str:
        """诊断非图片响应并提取排查信息。"""
        return diagnose_non_image_payload(data)

    def inspect_render_result(
        self, image_data: object, response_info: RenderAttemptRecord
    ) -> tuple[bool, str, int, str | None]:
        """校验外部渲染响应并读取文件诊断信息，供工作线程执行。

        Args:
            image_data: 宿主或自定义 T2I 服务返回的路径、字节或异常类型。
            response_info: 当前尝试的诊断字段，原地补充返回类型和大小。

        Returns:
            是否可用、失败原因、字节数和可选的图片尺寸。
        """
        response_info["return_type"] = type(image_data).__name__
        if image_data is None:
            return (
                False,
                "AstrBot 渲染接口返回了 None，未提供图片或具体原因。请同时查看 AstrBot 和 T2I 服务日志。",
                0,
                None,
            )
        if not isinstance(image_data, (str, bytes)):
            return (
                False,
                f"AstrBot 渲染接口返回了不支持的数据类型：{type(image_data).__name__}。",
                0,
                None,
            )
        if not image_data:
            error = (
                "AstrBot 渲染接口返回了空字节数据（0 字节）。"
                if isinstance(image_data, bytes)
                else "AstrBot 渲染接口返回了空文件路径。"
            )
            if isinstance(image_data, bytes):
                response_info["returned_bytes"] = 0
            return False, error, 0, None

        if isinstance(image_data, bytes):
            raw_sample = image_data[:4096]
            image_size = len(image_data)
        else:
            try:
                with Path(image_data).open("rb") as image_file:
                    response_info["file_exists"] = True
                    raw_sample = image_file.read(4096)
                    image_size = image_file.seek(0, 2)
            except FileNotFoundError:
                response_info["file_exists"] = False
                return False, "渲染接口返回了文件路径，但图片文件不存在。", 0, None
            except OSError as e:
                return (
                    False,
                    f"无法读取渲染接口返回的图片文件：{type(e).__name__}：{summarize_render_error(str(e))}",
                    0,
                    None,
                )
        response_info["returned_bytes"] = image_size
        if not raw_sample.startswith((b"\xff\xd8", b"\x89PNG")):
            error = self._diagnose_non_image_payload(raw_sample)
            if not raw_sample and isinstance(image_data, str):
                error = "渲染接口返回的图片文件为空（0 字节）。"
            return False, error, image_size, None

        dimensions = None
        try:
            source = (
                BytesIO(image_data) if isinstance(image_data, bytes) else image_data
            )
            with Image.open(source) as img:
                dimensions = f"{img.width}x{img.height}"
        except Exception:
            # 尺寸观测失败不影响宿主已返回的图片发送。
            pass
        return True, "", image_size, dimensions

    async def generate_image_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = None,
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        template_theme: str | None = None,
    ) -> tuple[str | None, str | None]:
        """生成图片格式的分析报告。

        Args:
            analysis_result: 聚合分析结果字典。
            group_id: 群组 ID。
            html_render_func: 异步 HTML 渲染函数。
            avatar_url_getter: 用户头像获取回调。
            nickname_getter: 成员昵称获取回调。
            avatar_cache_namespace: 平台命名空间。
            hide_user_names: 是否脱敏隐藏用户名。
            allow_alphanumeric_user_ids: 是否允许字母数字用户 ID。
            template_theme: 指定渲染模板主题名称。

        Returns:
            元组 (image_url_or_path, html_content)。
        """
        trace = TraceContext.current()
        theme = template_theme
        if not theme and trace:
            theme = str(trace.metadata.get("override_template_name") or "").strip()
        theme = theme or self.config_manager.get_report_template() or "scrapbook"
        identity = TypstIdentityOptions(
            avatar_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
            namespace=avatar_cache_namespace,
            hide_names=hide_user_names,
            extended_ids=allow_alphanumeric_user_ids,
        )
        request = ImageReportRequest(analysis_result, group_id, theme, identity)
        try:
            strategies = self.config_manager.get_t2i_rendering_strategies()
            session = ImageReportSession(
                source=self,
                request=request,
                semaphore=self._render_semaphore,
                environment=self.config_manager.get_t2i_font_source(),
                timeout=_RENDER_TOTAL_TIMEOUT_SECONDS,
                backends={
                    "typst": NativeImageBackend(
                        lambda: TypstReportRenderer(
                            self.config_manager,
                            self.data_dir,
                            self._avatar_service,
                            self._profile_asset_manifest,
                        ),
                        analysis_result,
                        theme,
                        identity,
                    ),
                    "custom": CustomImageBackend(render_custom_t2i),
                    "astrbot": HostImageBackend(html_render_func),
                },
            )
            return await session.run(strategies)
        except Exception as error:
            logger.error(f"生成图片报告过程发生严重错误: {error}", exc_info=True)
            return None, None

    async def generate_html_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        template_theme: str | None = None,
        custom_filename: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[str | None, str | None]:
        """生成 HTML 格式的分析报告并保存到磁盘。

        Args:
            analysis_result: 分析结果字典。
            group_id: 群组 ID。
            avatar_url_getter: 头像获取回调。
            nickname_getter: 昵称获取回调。
            avatar_cache_namespace: 平台命名空间。
            hide_user_names: 是否隐藏用户名。
            allow_alphanumeric_user_ids: 是否允许字母数字用户 ID。
            template_theme: 模板主题名称。
            custom_filename: 自定义文件名。
            trace_id: 追踪 Trace ID，用于渲染文件名格式中的 ${trace_id} 变量（未提供时取当前 TraceContext）。

        Returns:
            元组 (html_file_path, json_file_path)。
        """
        if not self.html_templates:
            return None, None
        if not template_theme:
            trace_ctx = TraceContext.current()
            if trace_ctx and trace_ctx.metadata.get("override_template_name"):
                template_theme = str(
                    trace_ctx.metadata.get("override_template_name") or ""
                ).strip()
            else:
                template_theme = (
                    self.config_manager.get_report_template() or "scrapbook"
                )

        try:
            output_dir = Path(self.config_manager.get_html_output_dir())
            await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

            effective_trace_id = trace_id or TraceContext.get() or ""
            if custom_filename:
                html_path = output_dir / custom_filename
                if not html_path.suffix:
                    html_path = html_path.with_suffix(".html")
            else:
                current_date = datetime.now().strftime("%Y%m%d")
                html_path = self._build_safe_report_path(
                    output_dir,
                    self.config_manager.get_html_filename_format(),
                    group_id=group_id,
                    date=current_date,
                    trace_id=effective_trace_id,
                )
                if not html_path.suffix:
                    html_path = html_path.with_suffix(".html")

            html_path.parent.mkdir(parents=True, exist_ok=True)

            render_data = await self.prepare_render_data(
                analysis_result,
                template_theme=template_theme,
                chart_template="activity_chart.html",
                avatar_url_getter=avatar_url_getter,
                nickname_getter=nickname_getter,
                avatar_cache_namespace=avatar_cache_namespace,
                hide_user_names=hide_user_names,
                allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
            )
            logger.debug(f"HTML 渲染数据准备完成，包含 {len(render_data)} 个字段")

            try:
                html_content = self.render_prepared_html(
                    "html_template.html", template_theme, render_data
                )
                logger.debug("使用 html_template.html 渲染成功")
            except Exception as e:
                logger.warning(
                    f"html_template.html 不存在或渲染失败，回退到 image_template.html: {e}"
                )
                html_content = self.render_prepared_html(
                    "image_template.html", template_theme, render_data
                )
                logger.debug("使用 image_template.html 渲染成功")

            if not html_content:
                logger.error("HTML报告渲染失败：返回空内容")
                return None, None

            logger.debug(f"HTML 内容生成完成，长度: {len(html_content)} 字符")

            html_content = self._inject_trace_id_meta(html_content, effective_trace_id)

            await asyncio.to_thread(
                html_path.write_text, html_content, encoding="utf-8"
            )
            logger.info(f"HTML 报告已保存: {html_path}")

            trace_ctx = TraceContext.current()
            if trace_ctx:
                for s in reversed(trace_ctx.spans):
                    if s.get("stage_name") == AnalysisStage.RENDER_REPORT.value:
                        topics_rendered = analysis_result.get("topics") or []
                        titles_rendered = analysis_result.get("user_titles") or []
                        stats_obj = analysis_result.get("statistics")
                        golden_quotes = stats_obj.golden_quotes if stats_obj else []
                        s.setdefault("payload", {}).update(
                            {
                                "format": "html",
                                "template": template_theme or "scrapbook",
                                "html_chars": len(html_content) if html_content else 0,
                                "html_file": html_path.name,
                                "topics_rendered": len(topics_rendered),
                                "titles_rendered": len(titles_rendered),
                                "quotes_rendered": len(golden_quotes),
                                "avatars_processed": (
                                    len(render_data.get("avatar_reuse_registry", {}))
                                ),
                                "hide_user_names": bool(hide_user_names),
                            }
                        )
                        break

                rfiles = trace_ctx.metadata.setdefault("report_files", [])
                if is_object_list(rfiles) and not any(
                    is_string_mapping(rf) and rf.get("filename") == html_path.name
                    for rf in rfiles
                ):
                    rfiles.append(
                        {
                            "filename": html_path.name,
                            "path": str(html_path.resolve()),
                            "format": "html",
                            "size_bytes": html_path.stat().st_size
                            if html_path.exists()
                            else 0,
                            "created_at": time.time(),
                        }
                    )
                try:
                    await trace_ctx.persist_snapshot_async()
                except Exception as e:
                    logger.warning(f"保存报告追踪快照失败: {e}")

            return str(html_path.absolute()), None

        except Exception as e:
            logger.error(f"生成 HTML 报告失败: {e}", exc_info=True)
            return None, None

    def build_html_caption(self, html_path: str) -> str:
        """根据配置的 WebUI 地址生成附带外链的 Caption 说明。

        Args:
            html_path: 本地 HTML 报告文件路径。

        Returns:
            生成的富文本说明字符串。
        """
        caption = "📊 每日群聊分析报告已生成"
        base_url = self.config_manager.get_html_base_url()
        if not base_url or not html_path:
            return caption

        output_dir = Path(self.config_manager.get_html_output_dir()).resolve(
            strict=False
        )
        try:
            relative_path = (
                Path(html_path).resolve(strict=False).relative_to(output_dir)
            )
            relative_url = str(relative_path).replace(os.sep, "/")
        except Exception:
            relative_url = Path(html_path).name

        encoded_relative_url = quote(relative_url, safe="/")
        return caption + f"\n{base_url.rstrip('/')}/{encoded_relative_url}"

    def generate_text_report(self, analysis_result: AnalysisResultPayload) -> str:
        """生成纯文本格式的分析报告。

        Args:
            analysis_result: 分析结果字典。

        Returns:
            排版后的纯文本报告内容。
        """
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        report = f"""
🎯 群聊日常分析报告
📅 {datetime.now().strftime("%Y年%m月%d日")}

📊 基础统计
• 消息总数: {stats.message_count}
• 参与人数: {stats.participant_count}
• 总字符数: {stats.total_characters}
• 表情数量: {stats.emoji_count}
• 最活跃时段: {stats.most_active_period}

💬 热门话题
"""
        max_topics = self.config_manager.get_max_topics()
        for i, topic in enumerate(topics[:max_topics], 1):
            contributors_str = "、".join(topic.contributors)
            report += f"{i}. {topic.topic}\n"
            report += f"   参与者: {contributors_str}\n"
            report += f"   {topic.detail}\n\n"

        report += "🏆 群友称号\n"
        max_user_titles = self.config_manager.get_max_user_titles()
        for title in user_titles[:max_user_titles]:
            report += f"• {title.name} - {title.title} ({title.mbti})\n"
            report += f"  {title.reason}\n\n"

        report += "💬 群圣经\n"
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        for i, golden_quote in enumerate(stats.golden_quotes[:max_golden_quotes], 1):
            report += f'{i}. "{golden_quote.content}" —— {golden_quote.sender}\n'
            report += f"   {golden_quote.reason}\n\n"

        return report

    async def generate_markdown_report(
        self,
        analysis_result: AnalysisResultPayload,
        html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = None,
        mention_style: str = "name",
        summary_image_uploader: Callable[[bytes], Awaitable[str | None]] | None = None,
    ) -> tuple[str, str]:
        """生成 Markdown 格式分析报告。

        Args:
            analysis_result: 分析结果字典。
            html_render_func: 可选的图片渲染函数。
            mention_style: 提及展示风格（'name' 为昵称，'qq' 为 QQ 官方真提及）。
            summary_image_uploader: QQ 原生概览图的素材上传回调，供 Markdown 同条引用。

        Returns:
            元组 (markdown_text, fallback_text)。
        """
        return await self._markdown_generator.generate_markdown_report(
            analysis_result,
            html_render_func,
            mention_style=mention_style,
            summary_image_uploader=summary_image_uploader,
        )

    @property
    def _markdown_generator(self) -> MarkdownReportGenerator:
        gen = getattr(self, "_markdown_generator_inst", None)
        if isinstance(gen, MarkdownReportGenerator):
            return gen
        templates = getattr(self, "html_templates", None) or HTMLTemplates(
            self.config_manager
        )
        sem = getattr(self, "_render_semaphore", None) or asyncio.Semaphore(2)
        inst = MarkdownReportGenerator(
            self.config_manager,
            templates,
            sem,
            getattr(self, "data_dir", None),
        )
        self._markdown_generator_inst = inst
        return inst

    @_markdown_generator.setter
    def _markdown_generator(self, val: MarkdownReportGenerator) -> None:
        self._markdown_generator_inst = val

    @property
    def _avatar_service(self) -> AvatarService:
        inst = getattr(self, "_avatar_service_inst", None)
        if isinstance(inst, AvatarService):
            return inst
        data_dir = getattr(self, "data_dir", None) or Path("./data")
        new_inst = AvatarService(data_dir)
        avatar_cache = getattr(self, "_avatar_cache", None)
        if avatar_cache is not None:
            new_inst.avatar_cache = avatar_cache
        avatar_failure_cache = getattr(self, "_avatar_failure_cache", None)
        if avatar_failure_cache is not None:
            new_inst.avatar_failure_cache = avatar_failure_cache
        avatar_session = getattr(self, "_avatar_session", None)
        if avatar_session is not None:
            new_inst.avatar_session = avatar_session
        avatar_session_lock = getattr(self, "_avatar_session_lock", None)
        if avatar_session_lock is not None:
            new_inst.avatar_session_lock = avatar_session_lock
        avatar_semaphore = getattr(self, "_avatar_session_concurrent_semaphore", None)
        if avatar_semaphore is not None:
            new_inst.avatar_session_concurrent_semaphore = avatar_semaphore
        self._avatar_service_inst = new_inst
        return new_inst

    @_avatar_service.setter
    def _avatar_service(self, val: AvatarService) -> None:
        self._avatar_service_inst = val

    @property
    def _preparer_service(self) -> RenderDataPreparer:
        """获取或懒加载 RenderDataPreparer 实例。"""
        preparer = getattr(self, "_preparer", None)
        if isinstance(preparer, RenderDataPreparer):
            return preparer
        profile_manifest = (
            getattr(self, "_profile_asset_manifest", None)
            or load_profile_asset_manifest()
        )
        html_templates = getattr(self, "html_templates", None) or HTMLTemplates(
            self.config_manager
        )
        activity_visualizer = (
            getattr(self, "activity_visualizer", None) or ActivityVisualizer()
        )
        self._preparer = RenderDataPreparer(
            config_manager=self.config_manager,
            avatar_service=self._avatar_service,
            html_templates=html_templates,
            activity_visualizer=activity_visualizer,
            profile_asset_manifest=profile_manifest,
        )
        return self._preparer

    @_preparer_service.setter
    def _preparer_service(self, val: RenderDataPreparer) -> None:
        self._preparer = val

    def _sanitize_analysis_result_for_export(
        self, analysis_result: AnalysisResultPayload
    ) -> dict[str, object]:
        """导出 HTML Sidecar JSON 前脱敏敏感身份信息。"""
        return self._preparer_service.sanitize_analysis_result_for_export(
            analysis_result
        )

    @classmethod
    def _to_plain_export_data(cls, value: object) -> object:
        """递归转换领域模型为普通字典与列表。"""
        return RenderDataPreparer.to_plain_export_data(value)

    def _sanitize_export_identity_text(
        self, value: object, analysis_result: AnalysisResultPayload
    ) -> object:
        """从导出的文本字段中去除用户名称与 ID。"""
        return self._preparer_service.sanitize_export_identity_text(
            value, analysis_result
        )

    async def prepare_render_data(
        self,
        analysis_result: AnalysisResultPayload,
        template_theme: str | None = None,
        chart_template: str = "activity_chart.html",
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        environment: str | None = None,
        resources: RenderingResourceConfig | None = None,
        font_mode: FontMode = "network",
    ) -> RenderTemplateContext:
        """组装模板引擎所需的强类型上下文。

        Args:
            analysis_result: 本次分析结果。
            template_theme: 报告主题，省略时使用配置中的主题。
            chart_template: 活跃度图表模板文件名。
            avatar_url_getter: 头像地址异步获取回调。
            nickname_getter: 昵称异步获取回调。
            avatar_cache_namespace: 隔离平台头像缓存的命名空间。
            hide_user_names: 是否隐藏用户名。
            allow_alphanumeric_user_ids: 是否允许字母数字用户 ID。
            environment: 本轮固定的资源环境，省略时采用第一优先级方案。
            resources: 本轮固定的 CDN 和字体地址。
            font_mode: 本轮图片T2I的字体加载方式。

        Returns:
            主模板使用的资源、统计数据与组件 HTML。

        Raises:
            KeyError: 分析结果缺少统计信息或其他必需字段。
        """
        return await self._preparer_service.prepare_render_data(
            analysis_result=analysis_result,
            template_theme=template_theme,
            chart_template=chart_template,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
            avatar_cache_namespace=avatar_cache_namespace,
            hide_user_names=hide_user_names,
            allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
            environment=environment,
            resources=resources,
            font_mode=font_mode,
        )

    async def _render_avatar_only_ids(
        self,
        user_ids: list[str],
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        avatar_reuse_registry: dict[str, str] | None = None,
        avatar_reuse_aliases: dict[str, str] | None = None,
    ) -> Markup:
        """渲染纯头像图标列表。"""
        return await self._preparer_service.render_avatar_only_ids(
            user_ids=user_ids,
            avatar_url_getter=avatar_url_getter,
            avatar_cache_namespace=avatar_cache_namespace,
            avatar_reuse_registry=avatar_reuse_registry,
            avatar_reuse_aliases=avatar_reuse_aliases,
        )

    async def _render_mentions(
        self,
        text: str,
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        user_analysis: dict[str, object] | None = None,
        avatar_cache_namespace: str | None = None,
        avatar_reuse_registry: dict[str, str] | None = None,
        avatar_reuse_aliases: dict[str, str] | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
    ) -> Markup:
        """将文本中的用户引用替换为头像气泡胶囊。"""
        return await self._preparer_service.render_mentions(
            text=text,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
            user_analysis=user_analysis,
            avatar_cache_namespace=avatar_cache_namespace,
            avatar_reuse_registry=avatar_reuse_registry,
            avatar_reuse_aliases=avatar_reuse_aliases,
            hide_user_names=hide_user_names,
            allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
        )

    @staticmethod
    def _sanitize_identity_text(
        text: str, analysis_result: AnalysisResultPayload, hide_user_names: bool
    ) -> str:
        """从字符串中消除用户标识。"""
        return RenderDataPreparer.sanitize_identity_text(
            text, analysis_result, hide_user_names
        )

    @staticmethod
    def _escape_text_segment(text: str) -> Markup:
        """转义文本并转换换行符为 `<br>`。"""
        return RenderDataPreparer.escape_text_segment(text)

    @staticmethod
    def _is_placeholder_display_name(name: str | None, user_id: str) -> bool:
        """判断展示名称是否为占位值。"""
        return RenderDataPreparer.is_placeholder_display_name(name, user_id)

    @staticmethod
    def _safe_url_for_log(url: str | None) -> str:
        """对日志中的 URL 进行脱敏。"""
        return AvatarService.safe_url_for_log(url)

    def _get_avatar_cache_key(
        self, avatar_id: str, avatar_cache_namespace: str | None = None
    ) -> str:
        """生成平台头像缓存键。"""
        return AvatarService.get_avatar_cache_key(avatar_id, avatar_cache_namespace)

    @staticmethod
    def _resize_avatar_bytes(payload: bytes) -> bytes:
        """缩放头像图片尺寸。"""
        return AvatarService.resize_avatar_bytes(payload)

    def _b64_with_mime(self, raw_bytes: bytes) -> str | None:
        """将二进制字节流转换为带 MIME 前缀的 Data URI。"""
        return AvatarService.b64_with_mime(raw_bytes)

    async def _get_user_avatar_bytes(
        self,
        user_id: str,
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> bytes | None:
        """获取头像原始字节流。"""
        if self._avatar_session is not None:
            self._avatar_service.avatar_session = self._avatar_session
        if self._avatar_session_lock is not None:
            self._avatar_service.avatar_session_lock = self._avatar_session_lock
        if self._avatar_session_concurrent_semaphore is not None:
            self._avatar_service.avatar_session_concurrent_semaphore = (
                self._avatar_session_concurrent_semaphore
            )
        return await self._avatar_service.get_user_avatar_bytes(
            user_id, avatar_url_getter
        )

    async def _get_user_avatar(
        self,
        avatar_id: str,
        avatar_url_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
    ) -> str:
        """获取用户头像 Base64（委托 AvatarService）。"""
        if self._avatar_cache is not None:
            self._avatar_service.avatar_cache = self._avatar_cache
        if self._avatar_failure_cache is not None:
            self._avatar_service.avatar_failure_cache = self._avatar_failure_cache

        if "_get_user_avatar_bytes" in self.__dict__:
            orig = self._avatar_service.get_user_avatar_bytes
            self._avatar_service.get_user_avatar_bytes = self._get_user_avatar_bytes
            try:
                return await self._avatar_service.get_user_avatar(
                    avatar_id, avatar_url_getter, avatar_cache_namespace
                )
            finally:
                self._avatar_service.get_user_avatar_bytes = orig

        return await self._avatar_service.get_user_avatar(
            avatar_id, avatar_url_getter, avatar_cache_namespace
        )

    def _get_default_avatar_base64(self) -> str:
        """获取默认头像 Base64。"""
        return AvatarService.get_default_avatar_base64()

    @staticmethod
    def _register_reusable_avatar(
        avatar_url: str | None,
        avatar_reuse_registry: dict[str, str] | None,
        avatar_reuse_aliases: dict[str, str] | None = None,
        avatar_key: str | None = None,
    ) -> str | None:
        """注册可复用头像标识。"""
        return AvatarService.register_reusable_avatar(
            avatar_url, avatar_reuse_registry, avatar_reuse_aliases, avatar_key
        )

    @staticmethod
    def _reuse_avatars_in_final_html(
        html_content: str,
        avatar_reuse_registry: dict[str, str] | None,
        avatar_reuse_aliases: dict[str, str] | None = None,
    ) -> str:
        """最终 HTML 头像复用与样式注入。"""
        return AvatarService.reuse_avatars_in_final_html(
            html_content, avatar_reuse_registry, avatar_reuse_aliases
        )

    async def close(self) -> None:
        """关闭并释放资源。"""
        if hasattr(self, "_avatar_service"):
            await self._avatar_service.close()
