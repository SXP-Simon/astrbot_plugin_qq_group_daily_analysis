"""词云配置保存的资源引用完整性与字体删除互斥回归。"""

import asyncio
import hashlib
import json
import threading
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from astrbot.api.star import StarTools

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.wordcloud_renderer import WordCloudRenderer
from src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge
from src.infrastructure.webui.routes import config_routes, wordcloud_routes
from src.infrastructure.webui.routes.config_routes import ConfigRoutes
from src.infrastructure.webui.routes.wordcloud_routes import WordCloudRoutes


def resource_fixture(tmp_path, monkeypatch):
    """构造生产渲染器与共享资源锁，避免调用宿主 T2I。"""
    manager = object.__new__(ConfigManager)
    manager.config = {"wordcloud": {"font": "sans"}}
    manager.save_config = MagicMock()
    monkeypatch.setattr(StarTools, "get_data_dir", lambda _name="": tmp_path)
    renderer = WordCloudRenderer(manager, tmp_path)
    lock = asyncio.Lock()
    routes = ConfigRoutes(
        SimpleNamespace(config_manager=manager),
        wordcloud_renderer=renderer,
        resource_lock=lock,
    )
    return manager, renderer, routes, lock


def propose(monkeypatch, config):
    """设置当前测试保存请求，保持其他路由请求彼此独立。"""
    monkeypatch.setattr(
        config_routes,
        "request",
        SimpleNamespace(json=AsyncMock(return_value={"config": config})),
    )


def create_font(tmp_path):
    """创建与正式文件标识相同的本地字体资源。"""
    content = b"wOF2" + bytes(60)
    name = hashlib.sha256(content).hexdigest() + ".woff2"
    path = tmp_path / "wordcloud_fonts" / name
    path.parent.mkdir()
    path.write_bytes(content)
    return "uploaded:" + name, path


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["global", "group"])
@pytest.mark.parametrize(
    "invalid_reference",
    [
        {"template": "HatsuneMiku"},
        {"font": "uploaded:" + "a" * 64 + ".woff2"},
    ],
)
async def test_save_rejects_unavailable_resource_before_mutating_config(
    tmp_path, monkeypatch, scope, invalid_reference
):
    manager = object.__new__(ConfigManager)
    manager.config = {"wordcloud": {"font": "sans"}, "other": {"value": "原值"}}
    manager.save_config = MagicMock()
    monkeypatch.setattr(StarTools, "get_data_dir", lambda _name="": tmp_path)
    proposed = (
        invalid_reference
        if scope == "global"
        else {"group_overrides": {"bot:GroupMessage:123": invalid_reference}}
    )
    original = deepcopy(manager.config)
    monkeypatch.setattr(
        config_routes,
        "request",
        SimpleNamespace(
            json=AsyncMock(
                return_value={
                    "config": {"wordcloud": proposed, "other": {"value": "不应写入"}}
                }
            )
        ),
    )
    response = await ConfigRoutes(
        SimpleNamespace(config_manager=manager)
    ).api_save_config()
    assert response["status_code"] == 400
    assert manager.config == original
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_save_accepts_custom_template_defaults_and_valid_group_inheritance(
    tmp_path, monkeypatch
):
    manager, renderer, routes, _ = resource_fixture(tmp_path, monkeypatch)
    font_id, _ = create_font(tmp_path)
    custom = tmp_path / "custom_t2i_templates" / "reporting_templates" / "Custom"
    custom.mkdir(parents=True)
    (custom / "wordcloud_template.html").write_text("自定义词云", encoding="utf-8")
    (custom / "wordcloud_defaults.json").write_text(
        json.dumps({"font": font_id, "min_font_size": 110, "max_font_size": 140}),
        encoding="utf-8",
    )
    config = {
        "wordcloud": {
            "template": "Custom",
            "group_overrides": {
                "bot:GroupMessage:123": {"min_font_size": 120},
                "bot:GroupMessage:456": {"template": "ATRI", "font": "sans"},
            },
        }
    }
    propose(monkeypatch, config)
    assert (await routes.api_save_config())["status_code"] == 200
    assert manager.config == config
    assert routes.wordcloud_renderer is renderer
    assert manager.get_wordcloud_options("bot:GroupMessage:123").font == font_id
    assert manager.get_wordcloud_options("bot:GroupMessage:123").max_font_size == 140
    assert manager.get_wordcloud_options("bot:GroupMessage:456").font == "sans"
    manager.save_config.assert_called_once()


