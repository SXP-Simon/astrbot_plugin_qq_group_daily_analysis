import io
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

from src.infrastructure.reporting import cdn_probe


def test_cdn_resources_are_in_git_export():
    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists():
        pytest.skip("仅在 Git 检出目录检查导出规则")
    # 使用工作区属性验证尚未提交的规则，不改动仓库索引或提交历史。
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "--worktree-attributes", "HEAD", "assets"],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=60,
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as package:
        exported = set(package.getnames())
    expected = {
        "assets/" + resource.path
        for resource in cdn_probe.PROBE_RESOURCES
        if resource.kind == "gh"
    }
    assert expected <= exported, (
        f"CDN 文件被导出规则排除了：{sorted(expected - exported)}"
    )

    # 读取工作流的实际排除路径，确保轻量 Release 包与 CDN 的导出规则分开。
    workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    exclusions = re.findall(r"'(:\(exclude\)[^']+)'", workflow)
    assert exclusions
    release_archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            "--worktree-attributes",
            "HEAD",
            "--",
            ".",
            *exclusions,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=60,
    )
    with tarfile.open(fileobj=io.BytesIO(release_archive.stdout), mode="r:") as package:
        release_files = set(package.getnames())
    assert not (expected & release_files)
    assert "assets/profile_assets/manifest.json" in release_files
    assert "pages/daily-analysis/assets/index.js" in release_files
