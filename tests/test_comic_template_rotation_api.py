"""漫画模板轮换状态接口与配置保存边界回归。"""

from __future__ import annotations

import asyncio
import json
import threading
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.webui import web_compat
from src.infrastructure.webui.openapi_spec import generate_openapi_spec
from src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge
from src.infrastructure.webui.routes import config_routes, template_routes
from src.infrastructure.webui.routes.config_routes import ConfigRoutes
from src.infrastructure.webui.routes.template_routes import TemplateRoutes
from src.shared import trace_context
from src.shared.comic_prompts import COMIC_STORYBOARD_PROMPTS
from src.shared.constants import PLUGIN_NAME


@pytest.fixture(autouse=True)
def local_transport(monkeypatch: pytest.MonkeyPatch):
    """隔离宿主传输层，直接检查实际响应包装。"""
    monkeypatch.setattr(web_compat, "_real_json_response", None)
    monkeypatch.setattr(web_compat, "_real_error_response", None)


def rotation_status() -> dict[str, object]:
    """提供包含明确空值语义的状态快照。"""
    return {
        "mode": "sequential",
        "scope": "group",
        "scope_key": "group:bot:GroupMessage:123",
        "candidates": ["classic", "pixel_rpg"],
        "current_template_id": "classic",
        "current_template_name": "原版漫画",
        "next_template_id": "pixel_rpg",
        "next_template_name": "像素 RPG 每日冒险日志",
        "date": "2026-10-17",
        "initialized": True,
        "warning": None,
    }


@pytest.mark.asyncio
async def test_status_is_read_only_off_loop_and_preserves_bridge_payload(monkeypatch):
    """查询只调用状态读取，不触发选择；宿主解包后完整保留状态。"""
    manager = MagicMock()
    expected = rotation_status()
    caller_thread = threading.get_ident()
    worker_threads: list[int] = []

    def read_status(*, group_id, umo):
        worker_threads.append(threading.get_ident())
        assert (group_id, umo) == ("123", "bot:GroupMessage:123")
        return expected

    manager.get_comic_template_rotation_status.side_effect = read_status
    monkeypatch.setattr(
        template_routes,
        "request",
        MagicMock(query={"group_id": "123", "umo": "bot:GroupMessage:123"}),
    )
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_get_comic_template_rotation_status()
    assert response["status_code"] == 200
    assert response["data"] == {"status": "ok", "data": expected}
    assert response["data"].get("data", response["data"]) == expected
    manager.reset_comic_template_rotation.assert_not_called()
    manager.select_comic_template.assert_not_called()
    assert worker_threads and caller_thread not in worker_threads


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"action": "reset"},
        {"action": "reset", "group_id": "123", "umo": "bot:GroupMessage:123"},
    ],
)
async def test_reset_only_delegates_selected_scope(payload, monkeypatch):
    """重置仅传递用户明确选择的范围，不提供全量清空入口。"""
    manager = MagicMock()
    manager.reset_comic_template_rotation.return_value = rotation_status()
    monkeypatch.setattr(
        template_routes, "request", MagicMock(json=AsyncMock(return_value=payload))
    )
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_reset_comic_template_rotation()
    assert response["status_code"] == 200
    manager.reset_comic_template_rotation.assert_called_once_with(
        group_id=payload.get("group_id", ""), umo=payload.get("umo")
    )


@pytest.mark.asyncio
async def test_reset_missing_group_context_reports_value_error(monkeypatch):
    """群独立模式缺少完整会话时，错误不会转成成功回执。"""
    manager = MagicMock()
    manager.reset_comic_template_rotation.side_effect = ValueError("请先选择完整群会话")
    monkeypatch.setattr(
        template_routes,
        "request",
        MagicMock(json=AsyncMock(return_value={"action": "reset"})),
    )
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_reset_comic_template_rotation()
    assert response["status_code"] == 400
    assert response["message"] == "请先选择完整群会话"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        {},
        {"action": "wrong"},
        {"action": "reset", "group_id": 123},
        {"action": "reset", "umo": []},
        {"action": "reset", "umo": "x" * 513},
    ],
)
async def test_reset_rejects_invalid_input_before_mutation(payload, monkeypatch):
    manager = MagicMock()
    monkeypatch.setattr(
        template_routes, "request", MagicMock(json=AsyncMock(return_value=payload))
    )
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_reset_comic_template_rotation()
    assert response["status_code"] == 400
    manager.reset_comic_template_rotation.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_payload", [[], None])
