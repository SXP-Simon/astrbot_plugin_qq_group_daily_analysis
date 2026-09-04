"""模板安装器单元测试（GitHub 链接 / zip 上传安装）。"""

from __future__ import annotations

import asyncio
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from src.infrastructure.reporting.template_installer import (
    TemplateInstallError,
    _archive_url_candidates,
    install_template_from_zip,
    is_path_within,
    parse_github_repo_url,
    preview_candidate_files,
    uninstall_template,
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

    result = install_template_from_zip(zip_data, store_dir=tmp_path, name="gda_flat")
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


def test_install_rejects_control_char_filename():
    """zip 成员文件名含控制字符时拒绝（防御性；标准库无法构造真实样本，直接测校验函数）。"""
    from src.infrastructure.reporting.template_installer import (
        _validate_archive_members,
    )

    class FakeMember:
        def __init__(self, name: str, size: int = 1):
            self.filename = name
            self.file_size = size

    class FakeZip:
        def infolist(self):
            return [FakeMember("ok.html"), FakeMember("bad\x00name.html")]

    with pytest.raises(TemplateInstallError, match="控制字符"):
        _validate_archive_members(FakeZip())  # type: ignore[arg-type]


def test_uninstall_rejects_symlink_target(tmp_path):
    """卸载目标为符号链接时拒绝（防删除链接指向的其他目录）。"""
    real_dir = tmp_path / "real_target"
    real_dir.mkdir()
    (real_dir / "image_template.html").write_text("<html></html>", encoding="utf-8")
    link = tmp_path / "gda_link"
    try:
        link.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建目录符号链接")
    with pytest.raises(TemplateInstallError, match="模板名非法"):
        uninstall_template("gda_link", store_dir=tmp_path)
    # 链接与目标均未被删除
    assert real_dir.is_dir()
    assert link.is_symlink()


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


def test_archive_url_candidates():
    """归档分支候选：显式分支不回退；API 解析成功只用结果；解析失败回退 main→master。"""
    # 用户显式指定分支（含 /tree/<分支>）→ 只尝试该分支，不静默回退
    assert _archive_url_candidates("feature/x") == ["feature/x"]
    assert _archive_url_candidates("dev") == ["dev"]
    # GitHub API 解析出默认分支 → 只用解析结果
    assert _archive_url_candidates("main") == ["main"]
    assert _archive_url_candidates("dev3") == ["dev3"]
    # API 不可用（空串）→ 依次回退 main → master
    assert _archive_url_candidates("") == ["main", "master"]


def test_parse_github_repo_url_valid():
    parsed = parse_github_repo_url("https://github.com/SXP-Simon/MyTheme")
    assert parsed["owner"] == "SXP-Simon"
    assert parsed["repo"] == "MyTheme"
    assert parsed["branch"] == ""
    assert parsed["default_name"] == "MyTheme"

    parsed = parse_github_repo_url("https://github.com/owner/repo.git")
    assert parsed["repo"] == "repo"

    parsed = parse_github_repo_url("https://github.com/owner/repo/tree/feat/theme-beta")
    assert parsed["branch"] == "feat/theme-beta"


def test_parse_github_repo_url_http_scheme_rejected():
    # 明文 http 一律拒绝：下载链路虽然硬编码 https，但入口收紧避免误导与中间人疑虑
    with pytest.raises(TemplateInstallError):
        parse_github_repo_url("http://github.com/owner/repo")


def test_is_path_within_basic(tmp_path):
    """is_path_within：根内为 True（含自身），根外与含 .. 的归一化路径按解析结果判定。"""
    store = tmp_path / "store"
    store.mkdir()
    inner = store / "gda_theme"
    inner.mkdir()
    (store / "a" / "b").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()

    assert is_path_within(store, store) is True
    assert is_path_within(inner, store) is True
    assert is_path_within(store / "a" / "b" / ".." / "c", store) is True
    assert is_path_within(outside, store) is False
    # 根内的路径即使不存在也判定为“在范围内”（语义仅比较解析后的路径，
    # 不要求文件存在——预览未安装模板时由此进入后续 404 分支）
    assert is_path_within(store / "not_exist", store) is True


def test_preview_candidate_files_selects_jpg_png(tmp_path):
    """preview/demo 的 jpg/png 中仅存在且非链接的文件被返回，其他类型被忽略。"""
    tpl_dir = tmp_path / "gda_theme"
    tpl_dir.mkdir()
    (tpl_dir / "preview.jpg").write_bytes(b"small-jpg")
    (tpl_dir / "demo.png").write_bytes(b"small-png")
    (tpl_dir / "not_a_preview.txt").write_text("x")

    found = preview_candidate_files(tpl_dir)
    assert [p.name for p in found] == ["preview.jpg", "demo.png"]


def test_preview_candidate_files_rejects_oversize(tmp_path, monkeypatch):
    """超过 MAX_PREVIEW_FILE_SIZE 的预览文件被拒绝（防超大图读入内存）。"""
    tpl_dir = tmp_path / "gda_theme"
    tpl_dir.mkdir()
    (tpl_dir / "preview.jpg").write_bytes(b"x" * 64)

    monkeypatch.setattr(
        "src.infrastructure.reporting.template_installer.MAX_PREVIEW_FILE_SIZE", 32
    )
    assert preview_candidate_files(tpl_dir) == []


def test_preview_candidate_files_rejects_symlink(tmp_path):
    """指向模板目录外文件的符号链接预览图被拒绝（防读取任意本地文件）。"""
    tpl_dir = tmp_path / "gda_theme"
    tpl_dir.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"secret-picture")

    try:
        os.symlink(outside, tpl_dir / "preview.jpg")
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建符号链接")

    (tpl_dir / "demo.png").write_bytes(b"ok")
    found = preview_candidate_files(tpl_dir)
    assert [p.name for p in found] == ["demo.png"]


