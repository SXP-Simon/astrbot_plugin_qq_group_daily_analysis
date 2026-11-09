from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .type_guards import is_string_mapping


@dataclass(frozen=True)
class ComicPreset:
    """内置漫画分镜风格。"""

    name: str
    description: str
    prompt: str


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
        name, description, prompt = (
            item.get("name"),
            item.get("description"),
            item.get("prompt"),
        )
        if not (
            isinstance(name, str)
            and isinstance(description, str)
            and isinstance(prompt, str)
        ):
            raise ValueError(f"漫画风格字段无效：{key}")
        result[key] = ComicPreset(name, description, prompt)
    return result


COMIC_PRESETS = _load_catalog()
DEFAULT_COMIC_STORYBOARD_PROMPT = COMIC_PRESETS["classic"].prompt
