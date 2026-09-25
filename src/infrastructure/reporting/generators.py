"""报告生成器模块

负责生成图片、HTML、纯文本等多种格式的群聊日常分析报告，协调模板引擎与渲染流。
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from PIL import Image

from ...domain.repositories.report_repository import IReportGenerator
from ...shared.constants import (
    AnalysisStage,
)
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..visualization.activity_charts import ActivityVisualizer
from .avatar_service import (
    AvatarService,
)
from .profile_mappings import (
    build_profile_image_from_manifest_pattern,
    get_manifest_profile_item_by_mbti,
    load_profile_asset_manifest,
    resolve_profile_info,
)
from .qq_official_markdown import QQOfficialMarkdownReportGenerator
from .render_data_preparer import RenderDataPreparer
from .render_diagnostics import (
    build_safe_report_path,
    diagnose_non_image_payload,
    resolve_t2i_viewport_options,
    sanitize_path_component,
)
from .templates import HTMLTemplates

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import aiohttp
    from diskcache import Cache
    from markupsafe import Markup

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager


class ReportGenerator(IReportGenerator):
    """报告生成器 - 负责全格式群聊分析报告的数据装配与渲染。"""

    config_manager: ConfigManager
    data_dir: Path
    activity_visualizer: ActivityVisualizer
    html_templates: HTMLTemplates | None
    _render_semaphore: asyncio.Semaphore
    _avatar_cache: Cache | None = None
    _profile_asset_manifest: dict[str, dict]
    _preparer: RenderDataPreparer
    _qq_official_markdown_generator_inst: QQOfficialMarkdownReportGenerator | None = (
        None
    )
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
        if hasattr(self.config_manager, "get_t2i_max_concurrent"):
            max_concurrent = int(self.config_manager.get_t2i_max_concurrent())
        else:
            max_concurrent = 2
        self._render_semaphore = asyncio.Semaphore(max_concurrent)
        self._qq_official_markdown_generator_inst = QQOfficialMarkdownReportGenerator(
            config_manager,
            self.html_templates,
            self._render_semaphore,
        )

        self._avatar_service_inst = AvatarService(self.data_dir)
        self._avatar_cache = self._avatar_service_inst._avatar_cache
        self._profile_asset_manifest = load_profile_asset_manifest()
        self._preparer = RenderDataPreparer(
            config_manager=self.config_manager,
            avatar_service=self._avatar_service_inst,
            html_templates=self.html_templates,
            activity_visualizer=self.activity_visualizer,
            profile_asset_manifest=self._profile_asset_manifest,
        )

    def _load_profile_asset_manifest(self) -> dict[str, dict]:
        """加载人格资源清单（委托 profile_mappings 模块）。"""
        return load_profile_asset_manifest()

    def _get_profile_mapping_overrides(self) -> dict[str, dict]:
        """解析用户配置的人格映射覆盖项。"""
        raw = self.config_manager.get_profile_mapping_config()
        if not raw:
            return {}

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
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
    ) -> dict | None:
        """按 MBTI 从 manifest 中寻找可用资源。"""
        return get_manifest_profile_item_by_mbti(
            self._profile_asset_manifest, profile_mode, mbti
        )

    def _resolve_profile_info(
        self,
        mbti: str,
        profile_mode: str,
        overrides: dict[str, dict],
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
    ) -> Path:
        """构建安全的报告输出文件路径。"""
        return build_safe_report_path(output_dir, filename_format, group_id, date)

    @staticmethod
    def _resolve_t2i_viewport_options(
        html_content: str, image_options: dict
    ) -> tuple[dict, str]:
        """解析 T2I 渲染视口选项。"""
        return resolve_t2i_viewport_options(html_content, image_options)

    @staticmethod
    def _diagnose_non_image_payload(data: bytes) -> str:
        """诊断非图片响应并提取排查信息。"""
        return diagnose_non_image_payload(data)

    async def generate_image_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = None,
        avatar_url_getter: Callable[[str, int | None], Awaitable[str | None]]
        | None = None,
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
        html_content = None
        if not self.html_templates:
            return None, None
        if not template_theme:
            trace_ctx = TraceContext.current()
            if trace_ctx and trace_ctx.metadata.get("override_template_name"):
                template_theme = str(
                    trace_ctx.metadata.get("override_template_name") or ""
                ).strip()
            elif hasattr(self.config_manager, "get_report_template"):
                template_theme = self.config_manager.get_report_template()
            else:
                template_theme = "scrapbook"

        try:
            render_payload = await self._prepare_render_data(
                analysis_result,
                template_theme=template_theme,
                chart_template="activity_chart.html",
                avatar_url_getter=avatar_url_getter,
                nickname_getter=nickname_getter,
                avatar_cache_namespace=avatar_cache_namespace,
                hide_user_names=hide_user_names,
                allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
            )

            tpl_render_start_ts = time.perf_counter()
            html_content = self.html_templates.render_template(
                "image_template.html", template_theme=template_theme, **render_payload
            )
            avatar_registry = render_payload.get("avatar_reuse_registry")
            avatar_aliases = render_payload.get("avatar_reuse_aliases")
            html_content = self._reuse_avatars_in_final_html(
                html_content,
                avatar_registry if isinstance(avatar_registry, dict) else None,
                avatar_aliases if isinstance(avatar_aliases, dict) else None,
            )
            template_render_ms = round(
                (time.perf_counter() - tpl_render_start_ts) * 1000, 2
            )
            html_size_kb = (
                round(len(html_content.encode("utf-8")) / 1024, 2)
                if html_content
                else 0.0
            )

            if not html_content:
                logger.error("图片报告HTML渲染失败：返回空内容")
                return None, None

            logger.debug(
                f"图片报告HTML渲染完成，耗时 {template_render_ms}ms, "
                f"大小: {html_size_kb} KB ({len(html_content)} 字符)"
            )

            if not callable(html_render_func):
                logger.error("图片报告渲染失败：未提供可调用的 html_render_func")
                return None, html_content

            render_strategies = self.config_manager.get_t2i_rendering_strategies()

            async with self._render_semaphore:
                logger.debug(f"[T2I] 已进入渲染队列 (群: {group_id})")
                last_exception = None

                for attempt, image_options in enumerate(render_strategies, 1):
                    viewport_description = "default"
                    html_error = None
                    try:
                        image_options, viewport_description = (
                            self._resolve_t2i_viewport_options(
                                html_content, image_options
                            )
                        )

                        if image_options.get("type") == "png":
                            image_options.pop("quality", None)

                        logger.debug(
                            "正在尝试第 "
                            f"{attempt} 轮渲染策略: type={image_options['type']}, "
                            f"full_page={image_options['full_page']}, "
                            f"viewport={viewport_description}, "
                            f"scale={image_options.get('device_scale_factor_level')}, "
                            f"timeout={image_options.get('timeout')}"
                        )

                        t2i_start_ts = time.perf_counter()
                        image_data = await html_render_func(
                            html_content,
                            {},
                            False,
                            image_options,
                        )
                        t2i_render_ms = round(
                            (time.perf_counter() - t2i_start_ts) * 1000, 2
                        )

                        if image_data:
                            is_valid = False
                            actual_data_head = None

                            if isinstance(image_data, bytes):
                                actual_data_head = image_data[:10]
                            elif os.path.exists(image_data):
                                try:
                                    with open(image_data, "rb") as f:
                                        actual_data_head = f.read(10)
                                except Exception as e:
                                    logger.warning(f"读取图片临时文件失败: {e}")

                            if actual_data_head:
                                if actual_data_head.startswith(
                                    (b"\xff\xd8", b"\x89PNG")
                                ):
                                    is_valid = True
                                else:
                                    raw_sample = b""
                                    if isinstance(image_data, bytes):
                                        raw_sample = image_data[:4096]
                                    elif os.path.exists(image_data):
                                        try:
                                            with open(image_data, "rb") as f:
                                                raw_sample = f.read(4096)
                                        except Exception:
                                            pass

                                    diag_info = self._diagnose_non_image_payload(
                                        raw_sample or actual_data_head
                                    )
                                    logger.warning(
                                        f"[T2I] 渲染引擎返回了非图片数据: {diag_info}"
                                    )

                            if is_valid:
                                image_size = (
                                    len(image_data)
                                    if isinstance(image_data, bytes)
                                    else (
                                        os.path.getsize(image_data)
                                        if os.path.exists(image_data)
                                        else 0
                                    )
                                )

                                dimensions = None
                                try:
                                    if isinstance(image_data, bytes):
                                        with Image.open(BytesIO(image_data)) as img:
                                            dimensions = f"{img.width}x{img.height}"
                                    elif os.path.exists(image_data):
                                        with Image.open(image_data) as img:
                                            dimensions = f"{img.width}x{img.height}"
                                except Exception:
                                    pass

                                trace_ctx = TraceContext.current()
                                if trace_ctx:
                                    for s in reversed(trace_ctx._spans):
                                        if (
                                            s.get("stage_name")
                                            == AnalysisStage.RENDER_REPORT.value
                                        ):
                                            payload = s.setdefault("payload", {})
                                            topics_raw = (
                                                analysis_result.get("topics") or []
                                            )
                                            titles_raw = (
                                                analysis_result.get("user_titles") or []
                                            )
                                            stats_raw = analysis_result.get(
                                                "statistics"
                                            )
                                            golden_quotes_raw = (
                                                stats_raw.golden_quotes
                                                if stats_raw
                                                else []
                                            )
                                            payload.update(
                                                {
                                                    "format": "image",
                                                    "template": template_theme
                                                    or "scrapbook",
                                                    "viewport": viewport_description,
                                                    "render_attempt": attempt,
                                                    "image_format": str(
                                                        image_options.get(
                                                            "type", "jpeg"
                                                        )
                                                    ),
                                                    "image_bytes": image_size,
                                                    "dimensions": dimensions,
                                                    "template_render_ms": template_render_ms,
                                                    "html_size_kb": html_size_kb,
                                                    "t2i_render_ms": t2i_render_ms,
                                                    "topics_rendered": len(topics_raw),
                                                    "titles_rendered": len(titles_raw),
                                                    "quotes_rendered": len(
                                                        golden_quotes_raw
                                                    ),
                                                    "avatars_processed": (
                                                        len(
                                                            render_payload[
                                                                "avatar_reuse_registry"
                                                            ]  # type: ignore[arg-type]
                                                        )
                                                        if isinstance(
                                                            render_payload.get(
                                                                "avatar_reuse_registry"
                                                            ),
                                                            (dict, list, set),
                                                        )
                                                        else 0
                                                    ),
                                                    "html_chars": len(html_content)
                                                    if html_content
                                                    else 0,
                                                    "hide_user_names": bool(
                                                        hide_user_names
                                                    ),
                                                }
                                            )
                                            attempts = payload.setdefault(
                                                "render_attempts", []
                                            )
                                            if isinstance(attempts, list):
                                                attempts.append(
                                                    {
                                                        "attempt": attempt,
                                                        "type": str(
                                                            image_options.get(
                                                                "type", "jpeg"
                                                            )
                                                        ),
                                                        "viewport": viewport_description,
                                                        "duration_ms": t2i_render_ms,
                                                        "status": "success",
                                                    }
                                                )
                                            break

                                if isinstance(image_data, bytes):
                                    b64 = base64.b64encode(image_data).decode("utf-8")
                                    image_url = f"base64://{b64}"
                                    logger.info(
                                        "图片生成成功 "
                                        f"(轮次 {attempt}, 视口 {viewport_description}): "
                                        f"[Base64 数据 {len(image_data)} 字节]"
                                    )
                                    return image_url, html_content
                                logger.info(
                                    "图片生成成功 "
                                    f"(轮次 {attempt}, 视口 {viewport_description}): "
                                    f"{image_data}"
                                )
                                return image_data, html_content

                        logger.warning(
                            f"渲染轮次 {attempt} ({image_options['type']}) 返回了无效或空数据"
                        )
                        trace_ctx = TraceContext.current()
                        if trace_ctx:
                            for s in reversed(trace_ctx._spans):
                                if (
                                    s.get("stage_name")
                                    == AnalysisStage.RENDER_REPORT.value
                                ):
                                    payload = s.setdefault("payload", {})
                                    attempts = payload.setdefault("render_attempts", [])
                                    if isinstance(attempts, list):
                                        attempts.append(
                                            {
                                                "attempt": attempt,
                                                "type": str(
                                                    image_options.get("type", "jpeg")
                                                ),
                                                "viewport": viewport_description,
                                                "status": "failed",
                                                "error": html_error
                                                or "返回数据非合法图片头",
                                            }
                                        )
                                    break

                    except Exception as e:
                        logger.warning(f"渲染轮次 {attempt} 失败: {e}")
                        last_exception = e
                        trace_ctx = TraceContext.current()
                        if trace_ctx:
                            for s in reversed(trace_ctx._spans):
                                if (
                                    s.get("stage_name")
                                    == AnalysisStage.RENDER_REPORT.value
                                ):
                                    payload = s.setdefault("payload", {})
                                    attempts = payload.setdefault("render_attempts", [])
                                    if isinstance(attempts, list):
                                        attempts.append(
                                            {
                                                "attempt": attempt,
                                                "type": str(
                                                    image_options.get("type", "jpeg")
                                                ),
                                                "viewport": viewport_description,
                                                "status": "failed",
                                                "error": str(e),
                                            }
                                        )
                                    break
                                    break
                        if attempt < len(render_strategies):
                            logger.debug("准备尝试下一轮回退策略")
                        continue

                logger.error(f"所有渲染尝试都失败。最后一个错误: {last_exception}")
                return None, html_content

        except Exception as e:
            logger.error(f"生成图片报告过程发生严重错误: {e}", exc_info=True)
            return None, html_content

    async def generate_html_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        avatar_url_getter: Callable | None = None,
        nickname_getter: Callable | None = None,
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
            trace_id: 追踪 Trace ID。

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
            elif hasattr(self.config_manager, "get_report_template"):
                template_theme = self.config_manager.get_report_template()
            else:
                template_theme = "scrapbook"

        try:
            output_dir = Path(self.config_manager.get_html_output_dir())
            await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

            if custom_filename:
                html_path = output_dir / custom_filename
                if not html_path.suffix:
                    html_path = html_path.with_suffix(".html")
            elif trace_id:
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                theme_suffix = f"_{template_theme}" if template_theme else ""
                html_path = (
                    output_dir
                    / f"report_{group_id}_{ts_str}_{trace_id}{theme_suffix}.html"
                )
            else:
                current_date = datetime.now().strftime("%Y%m%d")
                base_html_path = self._build_safe_report_path(
                    output_dir,
                    self.config_manager.get_html_filename_format(),
                    group_id=group_id,
                    date=current_date,
                )
                html_path = base_html_path
                if not html_path.suffix:
                    html_path = html_path.with_suffix(".html")

            json_path = html_path.with_suffix(".json")
            html_path.parent.mkdir(parents=True, exist_ok=True)

            render_data = await self._prepare_render_data(
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

            avatar_registry = render_data.get("avatar_reuse_registry")
            avatar_aliases = render_data.get("avatar_reuse_aliases")
            reg_dict = avatar_registry if isinstance(avatar_registry, dict) else None
            alias_dict = avatar_aliases if isinstance(avatar_aliases, dict) else None
            try:
                html_content = self.html_templates.render_template(
                    "html_template.html", template_theme=template_theme, **render_data
                )
                html_content = self._reuse_avatars_in_final_html(
                    html_content,
                    reg_dict,
                    alias_dict,
                )
                logger.debug("使用 html_template.html 渲染成功")
            except Exception as e:
                logger.warning(
                    f"html_template.html 不存在或渲染失败，回退到 image_template.html: {e}"
                )
                html_content = self.html_templates.render_template(
                    "image_template.html", template_theme=template_theme, **render_data
                )
                html_content = self._reuse_avatars_in_final_html(
                    html_content,
                    reg_dict,
                    alias_dict,
                )
                logger.debug("使用 image_template.html 渲染成功")

            if not html_content:
                logger.error("HTML报告渲染失败：返回空内容")
                return None, None

            logger.debug(f"HTML 内容生成完成，长度: {len(html_content)} 字符")

            await asyncio.to_thread(
                html_path.write_text, html_content, encoding="utf-8"
            )
            logger.info(f"HTML 报告已保存: {html_path}")

            def json_default_encoder(obj: object) -> object:
                to_dict_fn = getattr(obj, "to_dict", None)
                if callable(to_dict_fn):
                    return to_dict_fn()
                if is_dataclass(obj) and not isinstance(obj, type):
                    return asdict(obj)
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, (set, tuple)):
                    return list(obj)
                raise TypeError(
                    f"Object of type {type(obj).__name__} is not JSON serializable"
                )

            json_data = {
                "analysis_result": (
                    self._sanitize_analysis_result_for_export(analysis_result)
                    if hide_user_names or allow_alphanumeric_user_ids
                    else analysis_result
                ),
                "group_id": group_id,
                "generated_at": datetime.now().isoformat(),
            }
            await asyncio.to_thread(
                json_path.write_text,
                json.dumps(
                    json_data,
                    ensure_ascii=False,
                    indent=2,
                    default=json_default_encoder,
                ),
                encoding="utf-8",
            )
            logger.info(f"JSON 数据已保存: {json_path}")

            trace_ctx = TraceContext.current()
            if trace_ctx:
                for s in reversed(trace_ctx._spans):
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
                                    len(
                                        render_data["avatar_reuse_registry"]  # type: ignore[arg-type]
                                    )
                                    if isinstance(
                                        render_data.get("avatar_reuse_registry"),
                                        (dict, list, set),
                                    )
                                    else 0
                                ),
                                "hide_user_names": bool(hide_user_names),
                            }
                        )
                        break

                rfiles = trace_ctx.metadata.setdefault("report_files", [])
                if isinstance(rfiles, list) and not any(
                    isinstance(rf, dict) and rf.get("filename") == html_path.name
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
                from ...shared.trace_context import _global_trace_store

                if _global_trace_store is not None:
                    try:
                        _global_trace_store.save_trace(trace_ctx.to_dict())
                    except Exception:
                        pass

            return str(html_path.absolute()), str(json_path.absolute())

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

    async def generate_qq_official_markdown_report(
        self,
        analysis_result: AnalysisResultPayload,
        html_render_func: Callable | None = None,
    ) -> tuple[str, str]:
        """委托 QQ 官方机器人专属生成器构建 Markdown 报告。

        Args:
            analysis_result: 分析结果字典。
            html_render_func: 可选的图片渲染函数。

        Returns:
            元组 (markdown_text, image_url)。
        """
        return await self._qq_official_markdown_generator.generate(
            analysis_result,
            html_render_func,
        )

    @property
    def _qq_official_markdown_generator(self) -> QQOfficialMarkdownReportGenerator:
        if self._qq_official_markdown_generator_inst is None:
            templates = getattr(self, "html_templates", None) or HTMLTemplates(
                self.config_manager
            )
            sem = getattr(self, "_render_semaphore", None) or asyncio.Semaphore(2)
            self._qq_official_markdown_generator_inst = (
                QQOfficialMarkdownReportGenerator(
                    self.config_manager,
                    templates,
                    sem,
                )
            )
        return self._qq_official_markdown_generator_inst

    @_qq_official_markdown_generator.setter
    def _qq_official_markdown_generator(
        self, val: QQOfficialMarkdownReportGenerator
    ) -> None:
        self._qq_official_markdown_generator_inst = val

    @property
    def _avatar_service(self) -> AvatarService:
        if self._avatar_service_inst is None:
            data_dir = getattr(self, "data_dir", None) or Path("./data")
            inst = AvatarService(data_dir)
            if self._avatar_cache is not None:
                inst._avatar_cache = self._avatar_cache
            if self._avatar_failure_cache is not None:
                inst._avatar_failure_cache = self._avatar_failure_cache
            if self._avatar_session is not None:
                inst._avatar_session = self._avatar_session
            if self._avatar_session_lock is not None:
                inst._avatar_session_lock = self._avatar_session_lock
            if self._avatar_session_concurrent_semaphore is not None:
                inst._avatar_session_concurrent_semaphore = (
                    self._avatar_session_concurrent_semaphore
                )
            self._avatar_service_inst = inst
        return self._avatar_service_inst

    @_avatar_service.setter
    def _avatar_service(self, val: AvatarService) -> None:
        self._avatar_service_inst = val

    @property
    def _preparer_service(self) -> RenderDataPreparer:
        """获取或懒加载 RenderDataPreparer 实例。"""
        if hasattr(self, "_preparer") and self._preparer:
            return self._preparer
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

    async def _prepare_render_data(
        self,
        analysis_result: AnalysisResultPayload,
        template_theme: str | None = None,
        chart_template: str = "activity_chart.html",
        avatar_url_getter: Callable | None = None,
        nickname_getter: Callable | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
    ) -> dict[str, object]:
        """组装模板引擎所需的完整数据字典。"""
        return await self._preparer_service.prepare_render_data(
            analysis_result=analysis_result,
            template_theme=template_theme,
            chart_template=chart_template,
            avatar_url_getter=avatar_url_getter,
            nickname_getter=nickname_getter,
            avatar_cache_namespace=avatar_cache_namespace,
            hide_user_names=hide_user_names,
            allow_alphanumeric_user_ids=allow_alphanumeric_user_ids,
        )

    async def _render_avatar_only_ids(
        self,
        user_ids: list[str],
        avatar_url_getter: Callable | None = None,
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
        avatar_url_getter: Callable | None = None,
        nickname_getter: Callable | None = None,
        user_analysis: dict | None = None,
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

    def _b64_with_mime(self, _bytes: bytes) -> str | None:
        """将二进制字节流转换为带 MIME 前缀的 Data URI。"""
        return AvatarService.b64_with_mime(_bytes)

    async def _get_user_avatar_bytes(
        self, user_id: str, avatar_url_getter: Callable | None = None
    ) -> bytes | None:
        """获取头像原始字节流。"""
        if self._avatar_session is not None:
            self._avatar_service._avatar_session = self._avatar_session
        if self._avatar_session_lock is not None:
            self._avatar_service._avatar_session_lock = self._avatar_session_lock
        if self._avatar_session_concurrent_semaphore is not None:
            self._avatar_service._avatar_session_concurrent_semaphore = (
                self._avatar_session_concurrent_semaphore
            )
        return await self._avatar_service.get_user_avatar_bytes(
            user_id, avatar_url_getter
        )

    async def _get_user_avatar(
        self,
        avatar_id: str,
        avatar_url_getter: Callable | None = None,
        avatar_cache_namespace: str | None = None,
    ) -> str:
        """获取用户头像 Base64（委托 AvatarService）。"""
        if self._avatar_cache is not None:
            self._avatar_service._avatar_cache = self._avatar_cache
        if self._avatar_failure_cache is not None:
            self._avatar_service._avatar_failure_cache = self._avatar_failure_cache

        if "_get_user_avatar_bytes" in self.__dict__:
            orig = getattr(self._avatar_service, "get_user_avatar_bytes", None)
            self._avatar_service.get_user_avatar_bytes = self._get_user_avatar_bytes
            try:
                return await self._avatar_service.get_user_avatar(
                    avatar_id, avatar_url_getter, avatar_cache_namespace
                )
            finally:
                if orig is not None:
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
