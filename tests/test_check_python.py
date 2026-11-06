"""Check tool pinning and interpreter selection without installing tools."""

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
