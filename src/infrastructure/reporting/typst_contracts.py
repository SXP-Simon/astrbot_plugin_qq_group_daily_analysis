"""原生报告准备阶段的强类型输入与输出契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class TextRun(TypedDict):
    """普通文本或带本地头像的用户引用。"""

    text: str
    avatar: str


class TypstTopic(TypedDict):
    title: str
    detail: list[TextRun]
    contributors: list[TextRun]


class TypstPortrait(TypedDict):
    name: str
    title: str
    profile: str
    mbti: str
    reason: list[TextRun]
    avatar: str
    image: str
    image_fit: str
    opacity: float


class TypstQuote(TypedDict):
    sender: str
    content: list[TextRun]
    reason: list[TextRun]
    avatar: str


class TypstDimension(TypedDict):
    name: str
    percentage: float
    comment: list[TextRun]
    color: str


class TypstReview(TypedDict):
    title: str
    subtitle: str
    summary: list[TextRun]
    dimensions: list[TypstDimension]


class TypstReportData(TypedDict):
    """可直接序列化的排版数据；不含 HTML、原始用户 ID 和外链图片。"""

    language: str
    font_language: str
    date: str
    generated_at: str
    message_count: int
    participant_count: int
    characters: int
    emoji_count: int
    peak: str
    hours: list[int]
    topics: list[TypstTopic]
    portraits: list[TypstPortrait]
    quotes: list[TypstQuote]
    review: TypstReview | None
    tokens: list[int]
    decorations: list[str]
    miku_allseto: NotRequired[bool]


@dataclass(frozen=True, slots=True)
class TypstIdentityOptions:
    """只在准备阶段使用的平台回调与身份展示选项。

    Args:
        avatar_getter: 平台头像地址查询。
        nickname_getter: 平台昵称查询。
        namespace: 平台缓存命名空间。
        hide_names: 是否隐藏群友身份。
        extended_ids: 是否允许字母数字身份编号。
    """

    avatar_getter: Callable[[str, int | None], Awaitable[str | None]] | None = None
    nickname_getter: Callable[[str], Awaitable[str | None]] | None = None
    namespace: str | None = None
    hide_names: bool = False
    extended_ids: bool = False
