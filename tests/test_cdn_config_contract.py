import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui.routes.config_routes import ConfigRoutes
from src.shared.constants import DEFAULT_CDN_HOST
from src.utils.cdn_utils import normalize_cdn_base_url

CASES = json.loads(
    (Path(__file__).parent / "fixtures/cdn_url_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES)
def test_shared_cdn_contract_and_runtime_fallback(case):
    value, expected = case["input"], case["normalized"]
    if expected:
        assert normalize_cdn_base_url(value) == expected
    elif isinstance(value, str):
        with pytest.raises(ValueError):
            normalize_cdn_base_url(value)
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_cdn_base_url": value}}
    assert manager.get_t2i_cdn_base_url() == (expected or DEFAULT_CDN_HOST)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES)
async def test_save_rejects_invalid_cdn_before_any_mutation(case):
    manager = MagicMock()
    original = {"t2i_rendering": {"t2i_cdn_base_url": "https://old.example"}}
    manager.config = deepcopy(original)
    scheduler = MagicMock()
    scheduler.incremental_trigger = None
    routes = ConfigRoutes(
        MagicMock(config_manager=manager), context=MagicMock(), auto_scheduler=scheduler
    )
    config = {
        "t2i_rendering": {"t2i_cdn_base_url": case["input"], "future": [" unchanged "]},
        "future_group": {"list": [{"id": 1}, " files/unrelated.png ", "", None]},
    }
    expected_config = deepcopy(config)
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": config})
        response = await routes.api_save_config()
    status = response.get("status_code", 200) if isinstance(response, dict) else response.status_code
    if case["normalized"] is None:
        assert status == 400
        assert manager.config == original
        manager.save_config.assert_not_called()
        scheduler.schedule_jobs.assert_not_called()
    else:
        assert status == 200
        expected_config["t2i_rendering"]["t2i_cdn_base_url"] = case["normalized"]
        assert manager.config == expected_config
        manager.save_config.assert_called_once()
        scheduler.schedule_jobs.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("group", [None, [], "invalid", {"t2i_cdn_base_url": " " * 2049}])
async def test_save_rejects_invalid_rendering_group(group):
    manager = MagicMock(config={})
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": {"t2i_rendering": group}})
        response = await ConfigRoutes(MagicMock(config_manager=manager)).api_save_config()
    status = response["status_code"] if isinstance(response, dict) else response.status_code
    assert status == 400
    manager.save_config.assert_not_called()
    assert manager.config == {}


@pytest.mark.asyncio
async def test_reference_image_cleanup_stays_scoped_to_comic_characters():
    manager = MagicMock(config={})
    config = {
        "daily_comic": {
            "comic_characters": [{
                "name": "角色", "reference_images": ["files/old/image.png"],
                "future": [" files/keep.png ", {"key": 1}],
            }],
        },
    }
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": config})
        await ConfigRoutes(MagicMock(config_manager=manager)).api_save_config()
    character = manager.config["daily_comic"]["comic_characters"][0]
    assert character["__template_key"] == "character"
    assert character["reference_images"] == [
        "files/daily_comic/comic_characters/templates/character/reference_images/image.png"
    ]
    assert character["future"] == [" files/keep.png ", {"key": 1}]
