"""持久化漫画模板轮换，按任务原子预留并支持只读查询。"""

from __future__ import annotations

import json
import os
import random
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ...utils.logger import logger

if TYPE_CHECKING:
    from ...domain.value_objects.comic_template_rotation import (
        ComicTemplateRotationSettings,
        ComicTemplateRotationStatus,
    )


@dataclass
class _RotationState:
    """单个作用域的轮换记录；模式或候选顺序变化后重新开始。"""

    mode: str
    candidates: list[str]
    current: str | None = None
    cursor: int = 0
    anchor_date: str = ""
    selected_date: str = ""
    remaining: list[str] | None = None


class ComicTemplateRotationStore:
    """同一路径在所有配置管理器之间共享锁并原子替换状态文件。

    Args:
        state_path: 插件数据目录中的独立状态文件。
    """

    _locks: ClassVar[dict[str, threading.Lock]] = {}
    _locks_guard: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self._lock = self.lock_for_path(state_path)

    @classmethod
    def lock_for_path(cls, state_path: Path) -> threading.Lock:
        """返回共享路径锁，供每日角色状态复用同样的并发隔离规则。"""
        key = os.path.normcase(str(state_path.resolve()))
        with cls._locks_guard:
            return cls._locks.setdefault(key, threading.Lock())

    @staticmethod
    def scope_key(
        settings: ComicTemplateRotationSettings, group_id: str, umo: str | None
    ) -> str:
        """使用包含平台和机器人身份的完整会话隔离群进度。"""
        if settings.scope == "global":
            return "global"
        if not umo or len(umo.rsplit(":", 2)) != 3:
            return ""
        platform, message_type, session_id = umo.rsplit(":", 2)
        if not platform or message_type != "GroupMessage" or not session_id:
            return ""
        if group_id and session_id != group_id:
            return ""
        return "group:" + umo

    def _read(self) -> dict[str, object]:
        """读取持久化边界的 JSON，损坏内容安全重建。"""
        try:
            raw: object = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except ValueError as exc:
            logger.warning(f"读取漫画模板轮换状态失败，将重建进度: {exc}")
            return {}
        if not isinstance(raw, dict) or raw.get("version") != 1:
            logger.warning("漫画模板轮换状态格式无效，将重建进度")
            return {}
        states = raw.get("states")
        return states if isinstance(states, dict) else {}

    @staticmethod
    def _parse_state(
        raw: object, settings: ComicTemplateRotationSettings
    ) -> _RotationState | None:
        """验证一个作用域的记录，忽略旧模式、旧候选池或损坏记录。"""
        if not isinstance(raw, dict):
            return None
        if raw.get("mode") != settings.mode or raw.get("candidates") != list(
            settings.candidates
        ):
            return None
        current = raw.get("current")
        cursor = raw.get("cursor")
        anchor = raw.get("anchor_date")
        selected_date = raw.get("selected_date")
        remaining = raw.get("remaining")
        if (
            (
                current is not None
                and (not isinstance(current, str) or current not in settings.candidates)
            )
            or not isinstance(cursor, int)
            or isinstance(cursor, bool)
            or cursor < 0
            or not isinstance(anchor, str)
            or not isinstance(selected_date, str)
            or (
                remaining is not None
                and (
                    not isinstance(remaining, list)
                    or any(
                        not isinstance(item, str) or item not in settings.candidates
                        for item in remaining
                    )
                    or len(set(remaining)) != len(remaining)
                )
            )
        ):
            return None
        try:
            if anchor:
                date.fromisoformat(anchor)
            if selected_date:
                date.fromisoformat(selected_date)
        except ValueError:
            return None
        if settings.mode == "daily_sequential" and not anchor:
            return None
        if settings.mode == "daily_random" and (not selected_date or current is None):
            return None
        return _RotationState(
            mode=settings.mode,
            candidates=list(settings.candidates),
            current=current,
            cursor=cursor,
            anchor_date=anchor,
            selected_date=selected_date,
            remaining=remaining,
        )

    def _write(self, states: dict[str, object]) -> None:
        """写入失败时中止任务，避免使用未能持久化的轮换预留。

        Args:
            states: 各作用域的持久化记录。

        Raises:
            OSError: 无法原子保存轮换进度。
        """
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.state_path.parent,
                prefix=self.state_path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(
                    {"version": 1, "states": states},
                    temporary,
                    ensure_ascii=False,
                )
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(self.state_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def reserve(
        self,
        settings: ComicTemplateRotationSettings,
        scope_key: str,
        today: date,
    ) -> str:
        """为新生成任务预留一个模板，任务失败也保留已消耗的进度。

        Args:
            settings: 验证后的非固定模式设置。
            scope_key: 已隔离平台和机器人的作用域键。
            today: 运行环境时区中的当前自然日。

        Returns:
            预留的模板标识。

        Raises:
            ValueError: 调用方未提供候选池或有效作用域。
            OSError: 状态无法持久化。
        """
        if not scope_key or not settings.candidates:
            raise ValueError("漫画模板轮换缺少候选模板或有效会话")
        with self._lock:
            states = self._read()
            state = self._parse_state(states.get(scope_key), settings)
            if state is None:
                state = _RotationState(settings.mode, list(settings.candidates))
            pool = settings.candidates
            if settings.mode == "sequential":
                selected = pool[state.cursor % len(pool)]
                state.cursor = (state.cursor + 1) % len(pool)
            elif settings.mode == "daily_sequential":
                state.anchor_date = state.anchor_date or today.isoformat()
                selected = pool[
                    (today - date.fromisoformat(state.anchor_date)).days % len(pool)
                ]
            elif settings.mode == "daily_random":
                if state.selected_date == today.isoformat() and state.current:
                    return state.current
                selected = random.choice(pool)
            elif settings.mode == "shuffle":
                remaining = state.remaining or []
                if not remaining:
                    remaining = list(pool)
                    random.shuffle(remaining)
                    if len(remaining) > 1 and remaining[0] == state.current:
                        remaining[0], remaining[1] = remaining[1], remaining[0]
                selected = remaining.pop(0)
                state.remaining = remaining
            elif settings.mode == "random":
                selected = random.choice(pool)
            else:
                raise ValueError("固定漫画模板无需预留轮换进度")
            state.current = selected
            state.selected_date = today.isoformat()
            states[scope_key] = asdict(state)
            self._write(states)
            return selected

    def status(
        self,
        settings: ComicTemplateRotationSettings,
        scope_key: str,
        today: date,
        template_names: dict[str, str],
    ) -> ComicTemplateRotationStatus:
        """查询当前及可确定的下一模板，不创建文件也不抽取随机数。"""
        with self._lock:
            state = self._parse_state(self._read().get(scope_key), settings)
        current = state.current if state else None
        next_id: str | None = None
        pool = settings.candidates
        if settings.mode == "fixed":
            current = next_id = settings.fixed_template_id
        elif scope_key and pool:
            if settings.mode == "sequential":
                next_id = pool[(state.cursor if state else 0) % len(pool)]
            elif settings.mode == "daily_sequential":
                anchor = date.fromisoformat(state.anchor_date) if state else today
                offset = (today - anchor).days
                current = pool[offset % len(pool)]
                next_id = pool[(offset + 1) % len(pool)]
            elif settings.mode == "daily_random":
                if not state or state.selected_date != today.isoformat():
                    current = None
                else:
                    next_id = current
            elif settings.mode == "shuffle" and state and state.remaining:
                next_id = state.remaining[0]
        warning = settings.warning
        if settings.scope == "group" and not scope_key:
            warning = warning or "请先选择完整群会话以查看独立轮换进度"
        return {
            "mode": settings.mode,
            "scope": settings.scope,
            "scope_key": scope_key,
            "candidates": list(pool),
            "current_template_id": current,
            "current_template_name": template_names.get(current) if current else None,
            "next_template_id": next_id,
            "next_template_name": template_names.get(next_id) if next_id else None,
            "date": today.isoformat(),
            "initialized": state is not None,
            "warning": warning,
        }

    def reset(self, scope_key: str) -> None:
        """清除选定作用域的进度，其他群或全局记录不受影响。"""
        if not scope_key:
            raise ValueError("重置群级漫画模板进度需要完整群会话标识")
        with self._lock:
            states = self._read()
            if scope_key in states:
                del states[scope_key]
                self._write(states)
