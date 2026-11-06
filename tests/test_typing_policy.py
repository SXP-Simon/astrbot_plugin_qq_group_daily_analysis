"""验证禁止 Any 的配置确实拦截常见写法，而不误伤明确的边界类型。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("source", "forbidden"),
    [
        ("from typing import Any\nvalue: Any\n", True),
        ("from typing import Any as Dynamic\nvalue: list[Dynamic]\n", True),
        ("import typing as t\nvalue: t.Any\n", True),
        ("from typing_extensions import Any as Dynamic\nvalue: Dynamic\n", True),
        ("from collections.abc import Mapping\nvalue: Mapping[str, object]\n", False),
    ],
)
def test_ruff_bans_explicit_any(source, forbidden):
    result = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts/check_python.py"), "lint",
            "--select", "TID251", "--output-format", "json",
            "--stdin-filename", "src/_typing_policy_probe.py", "-",
        ],
        cwd=ROOT, input=source, encoding="utf-8", capture_output=True, check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    diagnostics = json.loads(result.stdout)
    assert bool(diagnostics) is forbidden
    assert all(item["code"] == "TID251" for item in diagnostics)
