"""真实缓存预览、字体维护与只读边界的回归测试。"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import UploadFile

from src.domain.value_objects.wordcloud import (
    WordCloudData,
    WordFrequency,
)
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.persistence.wordcloud_store import WordCloudStore
from src.infrastructure.reporting.wordcloud_renderer import WordCloudRenderer
from src.infrastructure.webui.routes import wordcloud_routes
from src.infrastructure.webui.routes.wordcloud_routes import WordCloudRoutes


def manager(config=None):
    """构造无宿主副作用的配置读取器。"""
    result = object.__new__(ConfigManager)
    result.config = config or {}
    return result


def body(monkeypatch, payload):
    """仅替换当前测试请求，不修改配置对象。"""
    monkeypatch.setattr(
        wordcloud_routes,
        "request",
        SimpleNamespace(json=AsyncMock(return_value=payload)),
    )


def statistics(group="123"):
    """完整统计包含可被门槛、排除词和展示上限独立筛选的词。"""
    return WordCloudData(
        frequencies=(
            WordFrequency("高性能", 20, 9),
            WordFrequency("亚托莉", 8, 6),
            WordFrequency("排除词", 8, 4),
            WordFrequency("少", 1, 1),
        ),
        message_count=40,
        group_id=group,
        platform_id="bot",
        date_str="2026-10-17",
        start_timestamp=1792195200,
        end_timestamp=1792281600,
    )


def uploaded(tmp_path):
    """建立具有真实摘要标识的最小测试字体。"""
    content = b"wOF2" + bytes(60)
    name = hashlib.sha256(content).hexdigest() + ".woff2"
    directory = tmp_path / "wordcloud_fonts"
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    path.with_suffix(".woff2.label").write_text("原字体", encoding="utf-8")
    return "uploaded:" + name, path


def test_snapshot_list_is_latest_per_group_and_read_only(tmp_path):
    store = WordCloudStore(tmp_path / "wordcloud.db")
    store.save("bot:GroupMessage:123", "old", statistics(), "sent")
    store.save("bot:GroupMessage:123", "new", statistics(), "failed")
    store.save("bot:GroupMessage:456", "other", statistics("456"), "sent")
    before = store.path.read_bytes()
    snapshots = store.list_snapshots()
    assert {item.umo for item in snapshots} == {
        "bot:GroupMessage:123",
        "bot:GroupMessage:456",
    }
    assert len(snapshots) == 2
    for snapshot in snapshots:
        assert store.get_snapshot(snapshot.id) == snapshot
    assert store.path.read_bytes() == before


def test_snapshot_rejects_replaced_expired_invalid_or_corrupt_cache(tmp_path):
    store = WordCloudStore(tmp_path / "wordcloud.db")
    store.save("bot:GroupMessage:123", "same", statistics(), "sent")
    snapshot = store.list_snapshots()[0]
    store.save("bot:GroupMessage:123", "same", statistics("changed"), "failed")
    assert store.get_snapshot(snapshot.id) is None
    with pytest.raises(ValueError, match="标识无效"):
        store.get_snapshot("../../wordcloud.db")
    with pytest.raises(ValueError, match="标识无效"):
        store.get_snapshot("ffffffffffffffff.0123456789abcdef")
    snapshot = store.list_snapshots()[0]
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE wordcloud_delivery SET updated_at=?", (time.time() - 31 * 86400,)
        )
    assert store.list_snapshots() == []
    assert store.get_snapshot(snapshot.id) is None
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE wordcloud_delivery SET updated_at=?,data_json='[]'", (time.time(),)
        )
    assert store.list_snapshots() == []


@pytest.mark.asyncio
async def test_snapshot_preview_reuses_cache_and_reports_filtering_without_mutation(
    tmp_path, monkeypatch
):
    config = manager({"wordcloud": {"font": "sans"}})
    renderer = WordCloudRenderer(config, tmp_path)
    seen = []

    def render(data, options, umo):
        seen.append((data, options, umo))
        return "<html>缓存词云</html>"

    monkeypatch.setattr(renderer, "build_html", render)
    store = WordCloudStore(tmp_path / "wordcloud.db")
    store.save("bot:GroupMessage:123", "data", statistics(), "sent")
    route = WordCloudRoutes(renderer, store)
    snapshot = store.list_snapshots()[0]
    before_db = store.path.read_bytes()
    before_config = json.dumps(config.config)
    body(
        monkeypatch,
        {
            "source": "snapshot",
            "snapshot_id": snapshot.id,
            "mode": "html",
            "options": {"stopwords": ["排除词"], "max_words": 1},
        },
    )
    result = await route.api_preview()
    assert result["status_code"] == 200
    metadata = result["data"]["data"]["metadata"]
    assert metadata["word_count"] == 4
    assert metadata["eligible_word_count"] == 2
    assert metadata["display_word_count"] == 1
    assert metadata["message_count"] == 40
    assert metadata["snapshot_id"] == snapshot.id
    assert metadata["umo"] == "bot:GroupMessage:123"
    assert metadata["notes"]
    assert seen[0][0] == statistics()
    assert seen[0][2] == "bot:GroupMessage:123"
    assert store.path.read_bytes() == before_db
    assert json.dumps(config.config) == before_config


@pytest.mark.asyncio
async def test_preview_rejects_stale_snapshot_or_scope_mismatch(tmp_path, monkeypatch):
    store = WordCloudStore(tmp_path / "wordcloud.db")
    store.save("bot:GroupMessage:123", "data", statistics(), "sent")
    snapshot = store.list_snapshots()[0]
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path), store)
    body(
        monkeypatch,
        {
            "source": "snapshot",
            "snapshot_id": snapshot.id,
            "umo": "bot:GroupMessage:456",
        },
    )
    assert (await route.api_preview())["status_code"] == 400
    body(monkeypatch, {"source": "snapshot", "snapshot_id": "0.0123456789abcdef"})
    assert (await route.api_preview())["status_code"] == 404
    body(monkeypatch, {"source": "snapshot"})
    assert (await route.api_preview())["status_code"] == 400


@pytest.mark.asyncio
async def test_corrected_draft_previews_before_invalid_saved_value_is_changed(
    tmp_path, monkeypatch
):
    config = manager(
        {"wordcloud": {"min_font_size": 170, "max_words": 17, "font": "sans"}}
    )
    renderer = WordCloudRenderer(config, tmp_path)
    received = []

    def render(_data, options, _umo):
        received.append(options)
        return "<html>草稿</html>"

    monkeypatch.setattr(renderer, "build_html", render)
    body(monkeypatch, {"options": {"min_font_size": 28}, "mode": "html"})
    response = await WordCloudRoutes(renderer).api_preview()
    assert response["status_code"] == 200
    assert received[0].min_font_size == 28
    assert received[0].max_words == 17
    assert config.config["wordcloud"]["min_font_size"] == 170


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["global", "group", "snapshot"])
async def test_corrected_override_draft_previews_without_modifying_saved_config(
    tmp_path, monkeypatch, scope
):
    config = manager({"wordcloud": {"group_overrides": "旧的无效值", "font": "sans"}})
    renderer = WordCloudRenderer(config, tmp_path)
    received = []

    def render(_data, options, umo):
        received.append((options, umo))
        return "<html>修正后的覆盖草稿</html>"

    monkeypatch.setattr(renderer, "build_html", render)
    store = WordCloudStore(tmp_path / "wordcloud.db")
    store.save("bot:GroupMessage:123", "data", statistics(), "sent")
    snapshot = store.list_snapshots()[0]
    payload = {"options": {"group_overrides": {}}, "mode": "html"}
    if scope == "group":
        payload["umo"] = "bot:GroupMessage:123"
    elif scope == "snapshot":
        payload.update(source="snapshot", snapshot_id=snapshot.id)
    before_config = json.dumps(config.config)
    before_cache = store.path.read_bytes()
    body(monkeypatch, payload)
    response = await WordCloudRoutes(renderer, store).api_preview()
    assert response["status_code"] == 200
    assert received[0][0].font == "sans"
    assert received[0][1] == ("" if scope == "global" else "bot:GroupMessage:123")
    assert json.dumps(config.config) == before_config
    assert store.path.read_bytes() == before_cache


@pytest.mark.asyncio
async def test_group_preview_uses_corrected_draft_override_before_saved_override(
    tmp_path, monkeypatch
):
    umo = "bot:GroupMessage:123"
    config = manager(
        {"wordcloud": {"group_overrides": {umo: "无效群设置"}, "font": "sans"}}
    )
    renderer = WordCloudRenderer(config, tmp_path)
    received = []

    def render(_data, options, _umo):
        received.append(options)
        return "<html>本群覆盖草稿</html>"

    monkeypatch.setattr(renderer, "build_html", render)
    body(
        monkeypatch,
        {"umo": umo, "options": {"group_overrides": {umo: {"word_spacing": 3}}}},
    )
    response = await WordCloudRoutes(renderer).api_preview()
    assert response["status_code"] == 200
    assert received[0].word_spacing == 3
    assert config.config["wordcloud"]["group_overrides"][umo] == "无效群设置"


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [{}, {"group_overrides": []}])
async def test_unrepaired_invalid_overrides_keep_clear_validation_error(
    tmp_path, monkeypatch, draft
):
    config = manager({"wordcloud": {"group_overrides": "无效值"}})
    route = WordCloudRoutes(WordCloudRenderer(config, tmp_path))
    body(monkeypatch, {"options": draft})
    response = await route.api_preview()
    assert response["status_code"] == 400
    assert "词云群级覆盖必须是对象" in str(response)
    assert config.config["wordcloud"]["group_overrides"] == "无效值"


@pytest.mark.asyncio
async def test_catalog_contains_template_defaults_and_uploaded_labels(tmp_path):
    font_id, _ = uploaded(tmp_path)
    config = manager({"wordcloud": {"word_spacing": 27, "font": font_id}})
    renderer = WordCloudRenderer(config, tmp_path)
    response = await WordCloudRoutes(renderer).api_templates()
    catalog = response["data"]["data"]
    atri = next(item for item in catalog["templates"] if item["name"] == "ATRI")
    assert atri["defaults"]["word_spacing"] == 10
    assert atri["defaults"]["font"] == "wenkai"
    assert {"id": font_id, "label": "原字体", "uploaded": True} in catalog["fonts"]
    assert catalog["fonts"][0]["uploaded"] is False


@pytest.mark.asyncio
async def test_font_sample_is_embedded_and_rejects_traversal(tmp_path, monkeypatch):
    font_id, _ = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"font": font_id})
    response = await route.api_font_preview()
    html = response["data"]["data"]["html"]
    assert "data:font/woff2;base64," in html
    assert "document.fonts.ready" in html
    assert 'src="http' not in html
    body(monkeypatch, {"font": "uploaded:../../secret.woff2"})
    assert (await route.api_font_preview())["status_code"] == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["global", "group"])
async def test_delete_rejects_global_and_group_references(
    tmp_path, monkeypatch, reference
):
    font_id, path = uploaded(tmp_path)
    config = (
        {"font": font_id}
        if reference == "global"
        else {"group_overrides": {"bot:GroupMessage:123": {"font": font_id}}}
    )
    route = WordCloudRoutes(WordCloudRenderer(manager({"wordcloud": config}), tmp_path))
    body(monkeypatch, {"id": font_id})
    assert (await route.api_delete_font())["status_code"] == 409
    assert path.exists()
    assert not (path.parent / "trash").exists()


@pytest.mark.asyncio
async def test_delete_archives_font_and_restore_preserves_identity_and_label(
    tmp_path, monkeypatch
):
    font_id, path = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"id": font_id, "label": "我的字体"})
    assert (await route.api_rename_font())["status_code"] == 200
    assert (await route.api_delete_font())["status_code"] == 200
    assert not path.exists()
    assert not path.with_suffix(".woff2.label").exists()
    archived = list((path.parent / "trash").glob("*/" + path.name))
    assert len(archived) == 1
    assert (await route.api_restore_font())["data"]["data"]["label"] == "我的字体"
    assert path.exists()
    assert path.with_suffix(".woff2.label").read_text(encoding="utf-8") == "我的字体"
    assert (await route.api_restore_font())["status_code"] == 409


@pytest.mark.asyncio
async def test_delete_rolls_back_if_label_move_fails(tmp_path, monkeypatch):
    font_id, path = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    original = Path.rename

    def fail_label(source, target):
        if source == path.with_suffix(".woff2.label"):
            raise OSError("模拟标签移动失败")
        return original(source, target)

    monkeypatch.setattr(Path, "rename", fail_label)
    body(monkeypatch, {"id": font_id})
    assert (await route.api_delete_font())["status_code"] == 500
    assert path.exists()
    assert path.with_suffix(".woff2.label").exists()


@pytest.mark.asyncio
async def test_restore_rejects_tampered_archive_without_creating_active_font(
    tmp_path, monkeypatch
):
    font_id, path = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"id": font_id})
    assert (await route.api_delete_font())["status_code"] == 200
    archived = next((path.parent / "trash").glob("*/" + path.name))
    archived.write_bytes(b"changed-font")
    assert (await route.api_restore_font())["status_code"] == 409
    assert not path.exists()
    assert archived.read_bytes() == b"changed-font"


@pytest.mark.asyncio
async def test_font_symlink_is_neither_listed_nor_modified(tmp_path, monkeypatch):
    font_id, path = uploaded(tmp_path)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda item: item == path or original(item))
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    catalog = (await route.api_templates())["data"]["data"]
    assert not any(font["id"] == font_id for font in catalog["fonts"])
    body(monkeypatch, {"id": font_id, "label": "changed", "font": font_id})
    for action in (
        route.api_rename_font,
        route.api_delete_font,
        route.api_restore_font,
        route.api_font_preview,
    ):
        assert (await action())["status_code"] == 400
    assert path.exists()


@pytest.mark.asyncio
async def test_duplicate_upload_preserves_renamed_label(tmp_path, monkeypatch):
    font_id, path = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"id": font_id, "label": "用户自定义名称"})
    assert (await route.api_rename_font())["status_code"] == 200
    upload = UploadFile(io.BytesIO(path.read_bytes()), filename="another.woff2")
    monkeypatch.setattr(
        wordcloud_routes,
        "request",
        SimpleNamespace(uploaded_files=AsyncMock(return_value={"file": upload})),
    )
    result = await route.api_upload_font()
    assert result["data"]["data"]["label"] == "用户自定义名称"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "font_id",
    ["sans", "uploaded:../file.woff2", ["wenkai"], "uploaded:" + "a" * 65 + ".woff2"],
)
async def test_font_mutation_rejects_builtin_invalid_and_traversal_ids(
    tmp_path, monkeypatch, font_id
):
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"id": font_id, "label": "name"})
    for action in (
        route.api_rename_font,
        route.api_delete_font,
        route.api_restore_font,
    ):
        assert (await action())["status_code"] == 400
    assert not (tmp_path / "wordcloud_fonts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("label", ["", " ", "a" * 121, "bad\nlabel", 42])
async def test_rename_rejects_invalid_labels_without_mutation(
    tmp_path, monkeypatch, label
):
    font_id, path = uploaded(tmp_path)
    route = WordCloudRoutes(WordCloudRenderer(manager(), tmp_path))
    body(monkeypatch, {"id": font_id, "label": label})
    assert (await route.api_rename_font())["status_code"] == 400
    assert path.with_suffix(".woff2.label").read_text(encoding="utf-8") == "原字体"
