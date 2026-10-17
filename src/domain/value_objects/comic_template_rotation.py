"""漫画模板轮换设置、任务快照与状态查询契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

ComicTemplateMode = Literal[
    "fixed", "sequential", "daily_sequential", "random", "daily_random", "shuffle"
]
ComicTemplateScope = Literal["global", "group"]


@dataclass(frozen=True)
class ComicTemplateSelection:
    """单次生成已经预留的模板，重试期间保持不变。"""

    template_id: str
    template_name: str
    mode: ComicTemplateMode
    scope: ComicTemplateScope
    prompt: str
    character_override: bool = False


@dataclass(frozen=True)
class ComicGenerationSnapshot:
    """在任务开始时冻结的角色、人格、参考图和模板配置。"""

    character_name: str
    persona_id: str
    reference_images: tuple[str, ...]
    template: ComicTemplateSelection


class ComicTemplateRotationStatus(TypedDict):
    """不消耗轮换进度的 WebUI 状态响应。"""

    mode: ComicTemplateMode
    scope: ComicTemplateScope
    scope_key: str
    candidates: list[str]
    current_template_id: str | None
    current_template_name: str | None
    next_template_id: str | None
    next_template_name: str | None
    date: str
    initialized: bool
    warning: str | None


@dataclass(frozen=True)
class ComicTemplateRotationSettings:
    """已经归一化的轮换配置。"""

    mode: ComicTemplateMode
    scope: ComicTemplateScope
    candidates: tuple[str, ...]
    fixed_template_id: str
    custom_prompt: str
    warning: str | None = None