def test_install_marker_write_failure_cleans_target(tmp_path, monkeypatch):
    """安装标记写入失败必须视为安装失败并清理目标目录（否则留下无法卸载的孤儿模板）。"""
    import src.infrastructure.reporting.template_installer as tpl_mod

    zip_data = build_zip(
        {"image_template.html": "<html></html>"},
        leading_root="gda_badge-main",
    )

    def boom(*args, **kwargs):
        raise TemplateInstallError("写入安装标记失败: disk full")

    monkeypatch.setattr(tpl_mod, "_write_install_marker", boom)
    with pytest.raises(TemplateInstallError, match="写入安装标记失败"):
        install_template_from_zip(zip_data, store_dir=tmp_path)
    assert not (tmp_path / "gda_badge").exists()


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
        "https://github.com/owner/repo/tree/../x",
        "https://github.com/owner/repo/tree/..",
        "https://github.com/owner/repo/tree/feat%2f..%2fevil",
        "https://github.com/owner/repo/tree/feat/..%2f..",
    ],
)
def test_parse_github_repo_url_rejects(bad_url):
    with pytest.raises(TemplateInstallError):
        parse_github_repo_url(bad_url)


def test_sandbox_blocks_dunder_access(tmp_path):
    """Jinja 沙箱拦截模板内的 dunder 属性访问（SSTI 防护）。"""
    from unittest.mock import MagicMock

    from src.infrastructure.reporting.templates import HTMLTemplates

    custom_root = tmp_path / "custom"
    theme = custom_root / "gda_evil"
    theme.mkdir(parents=True)
    (theme / "image_template.html").write_text(
        "{{ ''.__class__.__mro__[1].__subclasses__() }}", encoding="utf-8"
    )
    mock = MagicMock()
    mock.get_custom_report_template_dir = MagicMock(
        side_effect=lambda n: (custom_root / n) if n else custom_root
    )
    mock.get_report_template = MagicMock(return_value="gda_evil")
    mgr = HTMLTemplates(mock)

    out = mgr.render_template("image_template.html", template_theme="gda_evil")
    # 沙箱拦截 → 渲染失败 → 返回空串；若沙箱失效则输出会包含 __subclasses__ 信息
    assert out == ""


def test_template_exists_rejects_path_traversal():
    """template_exists 拒绝路径穿越类模板名。"""
    import asyncio

    from src.application.commands.template_command_service import (
        TemplateCommandService,
    )

    service = TemplateCommandService(plugin_root=".")
    assert not asyncio.run(service.template_exists("../../etc"))
    assert not asyncio.run(service.template_exists(".."))
    assert not asyncio.run(service.template_exists("simple/.."))


