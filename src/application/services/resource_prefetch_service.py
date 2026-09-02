"""预取并预热报告模板静态资源与字体的应用层服务。"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from ...infrastructure.reporting.templates import HTMLTemplates
from ...infrastructure.resources.html_resource_localizer import (
    HTMLResourceLocalizer,
)
from ...utils.logger import logger


class ResourcePrefetchService:
    """用于扫描报告模板并预先下载缓存外部静态资源的应用服务，支持全量与细粒度单模板预取。"""

    def __init__(
        self,
        resource_localizer: HTMLResourceLocalizer,
        html_templates: HTMLTemplates,
        plugin_root: Path | str | None = None,
    ):
        """初始化预取服务。

        Args:
            resource_localizer: 资源本地化流水线协调器。
            html_templates: HTML 模板管理器。
            plugin_root: 插件根路径。
        """
        self.localizer = resource_localizer
        self.html_templates = html_templates
        self.plugin_root = (
            Path(plugin_root) if plugin_root else Path(__file__).resolve().parents[3]
        )

    async def prefetch_template(self, template_name: str) -> dict[str, Any]:
        """为指定单个模板进行精准静态资源与外部字体预热与下载。

        Args:
            template_name: 模板标识名（如 'scrapbook', 'ATRI', 'cyberpunk' 等）。

        Returns:
            包含预取耗时、所属模板、分类统计及全景状态的字典。
        """
        t_name = template_name.strip() if template_name else "global"
        logger.info(f"[资源预取] 开始预取模板 [{t_name}] 的静态资源与字体...")
        start_t = time.time()

        # 1. 扫描对应模板目录下的静态 HTML 和 CSS 文件
        base_dir = Path(self.html_templates.base_dir)
        template_files: list[Path] = []

        if base_dir.is_dir():
            # 模板同名子目录或文件
            sub_dir = base_dir / t_name
            if sub_dir.is_dir():
                template_files.extend(sub_dir.rglob("*.html"))
                template_files.extend(sub_dir.rglob("*.css"))
            for p in base_dir.glob(f"*{t_name}*"):
                if p.is_file() and p.suffix in (".html", ".css"):
                    template_files.append(p)

        # 2. 扫描用户自定义模板目录
        get_custom_dir = getattr(
            self.html_templates.config_manager,
            "get_custom_report_template_dir",
            None,
        )
        if callable(get_custom_dir):
            sample_res = get_custom_dir("")
            if sample_res:
                p_custom = Path(str(sample_res))
                custom_root = p_custom if p_custom.is_dir() else p_custom.parent
                if custom_root.is_dir():
                    c_sub = custom_root / t_name
                    if c_sub.is_dir():
                        template_files.extend(c_sub.rglob("*.html"))
                        template_files.extend(c_sub.rglob("*.css"))
                    for p in custom_root.glob(f"*{t_name}*"):
                        if p.is_file() and p.suffix in (".html", ".css"):
                            template_files.append(p)

        # 嗅探文件中的外部资源
        for f in template_files:
            try:
                content = await asyncio.to_thread(f.read_text, encoding="utf-8")
                content = content.replace(
                    "{{ t2i_google_fonts_mirror }}",
                    "https://fonts.googleapis.com",
                )
                content = content.replace(
                    "{{ t2i_gstatic_mirror }}", "https://fonts.gstatic.com"
                )
                content = content.replace(
                    "{{ t2i_atri_font_mirror }}", "https://tc.ciallo.ccwu.cc"
                )
                await self.localizer.localize_html(
                    content, context={"template": t_name, "timeout": 8.0}
                )
            except Exception as e:
                logger.debug(f"[资源预取] 预取模板源文件 {f.name} 异常: {e}")

        # 3. 模拟渲染 image_template 与 html_template 触发动态资源本地化
        for tmpl_file in ["image_template.html", "html_template.html"]:
            try:
                rendered = self.html_templates.render_template(
                    tmpl_file,
                    template_theme=t_name,
                    t2i_google_fonts_mirror="https://fonts.googleapis.com",
                    t2i_gstatic_mirror="https://fonts.gstatic.com",
                    t2i_atri_font_mirror="https://tc.ciallo.ccwu.cc",
                    group_name="Prefetch Test",
                    date="2026-09-02",
                    messages=[],
                    topics=[],
                    user_titles=[],
                    golden_quotes=[],
                )
                if rendered:
                    await self.localizer.localize_html(
                        rendered, context={"template": t_name, "timeout": 8.0}
                    )
            except Exception as e:
                logger.debug(
                    f"[资源预取] 模板 [{t_name}] 模拟渲染 {tmpl_file} 完成: {e}"
                )

        duration_ms = round((time.time() - start_t) * 1000, 2)
        stats = self.localizer.cache_repo.get_stats()
        template_stat = stats.get("by_template", {}).get(t_name, {})

        logger.info(
            f"[资源预取] 模板 [{t_name}] 预取完成！耗时: {duration_ms}ms, "
            f"已缓存该模板资源: {template_stat.get('files', 0)} 个"
        )

        return {
            "template": t_name,
            "duration_ms": duration_ms,
            "template_stats": template_stat,
            "stats": stats,
        }

    async def prefetch_all_templates(self) -> dict[str, Any]:
        """逐个扫描所有内置与自定义模板，全面预取外部字体与静态资源。

        Returns:
            包含预取执行结果与全量缓存统计的字典。
        """
        start_total = time.time()
        templates_info = self.html_templates.get_available_templates()
        template_names = [t["id"] for t in templates_info]
        if "format" not in template_names:
            template_names.append("format")
        if "global" not in template_names:
            template_names.append("global")

        logger.info(
            f"[资源预取] 开始为全部 {len(template_names)} 个模板执行逐项预取..."
        )
        processed: list[dict[str, Any]] = []

        for name in template_names:
            try:
                res = await self.prefetch_template(name)
                processed.append(res)
            except Exception as e:
                logger.warning(f"[资源预取] 预取模板 [{name}] 异常: {e}")

        total_duration_ms = round((time.time() - start_total) * 1000, 2)
        stats = self.localizer.cache_repo.get_stats()
        logger.info(
            f"[资源预取] 全量模板预取完成！总耗时: {total_duration_ms}ms, "
            f"本地缓存总量: {stats['total_files']} 个文件 "
            f"({stats['total_bytes'] / (1024 * 1024):.2f} MB)"
        )

        return {
            "templates": template_names,
            "results": processed,
            "total_duration_ms": total_duration_ms,
            "stats": stats,
        }
