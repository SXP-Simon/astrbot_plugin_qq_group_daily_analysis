"""合并转发配置保存的类型边界和失败无副作用回归。"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "basic",
    [
        None,
        [],
        "invalid",
        True,
        0,
        {"enable_merged_forward": "false"},
        {"enable_merged_forward": "true"},
        {"enable_merged_forward": 0},
        {"enable_merged_forward": 1},
        {"enable_merged_forward": None},
        {"enable_merged_forward": []},
        {"merged_forward_timeout": True},
        {"merged_forward_timeout": False},
        {"merged_forward_timeout": "600"},
        {"merged_forward_timeout": 600.0},
        {"merged_forward_timeout": None},
        {"merged_forward_timeout": []},
        {"merged_forward_timeout": 9},
        {"merged_forward_timeout": 3601},
    ],
)
async def test_invalid_merge_settings_rejected_before_any_mutation(basic: object):
    """非法输入不写配置、不刷新定时任务，也不触发参考图清洗。"""
    original = {
        "basic": {"show_report_caption": False},
        "unrelated": {"keep": [" original "]},
    }
    manager = MagicMock(config=deepcopy(original))
    scheduler = MagicMock()
    scheduler.incremental_trigger.refresh_target_states = AsyncMock()
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    payload = {
        "basic": basic,
        "daily_comic": {
            "comic_characters": [{"reference_images": [" files/raw.png "]}]
        },
    }
    before_payload = deepcopy(payload)

    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": payload})
        response = await routes.api_save_config()

    status = (
        response.get("status_code", 200)
        if isinstance(response, dict)
        else response.status_code
    )
    assert status == 400
    assert manager.config == original
    assert payload == before_payload
    manager.save_config.assert_not_called()
    scheduler.schedule_jobs.assert_not_called()
    scheduler.incremental_trigger.refresh_target_states.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "update",
    [
        {},
        {"basic": {}},
        {"basic": {"show_report_caption": False}},
        {"basic": {"enable_merged_forward": True}},
        {"basic": {"enable_merged_forward": False}},
        {"basic": {"merged_forward_timeout": 10}},
        {"basic": {"merged_forward_timeout": 3600}},
        {"basic": {"enable_merged_forward": True, "merged_forward_timeout": 600}},
    ],
)
async def test_valid_and_legacy_merge_settings_preserve_save_flow(update: dict):
    """旧配置无需补新字段；有效输入及不相关字段原样通过既有保存流程。"""
    original = {"basic": {"show_report_caption": True}, "future": {"keep": [1]}}
    manager = MagicMock(config=deepcopy(original))
    scheduler = MagicMock()
    scheduler.incremental_trigger = None
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    before_update = deepcopy(update)

    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": update})
        response = await routes.api_save_config()

    status = (
        response.get("status_code", 200)
        if isinstance(response, dict)
        else response.status_code
    )
    assert status == 200
    assert manager.config == {**original, **before_update}
    assert update == before_update
    manager.save_config.assert_called_once()
    scheduler.schedule_jobs.assert_called_once()