def test_install_writes_marker(tmp_path):
    """安装后在模板目录写入 .tpl_installed.json 卸载标记。"""
    zip_data = build_zip(
        {"image_template.html": "<html></html>"},
        leading_root="MarkerTheme-main",
    )
    result = install_template_from_zip(
        zip_data, store_dir=tmp_path, source="url", source_url="https://github.com/x/y"
    )
    marker = tmp_path / result["name"] / ".tpl_installed.json"
    assert marker.is_file()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["source"] == "url"
    assert payload["source_url"] == "https://github.com/x/y"
    assert payload["installed_by"]


def test_uninstall_removes_installed_template(tmp_path):
    """卸载已安装（带标记）的模板：目录被删除并返回结果。"""
    zip_data = build_zip(
        {"image_template.html": "<html></html>", "topic_item.html": "<div></div>"}
    )
    install_template_from_zip(zip_data, store_dir=tmp_path, name="gda_mine")
    assert (tmp_path / "gda_mine").is_dir()

    result = uninstall_template("gda_mine", store_dir=tmp_path)
    assert result["removed"] is True
    assert result["name"] == "gda_mine"
    assert not (tmp_path / "gda_mine").exists()


def test_uninstall_rejects_builtin(tmp_path):
    """内置模板名（simple）不允许卸载。"""
    with pytest.raises(TemplateInstallError, match="内置模板"):
        uninstall_template("simple", store_dir=tmp_path)


