"""Trace id 与文件名组件的控制字符清洗回归。"""

from src.shared.trace_context import TraceContext, sanitize_component


def _has_control(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def test_generate_strips_c0_and_del():
    trace_id = TraceContext.generate(prefix="manual", group_name="A\x11B\x7fC")
    assert not _has_control(trace_id)
    assert "ABC" in trace_id


def test_sanitize_component_strips_c0_and_del():
    assert sanitize_component("a\x00b\x11c\x1fd\x7fe") == "abcde"
    assert sanitize_component("正常群名") == "正常群名"
