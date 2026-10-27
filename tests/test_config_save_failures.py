import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


class ConfigWithSave(dict):
    def __init__(self):
        super().__init__()
        self.save_config = MagicMock()


@pytest.fixture
def manager():
    instance = object.__new__(ConfigManager)
    instance.config = ConfigWithSave()
    return instance


@pytest.mark.parametrize(
    "error", [PermissionError("没有写入权限"), OSError("磁盘空间不足")]
)
def test_save_propagates_original_error_without_success_log(manager, error):
    manager.config.save_config.side_effect = error
    with (
        patch("src.infrastructure.config.config_manager.logger") as logger,
        pytest.raises(type(error)) as raised,
    ):
        manager.save_config()
    assert raised.value is error
    manager.config.save_config.assert_called_once_with()
    logger.info.assert_not_called()


def test_successful_save_still_delegates_to_astrbot(manager):
    with patch("src.infrastructure.config.config_manager.logger") as logger:
        manager.save_config()
    manager.config.save_config.assert_called_once_with()
    logger.error.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [PermissionError("没有写入权限"), OSError("磁盘空间不足")]
)
async def test_webui_returns_failure_and_skips_scheduler_when_write_fails(
    manager, error
):
    manager.config.save_config.side_effect = error
    scheduler = MagicMock()
    scheduler.incremental_trigger.refresh_target_states = AsyncMock()
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": {"basic": {"max_topics": 5}}})
        response = await routes.api_save_config()
    assert response["status_code"] == 500
    assert response["message"] == str(error)
    assert "持久化生效" not in str(response)
    scheduler.schedule_jobs.assert_not_called()
    scheduler.incremental_trigger.refresh_target_states.assert_not_awaited()


@pytest.mark.asyncio
async def test_webui_returns_success_and_refreshes_scheduler_after_write(manager):
    scheduler = MagicMock()
    scheduler.incremental_trigger.refresh_target_states = AsyncMock()
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": {"basic": {"max_topics": 5}}})
        response = await routes.api_save_config()
    assert response["status_code"] == 200
    assert response["data"]["status"] == "ok"
    assert manager.config["basic"]["max_topics"] == 5
    manager.config.save_config.assert_called_once_with()
    scheduler.schedule_jobs.assert_called_once_with(routes.context)
    scheduler.incremental_trigger.refresh_target_states.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_two_page_saves_reject_stale_snapshot_without_mutation(manager):
    manager.config.update({"basic": {"max_topics": 3}, "future": {"keep": True}})
    routes = ConfigRoutes(MagicMock(config_manager=manager))
    loaded = (await routes.api_get_config())["data"]["data"]
    revision = loaded["revision"]
    assert len(revision) == 64
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={"config": {"basic": {"max_topics": 5}}, "revision": revision}
        )
        first = await routes.api_save_config()
        saved_revision = first["data"]["revision"]
        assert saved_revision != revision
        request.json = AsyncMock(
            return_value={"config": {"basic": {"max_topics": 99}}, "revision": revision}
        )
        stale = await routes.api_save_config()
        assert stale["status_code"] == 409
        assert "重新读取" in stale["message"]
        assert manager.config["basic"]["max_topics"] == 5
        assert manager.config["future"] == {"keep": True}
        manager.config.save_config.assert_called_once()
        request.json = AsyncMock(
            return_value={
                "config": {"basic": {"max_topics": 6}},
                "revision": saved_revision,
            }
        )
        assert (await routes.api_save_config())["status_code"] == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("revision", [None, 1, "", "a" * 63, "z" * 64])
async def test_invalid_revision_does_not_change_config(manager, revision):
    routes = ConfigRoutes(MagicMock(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={"config": {"basic": {"max_topics": 9}}, "revision": revision}
        )
        assert (await routes.api_save_config())["status_code"] == 400
    assert manager.config == {}
    manager.config.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_default_projection_revision_matches_raw_config_and_detects_external_edits(
    manager,
):
    manager.config["t2i_rendering"] = {"t2i_rendering_strategies": []}
    routes = ConfigRoutes(MagicMock(config_manager=manager))
    loaded = (await routes.api_get_config())["data"]["data"]
    assert loaded["config"]["t2i_rendering"]["t2i_rendering_strategies"]
    assert manager.config["t2i_rendering"]["t2i_rendering_strategies"] == []
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={"config": loaded["config"], "revision": loaded["revision"]}
        )
        assert (await routes.api_save_config())["status_code"] == 200
        reloaded = (await routes.api_get_config())["data"]["data"]
        manager.config["basic"] = {"max_topics": 12}
        request.json = AsyncMock(
            return_value={
                "config": reloaded["config"],
                "revision": reloaded["revision"],
            }
        )
        assert (await routes.api_save_config())["status_code"] == 409
    assert manager.config["basic"]["max_topics"] == 12


@pytest.mark.asyncio
async def test_second_snapshot_is_rejected_while_first_save_refreshes_scheduler(
    manager,
):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def refresh():
        entered.set()
        await release.wait()

    scheduler = MagicMock()
    scheduler.incremental_trigger.refresh_target_states = AsyncMock(side_effect=refresh)
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    revision = (await routes.api_get_config())["data"]["data"]["revision"]
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            side_effect=[
                {"config": {"basic": {"max_topics": 5}}, "revision": revision},
                {"config": {"basic": {"max_topics": 9}}, "revision": revision},
            ]
        )
        first = asyncio.create_task(routes.api_save_config())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert (await routes.api_save_config())["status_code"] == 409
            assert manager.config["basic"]["max_topics"] == 5
            manager.config.save_config.assert_called_once()
        finally:
            release.set()
            result = await asyncio.wait_for(first, 1)
    assert result["data"]["revision"] != revision
    scheduler.incremental_trigger.refresh_target_states.assert_awaited_once()