def test_uninstall_rejects_unmanaged_dir(tmp_path):
    """手动放入数据目录（无安装标记）的模板不允许自动卸载。"""
    manual = tmp_path / "manual_theme"
    manual.mkdir()
    (manual / "image_template.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(TemplateInstallError, match="不是通过插件安装器"):
        uninstall_template("manual_theme", store_dir=tmp_path)
    # 目录未被删除
    assert manual.is_dir()


def test_uninstall_rejects_nonexistent(tmp_path):
    with pytest.raises(TemplateInstallError, match="不存在"):
        uninstall_template("gda_ghost", store_dir=tmp_path)


@pytest.mark.parametrize(
    "bad_name",
    ["", "../x", "a/b", "..", "name:bad", "a" * 51],
)
def test_uninstall_rejects_invalid_name(tmp_path, bad_name):
    with pytest.raises(TemplateInstallError):
        uninstall_template(bad_name, store_dir=tmp_path)


def test_uninstall_clears_only_marked(tmp_path):
    """批量场景：带标记模板被卸载后，无标记的兄弟目录保留。"""
    marked = tmp_path / "gda_keep"
    marked.mkdir()
    (marked / "image_template.html").write_text("<html></html>", encoding="utf-8")
    (marked / ".tpl_installed.json").write_text("{}", encoding="utf-8")
    manual = tmp_path / "manual_bro"
    manual.mkdir()
    (manual / "image_template.html").write_text("<html></html>", encoding="utf-8")

    uninstall_template("gda_keep", store_dir=tmp_path)
    assert not marked.exists()
    assert manual.is_dir()


def test_available_templates_meta_fields(tmp_path):
    """template.json 的 name/desc/tag/tag_color 透出到模板列表。"""
    from unittest.mock import MagicMock

    from src.infrastructure.reporting.templates import HTMLTemplates

    custom_root = tmp_path / "custom"
    theme = custom_root / "gda_meta"
    theme.mkdir(parents=True)
    (theme / "image_template.html").write_text("<html></html>", encoding="utf-8")
    (theme / "template.json").write_text(
        json.dumps(
            {
                "name": "樱雨日记",
                "desc": "樱花风格",
                "tag": "水彩樱花",
                "tag_color": "pink",
            }
        ),
        encoding="utf-8",
    )
    mock = MagicMock()
    mock.get_custom_report_template_dir = MagicMock(
        side_effect=lambda n: (custom_root / n) if n else custom_root
    )
    items = {t["id"]: t for t in HTMLTemplates(mock).get_available_templates()}
    meta = items["gda_meta"]
    assert meta["display_name"] == "樱雨日记"
    assert meta["desc"] == "樱花风格"
    assert meta["tag"] == "水彩樱花"
    assert meta["tag_color"] == "pink"


def test_list_available_templates_includes_custom(tmp_path, monkeypatch):
    """/查看模板 的可用列表包含自定义模板目录。"""
    from src.application.commands.template_command_service import (
        TemplateCommandService,
    )
    from src.infrastructure.reporting import template_installer

    custom_root = tmp_path / "custom"
    (custom_root / "gda_installed").mkdir(parents=True)
    (custom_root / "gda_installed" / "image_template.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    monkeypatch.setattr(
        template_installer, "default_template_store_dir", lambda: custom_root
    )

    service = TemplateCommandService(plugin_root=str(tmp_path))
    names = service.list_available_templates()
    assert "gda_installed" in names


def test_resolve_template_preview_path_prefers_template_dir(tmp_path, monkeypatch):
    """模板目录内预览图优先于插件仓库 assets 目录。"""
    from src.application.commands.template_command_service import (
        TemplateCommandService,
    )
    from src.infrastructure.reporting import template_installer

    custom_root = tmp_path / "custom"
    theme = custom_root / "gda_sky"
    theme.mkdir(parents=True)
    (theme / "preview.png").write_bytes(b"png")
    (theme / "image_template.html").write_text("<html></html>", encoding="utf-8")
    plugin_root = tmp_path / "plugin"
    (plugin_root / "assets").mkdir(parents=True)
    (plugin_root / "assets" / "gda_sky-demo.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(
        template_installer, "default_template_store_dir", lambda: custom_root
    )

    service = TemplateCommandService(plugin_root=str(plugin_root))
    resolved = service.resolve_template_preview_path("gda_sky")
    assert resolved is not None and resolved.endswith("preview.png")


def test_available_templates_can_uninstall_flag(tmp_path):
    """模板列表的 can_uninstall 仅对带安装标记的自定义目录为真。"""
    from unittest.mock import MagicMock

    from src.infrastructure.reporting.templates import HTMLTemplates

    custom_root = tmp_path / "custom"
    managed = custom_root / "gda_managed"
    unmanaged = custom_root / "manual_theme"
    modified_builtin = custom_root / "simple"  # 模拟内置模板的“自定义修改版”备份
    for dir_name in (managed, unmanaged, modified_builtin):
        dir_name.mkdir(parents=True)
        (dir_name / "image_template.html").write_text("<html></html>", encoding="utf-8")
    (managed / ".tpl_installed.json").write_text("{}", encoding="utf-8")
    # 未修改的内置拷贝：哈希与内置模板一致 → 不会被误判为自定义
    builtin_dir = Path(HTMLTemplates(MagicMock()).base_dir) / "simple"
    if (builtin_dir / "image_template.html").exists():
        (modified_builtin / "image_template.html").write_bytes(
            (builtin_dir / "image_template.html").read_bytes()
        )

    mock = MagicMock()
    mock.get_custom_report_template_dir = MagicMock(
        side_effect=lambda n: (custom_root / n) if n else custom_root
    )
    items = {t["id"]: t for t in HTMLTemplates(mock).get_available_templates()}

    assert items["gda_managed"]["can_uninstall"] is True
    assert items["manual_theme"]["can_uninstall"] is False
    # 内置模板不可卸载
    assert items["scrapbook"]["can_uninstall"] is False


def _make_theme_store(tmp_path):
    """创建带模板的 store 与指向外部的 symlink 模板目录（Windows 无权限时返回 None）。"""
    from unittest.mock import MagicMock

    from src.application.commands.template_command_service import (
        TemplateCommandService,
    )
    from src.infrastructure.reporting import template_installer
    from src.infrastructure.reporting.templates import HTMLTemplates

    store = tmp_path / "store"
    store.mkdir()
    (store / "gda_normal").mkdir()
    (store / "gda_normal" / "image_template.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "image_template.html").write_text("OUTSIDE_SENTINEL", encoding="utf-8")
    try:
        os.symlink(outside, store / "gda_link", target_is_directory=True)
    except (OSError, NotImplementedError):
        return None

    service = TemplateCommandService(plugin_root=str(tmp_path))
    mock = MagicMock()
    mock.get_custom_report_template_dir = MagicMock(
        side_effect=lambda n: (store / n) if n else store
    )
    return {
        "store": store,
        "service": service,
        "html_templates": HTMLTemplates(mock),
        "monkeypatch_target": template_installer,
    }


def test_symlink_template_dir_rejected_everywhere(tmp_path, monkeypatch):
    """符号链接模板目录在列表/校验/扫描/渲染四处均被拒绝（与卸载/预览侧防护一致）。"""
    ctx = _make_theme_store(tmp_path)
    if ctx is None:
        pytest.skip("当前平台不支持创建符号链接")

    monkeypatch.setattr(
        ctx["monkeypatch_target"], "default_template_store_dir", lambda: ctx["store"]
    )

    # 1) list_available_templates：正常目录在，symlink 目录不在
    names = ctx["service"].list_available_templates()
    assert "gda_normal" in names
    assert "gda_link" not in names

    # 2) template_exists：symlink 目录不被认定为有效模板
    assert asyncio.run(ctx["service"].template_exists("gda_link")) is False
    assert asyncio.run(ctx["service"].template_exists("gda_normal")) is True

    # 3) HTMLTemplates 扫描：symlink 目录不出现在画廊/下拉元信息中
    items = {t["id"]: t for t in ctx["html_templates"].get_available_templates()}
    assert "gda_normal" in items
    assert "gda_link" not in items

    # 4) 渲染 loader：symlink 目录被拒绝加载，抛出 FileNotFoundError，且 render_template 返回空
    with pytest.raises(FileNotFoundError, match="未找到指定的报告主题模板"):
        ctx["html_templates"]._get_env_sync("gda_link")
    assert (
        ctx["html_templates"].render_template(
            "image_template.html", template_theme="gda_link"
        )
        == ""
    )


def test_symlinked_template_file_rejected(tmp_path, monkeypatch):
    """目录内的主模板文件为符号链接时：列表/校验/渲染均拒绝（文件级 symlink）。"""
    from unittest.mock import MagicMock

    from src.application.commands.template_command_service import (
        TemplateCommandService,
    )
    from src.infrastructure.reporting import template_installer
    from src.infrastructure.reporting.templates import HTMLTemplates

    store = tmp_path / "store"
    store.mkdir()
    tpl = store / "gda_filelink"
    tpl.mkdir()
    (tpl / "image_template.html").write_text("<html></html>", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evil.html").write_text("FILE_SENTINEL", encoding="utf-8")
    try:
        os.symlink(outside / "evil.html", tpl / "html_template.html")
    except (OSError, NotImplementedError):
        pytest.skip("当前平台不支持创建符号链接")

    monkeypatch.setattr(template_installer, "default_template_store_dir", lambda: store)

    service = TemplateCommandService(plugin_root=str(tmp_path))
    # 列表排除 + template_exists 拒绝
    assert "gda_filelink" not in service.list_available_templates()
    assert asyncio.run(service.template_exists("gda_filelink")) is False

    # 渲染 loader 拒绝：含有 symlink 的模板目录被拒绝加载，抛出 FileNotFoundError，且 render_template 返回空
    mock = MagicMock()
    mock.get_custom_report_template_dir = MagicMock(
        side_effect=lambda n: (store / n) if n else store
    )
    with pytest.raises(FileNotFoundError, match="未找到指定的报告主题模板"):
        HTMLTemplates(mock)._get_env_sync("gda_filelink")
    assert (
        HTMLTemplates(mock).render_template(
            "html_template.html", template_theme="gda_filelink"
        )
        == ""
    )


def test_get_env_validates_template_name():
    """渲染入口对非法模板名与不存在模板抛出明确异常，不静默回退 scrapbook。"""
    from unittest.mock import MagicMock

    import pytest
    from src.infrastructure.reporting.template_installer import TemplateInstallError
    from src.infrastructure.reporting.templates import HTMLTemplates

    html_tpl = HTMLTemplates(MagicMock())
    # 非法路径穿越模板名抛出 TemplateInstallError
    with pytest.raises(TemplateInstallError):
        html_tpl._get_env_sync("../../evil")

    # 不存在的模板名抛出 FileNotFoundError
    with pytest.raises(FileNotFoundError, match="未找到指定的报告主题模板"):
        html_tpl._get_env_sync("non_existent_template_xyz")

    # render_template 优雅捕获异常并返回空字符串
    rendered = html_tpl.render_template(
        "image_template.html", template_theme="non_existent_template_xyz"
    )
    assert rendered == ""
