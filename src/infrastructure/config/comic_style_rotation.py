"""漫画风格轮换，只在新生成任务中预留下一套方案。"""

from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import TYPE_CHECKING, TypedDict

from ...shared.type_guards import is_object_list, is_string_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from ...domain.value_objects.group_session import GroupSession


@dataclass(frozen=True)
class ComicStyle:
    """由配置解析出的单套漫画分镜方案。"""

    preset_id: str
    name: str
    prompt: str


@dataclass
class _Progress:
    """保存候选指纹及轮换所需的最小进度。"""

    signature: str
    cursor: int = 0
    anchor: str = ""
    selected_date: str = ""
    last: int = -1
    last_style_name: str = ""
    remaining: list[int] | None = None


class ComicRotationEntry(TypedDict):
    """供管理界面查看的轮换记录。"""

    platform_id: str | None
    group_id: str | None
    last_style_name: str
    last_style_number: int
    selected_date: str


_ROTATION_LOCK = Lock()


def _read_progress(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not is_string_mapping(raw):
        raise ValueError("漫画轮换状态无效")
    return raw


def _write_progress(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=path.parent,
            prefix=path.name,
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as file:
            temporary = path.with_name(os.path.basename(file.name))
            json.dump(state, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def list_comic_rotation(path: Path) -> list[ComicRotationEntry]:
    """读取上次选择，浏览列表不会推进轮换。

    Args:
        path: 插件数据目录内的轮换文件。

    Returns:
        最近使用日期在前的轮换记录。
    """
    with _ROTATION_LOCK:
        raw = _read_progress(path)
    entries: list[ComicRotationEntry] = []
    for scope, entry in raw.items():
        if not is_string_mapping(entry):
            continue
        last, selected_date = entry.get("last"), entry.get("selected_date")
        if not isinstance(last, int) or last < 0 or not isinstance(selected_date, str):
            continue
        platform_id: str | None = None
        group_id: str | None = None
        if scope != "global":
            try:
                session: object = json.loads(scope)
            except ValueError:
                continue
            if (
                not is_object_list(session)
                or len(session) != 2
                or not isinstance(session[0], str)
                or not isinstance(session[1], str)
            ):
                continue
            platform_id, group_id = session[0], session[1]
        name = entry.get("last_style_name")
        entries.append(
            {
                "platform_id": platform_id,
                "group_id": group_id,
                "last_style_name": name if isinstance(name, str) else "",
                "last_style_number": last + 1,
                "selected_date": selected_date,
            }
        )
    return sorted(entries, key=lambda entry: entry["selected_date"], reverse=True)


def reset_comic_rotation(
    path: Path, session: GroupSession | None = None, *, all_scopes: bool = False
) -> None:
    """清空一个范围或全部进度，与生成任务互斥。

    Args:
        path: 插件数据目录内的轮换文件。
        session: 目标群，空值表示共享进度。
        all_scopes: 清空所有范围，也可恢复损坏的状态文件。
    """
    with _ROTATION_LOCK:
        if all_scopes:
            path.unlink(missing_ok=True)
            return
        raw = _read_progress(path)
        key = (
            json.dumps([session.platform_id, session.group_id]) if session else "global"
        )
        if key in raw:
            del raw[key]
            _write_progress(path, raw)


def reserve_comic_style(
    path: Path,
    styles: tuple[ComicStyle, ...],
    mode: str,
    session: GroupSession | None,
    today: date,
) -> ComicStyle:
    """在进程内串行分配风格并原子保存轮换状态。

    Args:
        path: 插件数据目录内的轮换文件。
        styles: 非空的有序候选方案。
        mode: 已校验的轮换模式。
        session: 群级范围的真实会话，全局范围为空。
        today: 插件所在环境的自然日。

    Returns:
        本次任务使用的风格。

    Raises:
        ValueError: 保存的状态文件无法解析或轮换模式无效。
        OSError: 状态文件无法读写。
    """
    scope = json.dumps([session.platform_id, session.group_id]) if session else "global"
    candidates = json.dumps(
        [mode, [asdict(item) for item in styles]], ensure_ascii=False
    )
    signature = sha256(candidates.encode("utf-8")).hexdigest()
    count = len(styles)
    with _ROTATION_LOCK:
        raw = _read_progress(path)
        state = _Progress(signature)
        entry = raw.get(scope)
        if is_string_mapping(entry) and entry.get("signature") == signature:
            cursor, anchor, selected_date, last, remaining = (
                entry.get("cursor"),
                entry.get("anchor"),
                entry.get("selected_date"),
                entry.get("last"),
                entry.get("remaining"),
            )
            if (
                isinstance(cursor, int)
                and isinstance(anchor, str)
                and isinstance(selected_date, str)
                and isinstance(last, int)
                and -1 <= last < count
            ):
                state.cursor = cursor % count
                state.anchor = anchor
                state.selected_date = selected_date
                state.last = last
                if is_object_list(remaining):
                    queue = [
                        item
                        for item in remaining
                        if isinstance(item, int) and 0 <= item < count
                    ]
                    if len(queue) == len(remaining) and len(set(queue)) == len(queue):
                        state.remaining = queue
        today_text = today.isoformat()
        if mode == "sequential":
            selected = state.cursor
            state.cursor = (selected + 1) % count
        elif mode == "daily_sequential":
            anchor_date = date.fromisoformat(state.anchor) if state.anchor else today
            state.anchor = anchor_date.isoformat()
            selected = (today - anchor_date).days % count
        elif mode == "daily_random":
            if state.selected_date == today_text and state.last >= 0:
                return styles[state.last]
            selected = random.randrange(count)
        elif mode == "random":
            selected = random.randrange(count)
        elif mode == "shuffle":
            remaining = state.remaining or []
            if not remaining:
                remaining = random.sample(range(count), count)
                if count > 1 and remaining[0] == state.last:
                    remaining[0], remaining[1] = remaining[1], remaining[0]
            selected = remaining.pop(0)
            state.remaining = remaining
        else:
            raise ValueError("无效的漫画风格轮换模式")
        state.last = selected
        state.last_style_name = styles[selected].name
        state.selected_date = today_text
        raw[scope] = asdict(state)
        _write_progress(path, raw)
    return styles[selected]
