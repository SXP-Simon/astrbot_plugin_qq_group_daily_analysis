from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .type_guards import is_string_mapping


@dataclass(frozen=True)
class ComicPreset:
    """内置漫画分镜风格及对应的示例图。"""

    name: str
    description: str
    prompt: str
    preview: str


def _load_catalog() -> dict[str, ComicPreset]:
    """读取前后端共用的内置风格目录。

    Returns:
        按配置界面展示顺序排列的风格。

    Raises:
        ValueError: 内置目录数据无效。
    """
    raw: object = json.loads(
        Path(__file__)
        .with_name("comic_prompt_templates.json")
        .read_text(encoding="utf-8")
    )
    if not is_string_mapping(raw):
        raise ValueError("漫画风格目录格式无效")
    result: dict[str, ComicPreset] = {}
    for key, item in raw.items():
        if not is_string_mapping(item):
            raise ValueError(f"无效的漫画风格：{key}")
        name, description, prompt, preview = (
            item.get("name"),
            item.get("description"),
            item.get("prompt"),
            item.get("preview"),
        )
        if not (
            isinstance(name, str)
            and isinstance(description, str)
            and isinstance(prompt, str)
            and isinstance(preview, str)
            and Path(preview).name == preview
            and preview.endswith(".webp")
            and "/" not in preview
            and chr(92) not in preview
        ):
            raise ValueError(f"漫画风格字段无效：{key}")
        result[key] = ComicPreset(name, description, prompt, preview)
    return result


COMIC_PRESETS = _load_catalog()
DEFAULT_COMIC_STORYBOARD_PROMPT = COMIC_PRESETS["classic"].prompt
COMIC_PREVIEW_ORIGIN = (
    "https://raw.githubusercontent.com/Liangyu-G/astrbot_plugin_qq_group_daily_analysis/"
    "31c9b759cfede8e9efb5512bb899a5880a761a64/assets/comic_previews/"
)