async def test_host_proxy_normalized_bad_body_cannot_reset_global(
    raw_payload, monkeypatch
):
    """宿主将非法请求体归一成空对象后，明确操作校验仍阻止重置。"""
    manager = MagicMock()
    target = MagicMock(json=AsyncMock(return_value=raw_payload), body=None, _body=None)
    proxy = web_compat._RequestProxy()
    monkeypatch.setattr(proxy, "_get_target", lambda: target)
    monkeypatch.setattr(template_routes, "request", proxy)
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_reset_comic_template_rotation()
    assert response["status_code"] == 400
    manager.reset_comic_template_rotation.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", [{"group_id": 123}, {"umo": []}, {"group_id": "x" * 129}]
)
async def test_status_rejects_invalid_query(query, monkeypatch):
    manager = MagicMock()
    monkeypatch.setattr(template_routes, "request", MagicMock(query=query))
    response = await TemplateRoutes(
        MagicMock(config_manager=manager)
    ).api_get_comic_template_rotation_status()
    assert response["status_code"] == 400
    manager.get_comic_template_rotation_status.assert_not_called()


@pytest.mark.asyncio
async def test_status_reports_unavailable_manager(monkeypatch):
    monkeypatch.setattr(template_routes, "request", MagicMock(query={}))
    response = await TemplateRoutes(None).api_get_comic_template_rotation_status()
    assert response["status_code"] == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "daily,prompts",
    [
        ({"comic_template_mode": "typo"}, {}),
        ({"comic_template_scope": "all"}, {}),
        ({"comic_template_candidates": ["classic", "classic"]}, {}),
        ({"comic_template_candidates": ["unknown"]}, {}),
        ({"comic_template_candidates": "classic"}, {}),
        ({"comic_template_candidates": [True]}, {}),
        ({"comic_template_mode": "random", "comic_template_candidates": []}, {}),
        (
            {"comic_template_mode": "shuffle", "comic_template_candidates": ["custom"]},
            {"comic_analysis_prompts": {"comic_storyboard_prompt": "  "}},
        ),
    ],
)
async def test_invalid_rotation_config_never_mutates_or_saves(
    daily, prompts, monkeypatch
):
    before = {"basic": {"enabled": True}}
    manager = MagicMock(config=deepcopy(before))
    monkeypatch.setattr(
        config_routes,
        "request",
        MagicMock(
            json=AsyncMock(
                return_value={"config": {"daily_comic": daily, "prompts": prompts}}
            )
        ),
    )
    response = await ConfigRoutes(MagicMock(config_manager=manager)).api_save_config()
    assert response["status_code"] == 400
    assert manager.config == before
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [
        {"basic": {"enabled": True}},
        {"daily_comic": {"comic_characters": []}},
        {
            "daily_comic": {
                "comic_template_mode": "fixed",
                "comic_template_candidates": [],
            }
        },
        {
            "daily_comic": {
                "comic_template_mode": "fixed",
                "comic_template_candidates": ["custom"],
            }
        },
        {"daily_comic": {"comic_template_mode": "daily_random"}},
        {
            "daily_comic": {
                "comic_template_mode": "shuffle",
                "comic_template_candidates": ["custom", "classic"],
            },
            "prompts": {
                "comic_analysis_prompts": {"comic_storyboard_prompt": "自定义内容"}
            },
        },
    ],
)
async def test_legacy_fixed_and_valid_rotation_config_can_save(config, monkeypatch):
    manager = MagicMock(config={})
    monkeypatch.setattr(
        config_routes,
        "request",
        MagicMock(json=AsyncMock(return_value={"config": config})),
    )
    response = await ConfigRoutes(MagicMock(config_manager=manager)).api_save_config()
    assert response["status_code"] == 200
    manager.save_config.assert_called_once()


