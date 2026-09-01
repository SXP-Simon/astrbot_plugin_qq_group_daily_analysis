"""模板安装器单元测试（GitHub 链接 / zip 上传安装）。"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from src.infrastructure.reporting.template_installer import (
    TemplateInstallError,
    install_template_from_zip,
    parse_github_repo_url,
    validate_template_name,
)


def build_zip(
    entries: dict[str, bytes | str],
    *,
    leading_root: str | None = None,
) -> bytes:
    """构造 zip 字节。leading_root 不为 None 时所有条目放入该目录前缀下。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            inner_name = f"{leading_root}/{name}" if leading_root else name
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(inner_name, data)
    return buffer.getvalue()


def test_install_from_zip_with_root_dir(tmp_path):
    """带顶层根目录（GitHub archive 形式）的 zip 正常安装。"""
    zip_data = build_zip(
        {
            "image_template.html": "<html>{{ topics_html }}</html>",
            "topic_item.html": "<div>{{ topics }}</div>",
            "template.json": json.dumps({"name": "樱雨日记", "desc": "测试"}),
        },
        leading_root="SakuraRain-main",
    )
    result = install_template_from_zip(zip_data, store_dir=tmp_path)

    assert result["name"] == "SakuraRain"
    assert result["label"] == "樱雨日记"
    assert result["has_image"] is True
    assert result["has_html"] is False
    target = tmp_path / "SakuraRain"
    assert (target / "image_template.html").is_file()
    assert (target / "topic_item.html").is_file()
    assert (target / "template.json").is_file()


def test_install_from_zip_flat_root(tmp_path):
    """无顶层根目录（模板文件直接在 zip 根）需显式指定名字。"""
    zip_data = build_zip(
        {
            "image_template.html": "<html></html>",
            "activity_chart.html": "<svg></svg>",
        }
    )
    with pytest.raises(TemplateInstallError, match="无法从压缩包推断模板名"):
        install_template_from_zip(zip_data, store_dir=tmp_path)

    result = install_template_from_zip(
        zip_data, store_dir=tmp_path, name="gda_flat"
    )
    assert result["has_image"] is True
    assert (tmp_path / "gda_flat" / "activity_chart.html").is_file()


def test_install_with_explicit_name(tmp_path):
    """用户显式指定的模板名优先生效。"""
    zip_data = build_zip(
        {"html_template.html": "<html></html>"},
        leading_root="whatever-main",
    )
    result = install_template_from_zip(
        zip_data, store_dir=tmp_path, name="gda_my_theme"
    )
    assert result["name"] == "gda_my_theme"
    assert (tmp_path / "gda_my_theme" / "html_template.html").is_file()


def test_install_rejects_missing_primary_template(tmp_path):
    """缺少 image_template.html / html_template.html 时拒绝安装。"""
    zip_data = build_zip({"topic_item.html": "<div></div>"})
    with pytest.raises(TemplateInstallError, match="未找到模板主文件"):
        install_template_from_zip(zip_data, store_dir=tmp_path)


def test_install_rejects_zip_slip(tmp_path):
    """zip-slip（../ 路径穿越）被拒绝。"""
    zip_data = build_zip(
        {
            "image_template.html": "<html></html>",
            "../evil.html": "x",
        }
    )
    with pytest.raises(TemplateInstallError, match="非法路径段"):
        install_template_from_zip(zip_data, store_dir=tmp_path)


def test_install_rejects_absolute_path(tmp_path):
    """绝对路径成员被拒绝。"""
    zip_data = build_zip(
        {
            "image_template.html": "<html></html>",
            "/tmp/evil.html": "x",
        }
    )
    with pytest.raises(TemplateInstallError, match="非法绝对路径"):
        install_template_from_zip(zip_data, store_dir=tmp_path)


def test_install_rejects_duplicate_with_builtin(tmp_path):
    """与内置模板重名（如 simple）时拒绝，避免与内置模板隐晦合并。"""
    zip_data = build_zip({"image_template.html": "<html></html>"})
    with pytest.raises(TemplateInstallError, match="与内置模板重名"):
        install_template_from_zip(zip_data, store_dir=tmp_path, name="simple")


def test_install_rejects_existing_target(tmp_path):
    """目标模板已存在时拒绝安装。"""
    (tmp_path / "gda_dup").mkdir(parents=True)
    zip_data = build_zip({"image_template.html": "<html></html>"})
    with pytest.raises(TemplateInstallError, match="已存在"):
        install_template_from_zip(zip_data, store_dir=tmp_path, name="gda_dup")


def test_install_rejects_multiple_template_roots(tmp_path):
    """压缩包内含多个模板根目录时拒绝（歧义）。"""
    zip_data = build_zip(
        {
            "A/image_template.html": "<html>A</html>",
            "B/image_template.html": "<html>B</html>",
        }
    )
    with pytest.raises(TemplateInstallError, match="多个模板目录"):
        install_template_from_zip(zip_data, store_dir=tmp_path)


def test_invalid_meta_json_is_ignored(tmp_path):
    """template.json 内容非法时不影响安装。"""
    zip_data = build_zip(
        {
            "image_template.html": "<html></html>",
            "template.json": "{not valid json",
        },
        leading_root="MetaBroken-main",
    )
    result = install_template_from_zip(zip_data, store_dir=tmp_path)
    assert result["name"] == "MetaBroken"
    assert result["label"] == "MetaBroken"


def test_install_rejects_invalid_zip(tmp_path):
    """非 zip 内容（损坏/伪造）被识别并给出可读错误。"""
    with pytest.raises(TemplateInstallError, match="格式无效"):
        install_template_from_zip(b"this is not a zip archive", store_dir=tmp_path)


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        "   ",
        "a/b",
        "a\\b",
        "..",
        ".",
        ".hidden",
        "trailing.",
        "name:with:colon",
        "a" * 51,
    ],
)
def test_validate_template_name_rejects(bad_name):
    with pytest.raises(TemplateInstallError):
        validate_template_name(bad_name)


def test_validate_template_name_allows_unicode():
    assert validate_template_name("群分析_樱雨") == "群分析_樱雨"
    assert validate_template_name("gda_miku-dream_v2") == "gda_miku-dream_v2"


def test_parse_github_repo_url_valid():
    parsed = parse_github_repo_url("https://github.com/SXP-Simon/MyTheme")
    assert parsed["owner"] == "SXP-Simon"
    assert parsed["repo"] == "MyTheme"
    assert parsed["branch"] == ""
    assert parsed["default_name"] == "MyTheme"

    parsed = parse_github_repo_url("https://github.com/owner/repo.git")
    assert parsed["repo"] == "repo"

    parsed = parse_github_repo_url(
        "https://github.com/owner/repo/tree/feat/theme-beta"
    )
    assert parsed["branch"] == "feat/theme-beta"


def test_parse_github_repo_url_http_scheme_allowed():
    parsed = parse_github_repo_url("http://github.com/owner/repo")
    assert parsed["owner"] == "owner"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "ftp://github.com/owner/repo",
        "https://gitee.com/owner/repo",
        "https://evil.com/owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/archive/refs/heads/main.zip",
        "https://github.com/owner/../repo",
    ],
)
def test_parse_github_repo_url_rejects(bad_url):
    with pytest.raises(TemplateInstallError):
        parse_github_repo_url(bad_url)
