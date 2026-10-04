"""日志格式串自检：防止「格式串里写了字面 % 又带了参数」这类运行时崩溃。

来历（真实事故，2026-10-05）：报告语言那行日志想写「某语言占比 >70% 才判」，
字面 % 被当作格式符，运行时抛
``ValueError: not enough arguments for format string``，
整次分析在「清洗完消息」之后直接失败——单元测试全绿也发现不了，
只有真机端到端跑一次才暴露。本文件把这类错误做成静态回归：
遍历 ``src/`` 下所有 ``logger.<level>("...", ...)`` 调用，用 ``%`` 试格式化一遍。
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}


def _iter_log_calls() -> list[tuple[Path, int, str, int]]:
    """收集 (文件, 行号, 格式串, 参数个数)；只取「字面量格式串」的日志调用。"""
    calls: list[tuple[Path, int, str, int]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - 语法错误交给 ruff/pytest 报
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            method = getattr(node.func, "attr", "")
            if method not in LOG_METHODS:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            calls.append((path, node.lineno, first.value, len(node.args) - 1))
    return calls


def test_logger_format_strings_are_well_formed() -> None:
    """日志格式串必须能被 % 正确格式化（字面 % 需写成 %%，参数个数要对得上）。"""
    problems: list[str] = []
    for path, lineno, message, arg_count in _iter_log_calls():
        if "%(" in message:
            # 映射式写法（%(name)s）由调用方传 dict，这里无法静态校验，跳过
            continue
        try:
            message % tuple(0 for _ in range(arg_count))
        except (ValueError, TypeError) as exc:
            problems.append(f"{path.relative_to(ROOT)}:{lineno} {message!r} → {exc}")
    assert not problems, "日志格式串有问题（字面 % 请写 %%）：\n" + "\n".join(problems)


def test_report_language_log_line_is_covered() -> None:
    """确保上一条自检确实覆盖到报告语言那行日志（防止扫描逻辑失效后静默通过）。"""
    messages = [message for _, _, message, _ in _iter_log_calls()]
    assert any("报告语言自动判断" in message for message in messages)
