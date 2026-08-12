"""覆盖漫画投递配置与 NapCat 兜底逻辑的回归测试。"""

import asyncio
import base64
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_comic_regressions import load_config_manager_class

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name, PLUGIN_ROOT / relative_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_drawing_providers_are_sorted_and_skip_invalid_entries(tmp_path):
    config_manager_class = load_config_manager_class(tmp_path)
    manager = object.__new__(config_manager_class)
    manager.config = {
        "daily_comic": {
            "drawing_provider_overrides": [
                {"name": "fallback", "api_key": "key-1", "priority": 1},
                {"name": "invalid", "api_protocol": "unknown", "api_key": "key-2"},
                {
                    "name": "primary",
                    "api_protocol": "gemini",
                    "api_key": "key-3",
                    "priority": 10,
                },
            ]
        }
    }

    providers = manager.get_drawing_provider_configs()

    assert [provider["name"] for provider in providers] == ["primary", "fallback"]


def test_multiple_character_references_are_preserved(tmp_path):
    config_manager_class = load_config_manager_class(tmp_path)
    manager = object.__new__(config_manager_class)
    manager.config = {
        "daily_comic": {
            "comic_characters": [
                {
                    "enable": True,
                    "reference_images": ["first.png", "", "second.webp"],
                }
            ]
        }
    }

    assert manager.get_drawing_reference_images() == ["first.png", "second.webp"]
    assert manager.get_drawing_reference_image() == "second.webp"


def test_napcat_stream_upload_uses_current_onebot_connection(tmp_path):
    napcat_stream = _load_module(
        "src.infrastructure.platform.napcat_stream",
        "src/infrastructure/platform/napcat_stream.py",
    )
    image_path = tmp_path / "comic.png"
    image_path.write_bytes(b"a" * 10)
    calls = []

    async def call_action(action, **params):
        calls.append((action, params))
        if params.get("is_complete"):
            return {"status": "ok", "data": {"file_path": "/tmp/comic.png"}}
        return {"status": "ok", "data": {}}

    result = asyncio.run(
        napcat_stream.upload_file_stream(
            SimpleNamespace(call_action=AsyncMock(side_effect=call_action)), image_path
        )
    )

    assert result == "/tmp/comic.png"
    assert len(calls) == 2
    chunk = calls[0][1]
    assert base64.b64decode(chunk["chunk_data"]) == b"a" * 10
    assert chunk["expected_sha256"] == hashlib.sha256(b"a" * 10).hexdigest()
