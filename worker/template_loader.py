"""
从 Workers 静态资源绑定中加载模板。
"""

from __future__ import annotations

from jinja2 import DictLoader, Environment, select_autoescape

from src.shared.web_report_renderer import normalize_template_name

_TEMPLATE_FILES = (
    "image_template.html",
    "topic_item.html",
    "user_title_item.html",
    "quote_item.html",
    "chat_quality_item.html",
    "activity_chart.html",
)
_ENV_CACHE: dict[str, Environment] = {}


class AssetTemplateLoader:
    def __init__(self, assets_binding):
        self.assets_binding = assets_binding

    async def has_template(self, template_name: str | None) -> bool:
        normalized = normalize_template_name(template_name)
        if not normalized:
            return False

        response = await self.assets_binding.fetch(
            f"https://assets.local/{normalized}/image_template.html"
        )
        return response.status == 200

    async def get_environment(self, template_name: str) -> Environment:
        normalized = normalize_template_name(template_name)
        if not normalized:
            raise ValueError("invalid template name")

        cached = _ENV_CACHE.get(normalized)
        if cached is not None:
            return cached

        template_sources: dict[str, str] = {}
        for template_file in _TEMPLATE_FILES:
            response = await self.assets_binding.fetch(
                f"https://assets.local/{normalized}/{template_file}"
            )
            if response.status != 200:
                raise FileNotFoundError(
                    f"missing template asset: {normalized}/{template_file}"
                )
            template_sources[template_file] = await response.text()

        env = Environment(
            loader=DictLoader(template_sources),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        _ENV_CACHE[normalized] = env
        return env
