"""验证离线脚本不依赖 AstrBot 启动或真实头像接口。"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("theme", "template_file", "mode"),
    [
        ("HatsuneMiku", "image_template.html", "mbti"),
        ("maria", "html_template.html", "sbti"),
    ],
)
def test_debug_render_standalone_daily_example(tmp_path, theme, template_file, mode):
    """从独立进程生成两类报告，保留示例正文、内嵌头像和人格模式。"""
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "nested" / "report.html"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "debug_render.py"),
            "-t", theme,
            "-f", template_file,
            "-m", mode,
            "-l", "zh-Hans",
            "-o", str(output),
        ],
        cwd=root,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = output.read_text(encoding="utf-8")
    assert "周六去公园" in rendered
    assert "电饭锅鸡腿饭" in rendered
    assert "2026年10月23日 · Demo" in rendered
    assert "小岚" in rendered
    assert re.search(r"data:image/(?:png|jpeg);base64,", rendered)
    assert "qlogo.cn" not in rendered
    assert not re.search(r"\[8001000[1-8]\]", rendered)
    # 18 处话题引用与 8 处金句锐评引用都经过正式的用户胶囊渲染。
    assert rendered.count('class="user-capsule"') >= 26
    if mode == "sbti":
        assert "/profile_assets@main/sbti/" in rendered


def test_mock_prose_uses_user_references_and_consistent_statistics():
    """示例正文通过用户 ID 引用群友，统计与关联字段保持自洽。"""
    script = Path(__file__).resolve().parents[1] / "scripts" / "debug_render.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))
    render = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "debug_render"
    )
    assignment = next(
        node for node in render.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "mock_data"
    )
    data = ast.literal_eval(assignment.value)
    users = data["user_analysis"]
    prose = [topic["detail"] for topic in data["topics"]]
    prose.extend(quote["reason"] for quote in data["statistics"]["golden_quotes"])
    for text in prose:
        references = re.findall(r"\[(\d+)\]", text)
        assert references
        assert set(references) <= users.keys()
        assert not any(user["nickname"] in text for user in users.values())
    for topic in data["topics"]:
        assert topic["contributors"] == [
            users[uid]["nickname"] for uid in topic["contributor_ids"]
        ]
    stats = data["statistics"]
    assert stats["message_count"] == sum(
        stats["activity_visualization"]["hourly_activity"].values()
    )
    tokens = stats["token_usage"]
    assert tokens["total_tokens"] == tokens["prompt_tokens"] + tokens["completion_tokens"]
