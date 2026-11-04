"""文件分区的路径边界、逐项操作及并发覆盖保护。"""

import pytest

from src.infrastructure.persistence.managed_files import ManagedFiles


def test_template_file_lifecycle_preserves_revision(tmp_path):
    store = ManagedFiles(tmp_path)
    store.mutate("custom_templates", "demo/report.typ", "create", payload=b"Hello")
    first = store.read("custom_templates", "demo/report.typ")
    assert first["text"] == "Hello"
    store.mutate(
        "custom_templates", "demo/report.typ", "replace", first["revision"], b"World"
    )
    with pytest.raises(FileExistsError):
        store.mutate("custom_templates", "demo/report.typ", "delete", first["revision"])
    second = store.read("custom_templates", "demo/report.typ")
    store.mutate(
        "custom_templates",
        "demo/report.typ",
        "rename",
        second["revision"],
        new_name="demo/main.typ",
    )
    assert store.files("custom_templates")[0]["name"] == "demo/main.typ"
    store.mutate("custom_templates", "demo/main.typ", "delete", second["revision"])
    assert not store.files("custom_templates")


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "/tmp/file",
        "a\\b",
        "C:/data",
        "a/../b",
        "a/.part",
        "NUL.txt",
        "a/foo.",
        "a:stream",
        "",
    ],
)
def test_rejects_platform_paths(tmp_path, name):
    with pytest.raises(ValueError):
        ManagedFiles(tmp_path).path("custom_templates", name)


def test_symlink_escape_and_readonly_partitions(tmp_path):
    store = ManagedFiles(tmp_path)
    root = tmp_path / "custom_t2i_templates/reporting_templates"
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前用户无法创建符号链接")
    assert not store.files("custom_templates")
    with pytest.raises(ValueError):
        store.read("custom_templates", "linked/secret.txt")
    for key in ("state", "avatar_storage", "typst_jobs"):
        with pytest.raises(ValueError):
            store.mutate(key, "x.txt", "delete", "revision")


def test_upload_validation_and_failed_replace_keeps_original(tmp_path):
    store = ManagedFiles(tmp_path)
    with pytest.raises(ValueError):
        store.mutate("template_resources", "unknown.png", "create", payload=b"bad")
    with pytest.raises(ValueError):
        store.mutate("typst_fonts", "fake.ttf", "create", payload=b"<html>error</html>")
    with pytest.raises(ValueError):
        store.mutate("config_files", "reference.png", "create", payload=b"bad")
    store.mutate("custom_templates", "demo/info.json", "create", payload=b"{}")
    original = store.read("custom_templates", "demo/info.json")
    with pytest.raises(ValueError):
        store.mutate(
            "custom_templates",
            "demo/info.json",
            "replace",
            original["revision"],
            b"{broken",
        )
    assert store.read("custom_templates", "demo/info.json") == original


def test_partition_totals_and_reports_do_not_touch_host_temp(tmp_path):
    (tmp_path / "typst/fonts").mkdir(parents=True)
    (tmp_path / "typst/fonts/font.ttf").write_bytes(b"font")
    (tmp_path / "traces.db").write_bytes(b"database")
    overview = ManagedFiles(tmp_path).overview()
    assert sum(item["size_bytes"] for item in overview) == 12
    assert next(item for item in overview if item["key"] == "typst_fonts")["count"] == 1
    assert not any("io_temp_img" in item["directory"] for item in overview)


def test_list_revision_allows_deletion_without_loading_file_content(
    tmp_path, monkeypatch
):
    store = ManagedFiles(tmp_path)
    directory = tmp_path / "reports"
    directory.mkdir()
    report = directory / "report.html"
    report.write_text("first")
    selected = store.files("reports")[0]
    report.write_text("updated content")
    with pytest.raises(FileExistsError):
        store.mutate("reports", selected["name"], "delete", selected["revision"])
    selected = store.files("reports")[0]
    monkeypatch.setattr(
        store, "read", lambda *_: pytest.fail("删除不应读取或 Base64 编码整份报告")
    )
    store.mutate("reports", selected["name"], "delete", selected["revision"])
    assert not report.exists()
