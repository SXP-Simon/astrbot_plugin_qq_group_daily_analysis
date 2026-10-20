"""配置保存回执经过宿主 Page Bridge 解包后的契约回归。"""

import json
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
async def test_save_receipt_survives_host_bridge_unwrap():
    """保存完成后，宿主转发的 data 仍携带成功状态和实际保存值。"""
    manager = MagicMock(config={})
    config = {
        "prompts": {
            "comic_analysis_prompts": {"comic_storyboard_template": "noir_detective"}
        },
        "daily_comic": {"comic_characters": [{"storyboard_prompt": ""}]},
    }
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": config})
        response = await ConfigRoutes(
            MagicMock(config_manager=manager)
        ).api_save_config()

    body = response["data"] if isinstance(response, dict) else json.loads(response.body)
    manager.save_config.assert_called_once()
    assert body["status"] == "ok"
    # 对齐宿主 response.data?.data ?? response.data 的转发规则。
    receipt = body["data"]
    assert receipt["status"] == "ok"
    assert receipt["message"] == "配置已成功保存并持久化生效"
    assert receipt["config"] == manager.config
    assert receipt["config"]["daily_comic"]["comic_characters"][0] == {
        "__template_key": "character",
        "storyboard_prompt": "",
    }


@pytest.mark.asyncio
async def test_save_error_rolls_back_real_manager_and_allows_retry(tmp_path):
    """真实管理器透传写盘失败，恢复内存和磁盘状态，重试成功后才刷新调度。"""
    path = tmp_path / "config.json"

    class StoredConfig(dict):
        fail = False

        def save_config(self):
            """模拟宿主在提交文件前发生写盘异常。"""
            if self.fail:
                raise OSError("配置文件写入失败")
            path.write_text(json.dumps(self), encoding="utf-8")

    config = StoredConfig({"basic": {"enabled": True}, "other": {"keep": [1, 2]}})
    config.save_config()
    before = deepcopy(dict(config))
    config.fail = True
    manager = object.__new__(ConfigManager)
    manager.config = config
    scheduler = MagicMock()
    scheduler.incremental_trigger.refresh_target_states = AsyncMock()
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    updated = {"basic": {"enabled": False}, "new_group": {"value": "新增内容"}}
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": updated})
        response = await routes.api_save_config()

    if isinstance(response, dict):
        assert response["status_code"] == 500
        assert response["message"] == "配置文件写入失败"
    else:
        assert response.status_code == 500
        assert json.loads(response.body)["status"] == "error"
    assert manager.config is config
    assert dict(config) == before
    assert json.loads(path.read_text(encoding="utf-8")) == before
    scheduler.schedule_jobs.assert_not_called()
    scheduler.incremental_trigger.refresh_target_states.assert_not_awaited()

    config.fail = False
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": updated})
        response = await routes.api_save_config()
    body = response["data"] if isinstance(response, dict) else json.loads(response.body)
    assert body["data"]["status"] == "ok"
    assert dict(config) == {**before, **updated}
    assert json.loads(path.read_text(encoding="utf-8")) == dict(config)
    scheduler.schedule_jobs.assert_called_once()
    scheduler.incremental_trigger.refresh_target_states.assert_awaited_once()
