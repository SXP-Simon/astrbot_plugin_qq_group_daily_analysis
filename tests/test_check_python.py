"""Check tool pinning and interpreter selection without installing tools."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_python import main


@pytest.mark.parametrize(
    ("arguments", "tool", "suffix"),
    [
        (["lint", "src/a.py"], "ruff", ["check", "src/a.py"]),
        (["format", "--check", "src/a.py"], "ruff", ["format", "--check", "src/a.py"]),
        (["typecheck"], "pyright", ["--pythonpath", sys.executable]),
    ],
)
def test_pinned_tool_and_arguments(arguments, tool, suffix):
    root = Path(__file__).resolve().parents[1]
    requirement = next(
        line for line in (root / "requirements-tools.txt").read_text().splitlines()
        if line.startswith(f"{tool}==")
    )
    with patch.object(sys, "argv", ["check_python.py", *arguments]), patch(
        "scripts.check_python.subprocess.call", return_value=7
    ) as run:
        assert main() == 7
    run.assert_called_once_with(
        ["uv", "tool", "run", "--from", requirement, tool, *suffix], cwd=root
    )


def test_invalid_check_does_not_start_process():
    with patch.object(sys, "argv", ["check_python.py", "unknown"]), patch(
        "scripts.check_python.subprocess.call"
    ) as run, pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    run.assert_not_called()


@pytest.mark.parametrize("api_name", ["previous_api", "current_api"])
def test_pyright_deprecated_api_gate(tmp_path, api_name):
    """实际运行固定版检查器，验证弃用接口失败而替代接口通过。"""
    root = Path(__file__).resolve().parents[1]
    requirement = next(
        line for line in (root / "requirements-tools.txt").read_text().splitlines()
        if line.startswith("pyright==")
    )
    (tmp_path / "api.py").write_text(
        'from typing_extensions import deprecated\n'
        '@deprecated("请使用 current_api")\n'
        'def previous_api() -> None: pass\n'
        'def current_api() -> None: pass\n',
        encoding="utf-8",
    )
    (tmp_path / "probe.py").write_text(
        f"from api import {api_name} as run\nrun()\n", encoding="utf-8",
    )
    config = tmp_path / "pyrightconfig.json"
    config.write_text(json.dumps({
        "extends": str(root / "pyrightconfig.json"),
        "include": ["api.py", "probe.py"],
        "extraPaths": [],
    }), encoding="utf-8")
    result = subprocess.run(
        ["uv", "tool", "run", "--from", requirement, "pyright", "--pythonpath", sys.executable,
         "--project", str(config), "--outputjson"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    diagnostics = json.loads(result.stdout)
    deprecated = [
        item for item in diagnostics["generalDiagnostics"]
        if item.get("rule") == "reportDeprecated"
    ]
    if api_name == "previous_api":
        assert result.returncode == 1, result.stdout + result.stderr
        assert deprecated and all(item["severity"] == "error" for item in deprecated)
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert diagnostics["summary"]["errorCount"] == 0
