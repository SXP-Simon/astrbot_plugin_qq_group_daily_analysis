"""漫画内置提示词目录，与 WebUI 共用同一份 JSON。"""

import json
from pathlib import Path

_catalog: object = json.loads(
    Path(__file__).with_name("comic_prompt_templates.json").read_text(encoding="utf-8")
)
if not isinstance(_catalog, dict):
    raise ValueError("漫画提示词目录必须是对象")

COMIC_STORYBOARD_PROMPTS: dict[str, str] = {}
COMIC_TEMPLATE_NAMES: dict[str, str] = {}
COMIC_PROMPT_PREVIEWS: dict[str, str] = {}
for _key, _entry in _catalog.items():
    if (
        not isinstance(_key, str)
        or not isinstance(_entry, dict)
        or not isinstance(_entry.get("prompt"), str)
        or not isinstance(_entry.get("name"), str)
    ):
        raise ValueError("漫画提示词目录条目格式无效")
    COMIC_STORYBOARD_PROMPTS[_key] = _entry["prompt"]
    COMIC_TEMPLATE_NAMES[_key] = _entry["name"]
    _preview = _entry.get("preview")
    if _preview is not None:
        if (
            not isinstance(_preview, str)
            or Path(_preview).name != _preview
            or "/" in _preview
            or "\\" in _preview
            or not _preview.endswith(".webp")
        ):
            raise ValueError("漫画提示词预览必须是 WebP 文件名")
        COMIC_PROMPT_PREVIEWS[_key] = _preview

DEFAULT_COMIC_STORYBOARD_PROMPT = COMIC_STORYBOARD_PROMPTS["classic"]
