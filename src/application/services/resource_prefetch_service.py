"""预取并预热报告模板静态资源与字体的应用层服务。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ...infrastructure.reporting.templates import HTMLTemplates
from ...infrastructure.resources.html_resource_localizer import HTMLResourceLocalizer
from ...utils.logger import logger


class ResourcePrefetchService:
    """用于扫描报告模板并预先下载缓存所有外部静态资源的应用服务。"""

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

    async def prefetch_all_templates(self) -> dict[str, Any]:
        """扫描所有内置与自定义模板，全面预取外部字体与静态资源。

        Returns:
            包含预取执行结果与缓存统计的字典。
        """
        templates_info = self.html_templates.get_available_templates()
        template_names = [t["id"] for t in templates_info]
        # 补全可能存在的特殊子模板（如 format）
        if "format" not in template_names:
            template_names.append("format")

        logger.info(
            f"[资源预取] 开始为 {len(template_names)} 个模板预取静态资源与字体..."
        )
        processed_templates: list[str] = []

        # 1. 扫描模板目录下的所有 HTML 和 CSS 源文件
        base_dir = Path(self.html_templates.base_dir)
        template_files: list[Path] = []
        if base_dir.is_dir():
            for p in base_dir.rglob("*.html"):
                template_files.append(p)
            for p in base_dir.rglob("*.css"):
                template_files.append(p)

        # 2. 扫描用户自定义模板目录
        get_custom_dir = getattr(
            self.html_templates.config_manager, "get_custom_report_template_dir", None
        )
        if callable(get_custom_dir):
            sample_res = get_custom_dir("")
            if sample_res:
                p_custom = Path(str(sample_res))
                custom_root = p_custom if p_custom.is_dir() else p_custom.parent
                if custom_root.is_dir():
                    for p in custom_root.rglob("*.html"):
                        template_files.append(p)
                    for p in custom_root.rglob("*.css"):
                        template_files.append(p)

        # 异步遍历各模板源文件进行嗅探与预取
        async def _process_file(file_path: Path):
            try:
                content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
                # 将 Jinja 占位符替换为真实的默认镜像地址以供预取
                content = content.replace(
                    "{{ t2i_google_fonts_mirror }}", "https://fonts.googleapis.com"
                )
                content = content.replace(
                    "{{ t2i_gstatic_mirror }}", "https://fonts.gstatic.com"
                )
                content = content.replace(
                    "{{ t2i_atri_font_mirror }}", "https://tc.ciallo.ccwu.cc"
                )
                await self.localizer.localize_html(content, context={"timeout": 10.0})
            except Exception as e:
                logger.warning(f"[资源预取] 预取模板文件失败 {file_path}: {e}")

        tasks = [_process_file(f) for f in template_files]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 3. 对每个主题执行一次模拟渲染以覆盖动态生成的静态链接
        for name in template_names:
            try:
                rendered = self.html_templates.render_template(
                    "image_template.html",
                    template_theme=name,
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
                        rendered, context={"timeout": 10.0}
                    )
                processed_templates.append(name)
            except Exception as e:
                logger.debug(f"[资源预取] 模板 {name} 模拟预取渲染完成: {e}")
                processed_templates.append(name)

        stats = self.localizer.cache_repo.get_stats()
        logger.info(
            f"[资源预取] 预取完成！当前本地缓存文件数: {stats['total_files']} "
            f"({stats['total_bytes'] / (1024 * 1024):.2f} MB)"
        )

        return {
            "templates": processed_templates,
            "stats": stats,
        }
