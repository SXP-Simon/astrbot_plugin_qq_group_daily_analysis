"""宿主模型配置只读展示与运行时配置解析的一致性回归。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from astrbot.api.provider import Provider

from src.infrastructure.analysis.utils.llm_utils import _get_host_fallback_provider_ids
from src.infrastructure.webui.routes import config_routes
from src.infrastructure.webui.routes.config_routes import ConfigRoutes
from src.infrastructure.webui.openapi_spec import generate_openapi_spec


@pytest.fixture
def context():
    providers = {}
    for pid in ["primary", "backup"]:
        providers[pid] = Mock(
            spec=Provider,
            provider_config={"id": pid, "name": f"模型 {pid}", "model": "model", "key": ["secret-key"], "api_base": "https://private.example"},
            get_model=Mock(return_value="model"),
            meta=Mock(return_value=SimpleNamespace(id=pid)),
        )
    return SimpleNamespace(
        get_config=Mock(),
        get_current_chat_provider_id=AsyncMock(return_value="primary"),
        get_using_provider_async=AsyncMock(return_value=providers["primary"]),
        get_all_providers=Mock(return_value=list(providers.values())),
        get_provider_by_id=Mock(side_effect=providers.get),
        save_config=Mock(),
        llm_generate=AsyncMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema", ["legacy", "runner", "agent"])
async def test_readonly_configuration_matches_runtime_without_secrets(context, monkeypatch, schema):
    ids = ["backup", "primary", "backup", "removed"]
    config = {"provider_settings": {"fallback_chat_models": ids}}
    if schema != "legacy":
        config = {"agent" if schema == "agent" else "agent_runner": {"config": {"model": {"fallback_provider_ids": ids}}}}
    before = deepcopy(config)
    context.get_config.return_value = config
    monkeypatch.setattr(config_routes, "request", SimpleNamespace(query={}))
    response = await ConfigRoutes(None, context=context).api_get_host_llm_config()
    assert response["status_code"] == 200
    data = response["data"]["data"]
    assert data["primary_id"] == "primary"
    assert data["fallback_ids"] == ["backup", "primary", "removed"]
    assert data["providers"][-1] == {"id": "removed", "name": "removed", "model": "", "available": False}
    assert _get_host_fallback_provider_ids(context, None) == ["backup", "primary"]
    assert "secret-key" not in str(response) and "private.example" not in str(response)
    assert config == before
    context.save_config.assert_not_called()
    context.llm_generate.assert_not_awaited()
    context.get_using_provider_async.assert_awaited_once_with(umo=None)


@pytest.mark.asyncio
async def test_group_scope_distinguishes_instances_and_respects_empty_current_list(context, monkeypatch):
    profiles = {
        "bot-a:GroupMessage:123": {"agent": {"config": {"model": {"fallback_provider_ids": ["backup"]}}}},
        "bot-b:GroupMessage:123": {"agent": {"config": {"model": {"fallback_provider_ids": []}}}, "provider_settings": {"fallback_chat_models": ["backup"]}},
    }
    context.get_config.side_effect = lambda umo: profiles[umo]
    context.get_using_provider_async.side_effect = lambda umo: context.get_provider_by_id("primary" if umo.startswith("bot-a:") else "backup")
    results = []
    for platform in ["bot-a", "bot-b"]:
        monkeypatch.setattr(config_routes, "request", SimpleNamespace(query={"platform_id": platform, "group_id": "123"}))
        response = await ConfigRoutes(None, context=context).api_get_host_llm_config()
        results.append(response["data"]["data"])
    assert [item["primary_id"] for item in results] == ["primary", "backup"]
    assert [item["fallback_ids"] for item in results] == [["backup"], []]
    assert context.get_using_provider_async.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [{"group_id": "123"}, {"platform_id": "bot-a"}, {"platform_id": "bot-a", "group_id": "bad\n123"}])
async def test_invalid_scope_does_not_read_default_config(context, monkeypatch, query):
    monkeypatch.setattr(config_routes, "request", SimpleNamespace(query=query))
    response = await ConfigRoutes(None, context=context).api_get_host_llm_config()
    assert response["status_code"] == 400
    context.get_config.assert_not_called()


@pytest.mark.asyncio
async def test_host_read_error_does_not_leak_private_details(context, monkeypatch):
    monkeypatch.setattr(config_routes, "request", SimpleNamespace(query={}))
    context.get_config.side_effect = RuntimeError("secret-key private.example")
    response = await ConfigRoutes(None, context=context).api_get_host_llm_config()
    assert response["status_code"] == 503
    assert "secret-key" not in str(response) and "private.example" not in str(response)
    context.llm_generate.assert_not_awaited()


def test_host_config_contract_is_get_only():
    assert set(generate_openapi_spec()["paths"]["/config/host-llm"]) == {"get"}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unrelated_meta", "primary_meta", "backup_model", "backup_lookup"])
async def test_broken_provider_does_not_hide_other_host_models(context, monkeypatch, failure):
    monkeypatch.setattr(config_routes, "request", SimpleNamespace(query={}))
    context.get_config.return_value = {"provider_settings": {"fallback_chat_models": ["backup"]}}
    primary, backup = context.get_all_providers.return_value
    error = RuntimeError("secret-key private.example")
    if failure == "unrelated_meta":
        broken = Mock(spec=Provider, meta=Mock(side_effect=error))
        context.get_all_providers.return_value = [broken, primary, backup]
    elif failure == "primary_meta":
        primary.meta.side_effect = error
    elif failure == "backup_model":
        backup.get_model.side_effect = error
    else:
        def lookup(pid):
            if pid == "backup":
                raise error
            return primary if pid == "primary" else None
        context.get_provider_by_id.side_effect = lookup

    response = await ConfigRoutes(None, context=context).api_get_host_llm_config()
    assert response["status_code"] == 200
    data = response["data"]["data"]
    assert data["fallback_ids"] == ["backup"]
    by_id = {provider["id"]: provider for provider in data["providers"]}
    if failure == "primary_meta":
        assert data["primary_id"] is None
        assert by_id["backup"]["available"] is True
    else:
        assert data["primary_id"] == "primary"
        assert by_id["primary"]["available"] is True
        assert by_id["backup"]["available"] is (failure == "unrelated_meta")
    assert "secret-key" not in str(response) and "private.example" not in str(response)
    context.save_config.assert_not_called()
    context.llm_generate.assert_not_awaited()
