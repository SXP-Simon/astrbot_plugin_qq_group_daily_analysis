"""验证 HTML 报告产物命名始终遵循 html_filename_format 配置，且产物可凭追踪号定位。

回归背景：TraceContext.get() 在无任务上下文时也会返回随机 ID，
generators.generate_html_report 里「有追踪 ID 就用固定命名」的分支因此恒真，
用户配置的 html_filename_format（含其默认值）成了不可达代码。
命名交给用户配置后，产物改为在 HTML 头部内嵌 astrbot-trace-id，保证仍可按追踪号反查文件。
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from src.infrastructure.reporting.generators import ReportGenerator
from src.shared.trace_context import TraceContext

ANALYSIS_RESULT = {"topics": [], "user_titles": [], "statistics": None}

AMBIENT_TRACE = "web_manual_20261005_012347_e79b1bd4dc63"

NO_HEAD_HTML = "<html>naming</html>"

WITH_HEAD_HTML = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
    '    <meta charset="UTF-8">\n    <title>群聊日常分析看板</title>\n</head>\n'
    "<body>ok</body>\n</html>\n"
)


class FakeConfig:
    """只暴露命名链路所需配置读取的最小桩。"""

    def __init__(self, output_dir, filename_format):
        self._output_dir = output_dir
        self._filename_format = filename_format

    def get_html_output_dir(self):
        return str(self._output_dir)

    def get_html_filename_format(self):
        return self._filename_format

    def get_report_template(self):
        return "HatsuneMiku"


def build_generator(output_dir, filename_format, html=NO_HEAD_HTML):
    generator = object.__new__(ReportGenerator)
    generator.config_manager = FakeConfig(output_dir, filename_format)
    generator.html_templates = SimpleNamespace(render_template=lambda *a, **k: html)
    generator._reuse_avatars_in_final_html = lambda html_content, *args: html_content

    async def fake_prepare_render_data(*args, **kwargs):
        return {}

    generator._prepare_render_data = fake_prepare_render_data
    return generator


def run_html_report(generator, group_id="344184506", **kwargs):
    with TraceContext(trace_id=AMBIENT_TRACE) as trace:
        result = asyncio.run(
            generator.generate_html_report(ANALYSIS_RESULT, group_id, **kwargs)
        )
    return trace, result


def test_filename_format_applies_when_trace_context_active(tmp_path):
    """存在 TraceContext 时，产物路径仍应遵守 html_filename_format。"""
    generator = build_generator(tmp_path, "${group_id}/${date}.html")

    _, (html_path, json_path) = run_html_report(generator)

    assert html_path is not None
    assert json_path is None
    assert Path(html_path).parent == tmp_path / "344184506"
    assert Path(html_path).name.endswith(".html")
    assert "report_344184506_" not in Path(html_path).name


def test_trace_id_variable_renders_bound_trace(tmp_path):
    """${trace_id} 变量在格式中可用，取当前 TraceContext 的追踪号。"""
    generator = build_generator(tmp_path, "报告_${group_id}_${trace_id}.html")

    trace, (html_path, _) = run_html_report(generator)

    assert html_path is not None
    assert Path(html_path).name == f"报告_344184506_{trace.trace_id}.html"


def test_explicit_trace_id_wins_over_ambient_context(tmp_path):
    """续跑/重绘显式传入的 trace_id 应优先于当前环境上下文。"""
    generator = build_generator(tmp_path, "报告_${trace_id}.html")

    _, (html_path, _) = run_html_report(generator, trace_id="report_source_trace")

    assert html_path is not None
    assert Path(html_path).name == "报告_report_source_trace.html"


def test_custom_filename_still_has_highest_priority(tmp_path):
    """custom_filename（换模板重绘）优先级不变，且自动补 .html 后缀。"""
    generator = build_generator(tmp_path, "${group_id}/${date}.html")

    _, (html_path, json_path) = run_html_report(
        generator, custom_filename="report_344184506_20261005_rerender"
    )

    assert html_path is not None
    assert json_path is None
    assert Path(html_path) == tmp_path / "report_344184506_20261005_rerender.html"
    assert not (tmp_path / "report_344184506_20261005_rerender.json").exists()


def test_path_traversal_protection_still_blocks_unsafe_format(tmp_path):
    """配置格式含目录穿越时仍被拦截，不会写出目录外的文件。"""
    output_dir = tmp_path / "html"
    generator = build_generator(output_dir, "../escaped/${group_id}.html")

    _, (html_path, json_path) = run_html_report(generator)

    assert html_path is None
    assert json_path is None
    assert not (tmp_path / "escaped").exists()


def test_html_artifact_embeds_trace_id_meta(tmp_path):
    """自定义命名后，产物仍内嵌追踪号，可凭追踪号反查文件。"""
    generator = build_generator(tmp_path, "${group_id}/${date}.html", WITH_HEAD_HTML)

    trace, (html_path, json_path) = run_html_report(generator)

    assert html_path is not None
    assert json_path is None
    content = Path(html_path).read_text(encoding="utf-8")
    assert f'<meta name="astrbot-trace-id" content="{trace.trace_id}">' in content
    assert content.count("astrbot-trace-id") == 1
    assert content.startswith("<!DOCTYPE html>")
    assert "<title>群聊日常分析看板</title>" in content


def test_trace_id_meta_skipped_when_template_has_no_head(tmp_path):
    """模板不含 head 节点时跳过注入，不破坏原有产物。"""
    generator = build_generator(tmp_path, "${group_id}/${date}.html", NO_HEAD_HTML)

    _, (html_path, _) = run_html_report(generator)

    assert html_path is not None
    assert Path(html_path).read_text(encoding="utf-8") == NO_HEAD_HTML


def test_trace_id_meta_injection_is_idempotent():
    """重复注入同一份产物时保持幂等，不产生第二份 meta。"""
    once = ReportGenerator._inject_trace_id_meta(WITH_HEAD_HTML, "trace-1")
    twice = ReportGenerator._inject_trace_id_meta(once, "trace-1")

    assert once == twice
    assert once.count("astrbot-trace-id") == 1


def test_trace_id_meta_escapes_attribute_value():
    """追踪号进入 HTML 属性前必须转义，避免破坏文档结构。"""
    injected = ReportGenerator._inject_trace_id_meta("<head></head>", 'a&b"c<d')

    assert 'content="a&amp;b&quot;c&lt;d"' in injected


def test_trace_id_meta_skipped_for_header_only_document():
    """只有 header 元素（无 head）的文档不得被注入 meta，保持结构不变。"""
    html = "<html><body><header>标题</header><p>正文</p></body></html>"

    assert ReportGenerator._inject_trace_id_meta(html, "trace-1") == html


def test_trace_id_meta_not_blocked_by_plain_text_occurrence():
    """正文里出现同名文字不应阻止注入，产物仍需带上可反查的 meta。"""
    html = "<head></head><body>说明：astrbot-trace-id 会写进 head</body>"

    injected = ReportGenerator._inject_trace_id_meta(html, "trace-1")

    assert injected.count('<meta name="astrbot-trace-id"') == 1


def test_trace_id_meta_replaced_when_trace_id_changes():
    """同一文件被另一任务复用时，旧追踪号应被改写为当前追踪号。"""
    html = '<head><meta name="astrbot-trace-id" content="stale"></head>'

    injected = ReportGenerator._inject_trace_id_meta(html, "fresh")

    assert 'content="fresh"' in injected
    assert "stale" not in injected
    assert injected.count("astrbot-trace-id") == 1
