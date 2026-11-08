import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.webui.routes.config_routes import ConfigRoutes

CASES = json.loads(
    (Path(__file__).parent / "fixtures/config_validation_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [case for case in CASES if not case["valid"]], ids=lambda case: case["name"])
async def test_rejected_config_never_mutates_runtime_or_persists(case):
    manager = SimpleNamespace(config={"existing": {"keep": True}}, save_config=Mock())
    scheduler = Mock()
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager), auto_scheduler=scheduler)
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": copy.deepcopy(case["config"])})
        response = await routes.api_save_config()
    assert response["status_code"] == 400
    assert manager.config == {"existing": {"keep": True}}
    manager.save_config.assert_not_called()
    scheduler.schedule_jobs.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], None, "wrong", {"config": {"basic": []}}, {"config": {"basic": None}}])
async def test_invalid_request_and_group_shape_return_client_error(payload):
    manager = SimpleNamespace(config={}, save_config=Mock())
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value=payload)
        response = await ConfigRoutes(SimpleNamespace(config_manager=manager)).api_save_config()
    assert response["status_code"] == 400
    assert manager.config == {}
    manager.save_config.assert_not_called()