@pytest.mark.asyncio
async def test_partial_prompt_save_checks_existing_active_custom_candidate(monkeypatch):
    manager = MagicMock(
        config={
            "daily_comic": {
                "comic_template_mode": "random",
                "comic_template_candidates": ["custom"],
            },
            "prompts": {
                "comic_analysis_prompts": {"comic_storyboard_prompt": "仍在使用"}
            },
        }
    )
    before = deepcopy(manager.config)
    monkeypatch.setattr(
        config_routes,
        "request",
        MagicMock(
            json=AsyncMock(
                return_value={
                    "config": {
                        "prompts": {
                            "comic_analysis_prompts": {"comic_storyboard_prompt": ""}
                        }
                    }
                }
            )
        ),
    )
    response = await ConfigRoutes(MagicMock(config_manager=manager)).api_save_config()
    assert response["status_code"] == 400
    assert manager.config == before
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_saves_validate_custom_prompt_after_acquiring_lock(
    monkeypatch,
):
    """较早保存清空提示词后，后续候选池保存须按最新配置校验。"""
    manager = MagicMock(
        config={
            "daily_comic": {
                "comic_template_mode": "fixed",
                "comic_template_candidates": ["custom"],
            },
            "prompts": {
                "comic_analysis_prompts": {"comic_storyboard_prompt": "原有提示词"}
            },
        }
    )
    entered = threading.Event()
    release = threading.Event()

    def hold_validation(_config):
        entered.set()
        assert release.wait(5), "测试未及时释放配置保存线程"

    renderer = MagicMock()
    renderer.validate_config_resources.side_effect = hold_validation
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), wordcloud_renderer=renderer
    )
    request = MagicMock(
        json=AsyncMock(
            side_effect=[
                {
                    "config": {
                        "wordcloud": {},
                        "prompts": {
                            "comic_analysis_prompts": {"comic_storyboard_prompt": ""}
                        },
                    }
                },
                {
                    "config": {
                        "daily_comic": {
                            "comic_template_mode": "random",
                            "comic_template_candidates": ["custom"],
                        }
                    }
                },
            ]
        )
    )
    monkeypatch.setattr(config_routes, "request", request)
    first = asyncio.create_task(routes.api_save_config())
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        second = asyncio.create_task(routes.api_save_config())
        await asyncio.sleep(0)
        assert not second.done()
    finally:
        release.set()
    assert second is not None
    first_response, second_response = await asyncio.gather(first, second)
    assert first_response["status_code"] == 200
    assert second_response["status_code"] == 400
    assert manager.config["daily_comic"]["comic_template_mode"] == "fixed"
    assert (
        manager.config["prompts"]["comic_analysis_prompts"]["comic_storyboard_prompt"]
        == ""
    )
    manager.save_config.assert_called_once()


def test_rotation_schema_preserves_order_and_explicit_custom():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    daily = schema["daily_comic"]["items"]
    assert daily["comic_template_mode"]["default"] == "fixed"
    assert daily["comic_template_scope"]["default"] == "global"
    candidates = daily["comic_template_candidates"]
    assert candidates["default"] == list(COMIC_STORYBOARD_PROMPTS)
    assert candidates["options"] == [*COMIC_STORYBOARD_PROMPTS, "custom"]
    assert len(candidates["labels"]) == len(candidates["options"])


def test_rotation_routes_and_openapi_contract(monkeypatch):
    monkeypatch.setattr(trace_context, "_global_active_task_manager", None)
    bridge = PluginPageWebUIBridge(MagicMock(), MagicMock(), MagicMock())
    from src.infrastructure.logging.plugin_log_buffer import global_log_buffer

    monkeypatch.setattr(global_log_buffer, "register_listener", lambda _listener: None)
    bridge.register_routes()
    registration = {
        call.args[0]: call.args
        for call in bridge.context.register_web_api.call_args_list
    }
    for path, method, handler in [
        (
            "status",
            "GET",
            bridge.template_routes.api_get_comic_template_rotation_status,
        ),
        ("reset", "POST", bridge.template_routes.api_reset_comic_template_rotation),
    ]:
        registered = registration[f"/{PLUGIN_NAME}/comic/templates/rotation/{path}"]
        assert registered[1:3] == (handler, [method])
        operation = generate_openapi_spec()["paths"][
            f"/comic/templates/rotation/{path}"
        ][method.lower()]
        assert "400" in operation["responses"]
        assert "503" in operation["responses"]
        assert operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ComicTemplateRotationResponse"}


@pytest.mark.asyncio
async def test_rotation_bridge_forwarders():
    bridge = object.__new__(PluginPageWebUIBridge)
    bridge.template_routes = MagicMock()
    expected = {"status": "ok", "data": rotation_status()}
    bridge.template_routes.api_get_comic_template_rotation_status = AsyncMock(
        return_value=expected
    )
    bridge.template_routes.api_reset_comic_template_rotation = AsyncMock(
        return_value=expected
    )
    assert await bridge.api_get_comic_template_rotation_status() == expected
    assert await bridge.api_reset_comic_template_rotation() == expected