@pytest.mark.asyncio
async def test_save_checks_missing_font_in_custom_template_defaults(
    tmp_path, monkeypatch
):
    manager, _, routes, _ = resource_fixture(tmp_path, monkeypatch)
    custom = tmp_path / "custom_t2i_templates" / "reporting_templates" / "Custom"
    custom.mkdir(parents=True)
    (custom / "wordcloud_template.html").write_text("自定义词云", encoding="utf-8")
    (custom / "wordcloud_defaults.json").write_text(
        json.dumps({"font": "uploaded:" + "a" * 64 + ".woff2"}),
        encoding="utf-8",
    )
    propose(monkeypatch, {"wordcloud": {"template": "Custom"}})
    assert (await routes.api_save_config())["status_code"] == 400
    assert manager.config == {"wordcloud": {"font": "sans"}}
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_save_checks_effective_group_numeric_values(tmp_path, monkeypatch):
    manager, _, routes, _ = resource_fixture(tmp_path, monkeypatch)
    propose(
        monkeypatch,
        {
            "wordcloud": {
                "font": "sans",
                "max_font_size": 100,
                "group_overrides": {"bot:GroupMessage:123": {"min_font_size": 120}},
            }
        },
    )
    response = await routes.api_save_config()
    assert response["status_code"] == 400
    assert "bot:GroupMessage:123" in str(response)
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_old_tab_cannot_save_font_after_another_tab_deleted_it(
    tmp_path, monkeypatch
):
    manager, renderer, routes, lock = resource_fixture(tmp_path, monkeypatch)
    font_id, font = create_font(tmp_path)
    fonts = WordCloudRoutes(renderer, resource_lock=lock)
    monkeypatch.setattr(
        wordcloud_routes,
        "request",
        SimpleNamespace(json=AsyncMock(return_value={"id": font_id})),
    )
    assert (await fonts.api_delete_font())["status_code"] == 200
    assert not font.exists()
    propose(monkeypatch, {"wordcloud": {"font": font_id}})
    assert (await routes.api_save_config())["status_code"] == 400
    assert manager.config == {"wordcloud": {"font": "sans"}}
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_font_delete_waits_until_resource_check_and_config_save_finish(
    tmp_path, monkeypatch
):
    manager, renderer, routes, lock = resource_fixture(tmp_path, monkeypatch)
    font_id, font = create_font(tmp_path)
    fonts = WordCloudRoutes(renderer, resource_lock=lock)
    validated = threading.Event()
    release = threading.Event()
    original = renderer.validate_config_resources

    def pause_after_validation(config):
        original(config)
        validated.set()
        assert release.wait(5), "测试未及时释放校验线程"

    monkeypatch.setattr(renderer, "validate_config_resources", pause_after_validation)
    propose(monkeypatch, {"wordcloud": {"font": font_id}})
    monkeypatch.setattr(
        wordcloud_routes,
        "request",
        SimpleNamespace(json=AsyncMock(return_value={"id": font_id})),
    )
    saving = asyncio.create_task(routes.api_save_config())
    try:
        assert await asyncio.to_thread(validated.wait, 2)
        deleting = asyncio.create_task(fonts.api_delete_font())
        await asyncio.sleep(0)
        assert lock.locked()
        assert not deleting.done()
        assert font.exists()
    finally:
        release.set()
    saved, deleted = await asyncio.gather(saving, deleting)
    assert saved["status_code"] == 200
    assert deleted["status_code"] == 409
    assert font.exists()
    assert manager.config["wordcloud"]["font"] == font_id
    manager.save_config.assert_called_once()


def test_production_bridge_shares_renderer_and_font_resource_lock(
    tmp_path, monkeypatch
):
    manager, renderer, _, _ = resource_fixture(tmp_path, monkeypatch)
    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=MagicMock(),
        active_task_manager=MagicMock(),
        analysis_service=SimpleNamespace(config_manager=manager),
        wordcloud_renderer=renderer,
    )
    assert bridge.config_routes.wordcloud_renderer is renderer
    assert bridge.wordcloud_routes.renderer is renderer
    assert (
        bridge.config_routes._wordcloud_resource_lock
        is bridge.wordcloud_routes._font_lock
    )
