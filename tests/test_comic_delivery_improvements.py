"""覆盖漫画投递配置与 NapCat 兜底逻辑的回归测试。"""

import asyncio
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from test_comic_regressions import load_config_manager_class

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PNG_BYTES = b"\x89PNG\r\n\x1a\nplaceholder"


def _load_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(
        module_name, PLUGIN_ROOT / relative_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _load_drawing_client_class():
    """加载绘图客户端，并补齐独立测试所需的 AstrBot 类型替身。"""
    import astrbot.api
    from astrbot.api import star

    astrbot.api.AstrBotConfig = dict
    star.StarTools = SimpleNamespace(
        get_data_dir=lambda _plugin_name: PLUGIN_ROOT / "data"
    )
    module = _load_module(
        "src.infrastructure.drawing.drawing_client",
        "src/infrastructure/drawing/drawing_client.py",
    )
    return module.DrawingClient


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


def test_drawing_provider_schema_keeps_all_reference_presets():
    """绘图配置面板应保留参考插件中的全部供应商预设。"""
    schema = json.loads((PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    templates = schema["daily_comic"]["items"]["drawing_provider_overrides"][
        "templates"
    ]
    preset_keys = [
        "google",
        "openai",
        "zai",
        "grok2api",
        "agnes_ai",
        "agnes_ai_china",
        "xai",
        "minimax",
        "stepfun",
        "openai_images",
        "doubao",
        "sensenova",
        "dashscope",
    ]

    assert list(templates) == [*preset_keys, "custom"]
    for preset_key in preset_keys:
        items = templates[preset_key]["items"]
        assert {"priority", "api_key", "api_url", "model", "proxy", "timeout"} <= set(
            items
        )
    assert "drawing_proxy" in schema["daily_comic"]["items"]


def test_drawing_schema_has_a_single_provider_configuration_entry():
    """供应商连接和出图参数只应配置在供应商表条目中。

    这能防止配置面板重新显示旧的外层 API URL、模型、尺寸等字段，造成同一
    供应商参数有两处来源、实际优先级难以判断的问题。
    """
    schema = json.loads((PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    comic_items = schema["daily_comic"]["items"]

    assert {
        "drawing_api_url",
        "drawing_api_key",
        "drawing_model",
        "drawing_api_protocol",
        "drawing_image_size",
        "drawing_aspect_ratio",
        "drawing_image_quality",
        "drawing_background",
        "drawing_output_format",
        "drawing_timeout",
    }.isdisjoint(comic_items)


def test_drawing_provider_schema_exposes_advanced_preset_controls():
    """四个重点预设必须公开其实际支持的专属控制项。

    此断言防止仅在后端增加参数却遗漏配置面板，导致用户无法开启参考图截断、
    组图、尺寸和 GPT Image 的输出控制能力。
    """
    schema = json.loads((PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    templates = schema["daily_comic"]["items"]["drawing_provider_overrides"][
        "templates"
    ]

    assert {
        "quality",
        "background",
        "response_format",
        "output_compression",
        "moderation",
        "max_reference_images",
        "generations_only",
    } <= set(templates["openai_images"]["items"])
    assert {
        "endpoint_id",
        "model_capability",
        "size_mode",
        "size",
        "custom_size",
        "watermark",
        "optimize_prompt_mode",
        "sequential_image_generation",
        "sequential_max_images",
        "max_reference_images",
    } <= set(templates["doubao"]["items"])
    assert {"default_size", "n"} <= set(templates["sensenova"]["items"])
    assert {
        "max_reference_images",
        "size_mode",
        "custom_size",
        "n",
        "watermark",
        "negative_prompt",
        "prompt_extend",
        "thinking_mode",
        "enable_sequential",
    } <= set(templates["dashscope"]["items"])


def test_drawing_provider_presets_map_to_runtime_protocols(tmp_path):
    """预设模板保存后必须映射到对应的实际请求协议。"""
    config_manager_class = load_config_manager_class(tmp_path)
    manager = object.__new__(config_manager_class)
    expected_protocols = {
        "google": "google",
        "openai": "chat",
        "zai": "chat",
        "grok2api": "grok",
        "agnes_ai": "agnes_ai",
        "agnes_ai_china": "agnes_ai",
        "xai": "xai",
        "minimax": "minimax",
        "stepfun": "stepfun",
        "openai_images": "images",
        "doubao": "doubao",
        "sensenova": "sensenova",
        "dashscope": "dashscope",
    }
    manager.config = {
        "daily_comic": {
            "drawing_provider_overrides": [
                {"__template_key": key, "api_key": f"key-{index}"}
                for index, key in enumerate(expected_protocols)
            ]
        }
    }

    providers = manager.get_drawing_provider_configs()

    assert [provider["api_protocol"] for provider in providers] == list(
        expected_protocols.values()
    )


def test_drawing_client_requires_a_provider_entry():
    """供应商表为空时不应使用已移除的外层旧配置回退。"""

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        client = drawing_client_class(
            SimpleNamespace(get_drawing_provider_configs=lambda: [])
        )

        image, error = await client.generate_image("漫画提示词")

        assert image is None
        assert error == "未配置有效的漫画绘图供应商，请在绘图供应商配置表中添加条目。"

    asyncio.run(scenario())


def test_drawing_client_preserves_last_image_download_failure_after_fallbacks():
    """图片 URL 无法下载时应继续尝试候选，全部失败后保留可用链接。"""

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        drawing_module = sys.modules[drawing_client_class.__module__]
        download_error = drawing_module.ImageDownloadFailedError
        config_manager = SimpleNamespace(
            get_drawing_provider_configs=lambda: [
                {"name": "first"},
                {"name": "second"},
            ],
        )
        client = drawing_client_class(config_manager)
        client._generate_image_with_provider = AsyncMock(
            side_effect=[
                download_error(
                    "图片下载失败 [HTTP 403]",
                    fallback_url="https://image.example.com/generated.png",
                ),
                (None, "second provider failed"),
            ]
        )

        try:
            await client.generate_image("漫画提示词")
        except download_error as exc:
            assert exc.fallback_url == "https://image.example.com/generated.png"
        else:
            raise AssertionError("预期保留最后一个图片下载失败")

        assert client._generate_image_with_provider.await_count == 2

    asyncio.run(scenario())


def test_agnes_china_preset_uses_china_endpoint():
    """Agnes 中国站和国际站应作为独立预设，避免 API Key 跨站鉴权。"""
    schema = json.loads((PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    templates = schema["daily_comic"]["items"]["drawing_provider_overrides"][
        "templates"
    ]

    assert templates["agnes_ai"]["items"]["api_url"]["default"] == (
        "https://apihub.agnes-ai.com"
    )
    assert templates["agnes_ai_china"]["items"]["api_url"]["default"] == (
        "https://api.agnes-ai.cn"
    )


def test_google_and_preset_requests_use_the_expected_endpoints_and_payloads():
    """Google、MiniMax、豆包和 DashScope 预设应使用各自的官方请求格式。"""

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        client = drawing_client_class(SimpleNamespace())
        client._post_json_for_image = AsyncMock(return_value=PNG_BYTES)
        reference = [(b"reference", "image/png")]

        google_provider = {
            "api_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "google-key",
            "model": "gemini-3-pro-image-preview",
            "image_size": "2K",
            "aspect_ratio": "16:9",
            "timeout": 60,
        }
        assert await client._call_google_api("漫画提示词", reference, google_provider)
        google_call = client._post_json_for_image.await_args
        assert google_call.args[0].endswith(
            "/models/gemini-3-pro-image-preview:generateContent"
        )
        assert google_call.args[1]["x-goog-api-key"] == "google-key"
        google_payload = google_call.args[2]
        assert google_payload["generationConfig"]["imageConfig"] == {
            "image_size": "2K",
            "aspect_ratio": "16:9",
        }
        assert (
            google_payload["contents"][0]["parts"][1]["inlineData"]["mimeType"]
            == "image/png"
        )

        for provider_type, provider, expected_url, expected_field in [
            (
                "minimax",
                {
                    "api_url": "https://api.minimaxi.com",
                    "api_key": "minimax-key",
                    "model": "image-01",
                    "image_size": "2K",
                    "aspect_ratio": "16:9",
                    "timeout": 60,
                    "output_format": "png",
                },
                "/v1/image_generation",
                "subject_reference",
            ),
            (
                "doubao",
                {
                    "api_url": "https://ark.cn-beijing.volces.com",
                    "api_key": "doubao-key",
                    "model": "doubao-seedream-5-0",
                    "image_size": "2K",
                    "aspect_ratio": "16:9",
                    "timeout": 60,
                    "output_format": "png",
                    "endpoint_mode": "agent_plan",
                },
                "/api/plan/v3/images/generations",
                "image",
            ),
            (
                "dashscope",
                {
                    "api_url": "https://dashscope.aliyuncs.com",
                    "api_key": "dashscope-key",
                    "model": "qwen-image-2.0",
                    "image_size": "2K",
                    "aspect_ratio": "16:9",
                    "timeout": 60,
                    "output_format": "png",
                },
                "/api/v1/services/aigc/multimodal-generation/generation",
                "input",
            ),
        ]:
            client._post_json_for_image.reset_mock()
            assert await client._call_preset_api(
                "漫画提示词", reference, provider, provider_type
            )
            call = client._post_json_for_image.await_args
            assert call.args[0].endswith(expected_url)
            payload = call.args[2]
            assert expected_field in payload

        dashscope_payload = client._post_json_for_image.await_args.args[2]
        assert dashscope_payload["parameters"]["size"] == "2048*1152"
        assert dashscope_payload["input"]["messages"][0]["content"][1][
            "image"
        ].startswith("data:image/png;base64,")

    asyncio.run(scenario())


def test_stepfun_reference_image_uses_multipart_edits_request(monkeypatch):
    """阶跃星辰图生图应通过 edits 端点提交 multipart 的 image 字段。"""
    requests = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}]}

    class AsyncClient:
        def __init__(self, **kwargs):
            del kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            del args

        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    drawing_client_class = _load_drawing_client_class()
    drawing_client_module = sys.modules[drawing_client_class.__module__]
    monkeypatch.setattr(drawing_client_module.httpx, "AsyncClient", AsyncClient)
    drawing_client = drawing_client_class(SimpleNamespace())
    drawing_client._extract_image_from_response = AsyncMock(return_value=PNG_BYTES)
    provider = {
        "api_url": "https://api.stepfun.com",
        "api_key": "stepfun-key",
        "model": "step-image-edit-2",
        "image_size": "2K",
        "timeout": 60,
    }

    assert (
        asyncio.run(
            drawing_client._call_stepfun_api(
                "漫画提示词",
                [(b"reference", "image/png")],
                provider,
                "stepfun-key",
                "step-image-edit-2",
                60,
            )
        )
        == PNG_BYTES
    )

    url, request = requests[0]
    assert url == "https://api.stepfun.com/v1/images/edits"
    assert request["data"]["model"] == "step-image-edit-2"
    assert request["files"]["image"] == (
        "reference.png",
        b"reference",
        "image/png",
    )


def test_drawing_proxy_prefers_provider_and_is_reused_for_image_download(monkeypatch):
    """供应商代理应覆盖全局代理，并用于下载同次请求返回的图片。"""
    requests = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"data": [{"url": "https://image.example.com/comic.png"}]}

    class AsyncClient:
        def __init__(self, **kwargs):
            requests.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            del args

        async def post(self, *_args, **_kwargs):
            return Response()

    drawing_client_class = _load_drawing_client_class()
    drawing_client_module = sys.modules[drawing_client_class.__module__]
    monkeypatch.setattr(drawing_client_module.httpx, "AsyncClient", AsyncClient)
    config_manager = SimpleNamespace(
        get_drawing_proxy=lambda: "http://global-proxy:7890",
    )
    drawing_client = drawing_client_class(config_manager)
    drawing_client._extract_image_from_response = AsyncMock(return_value=PNG_BYTES)
    provider = {
        "api_url": "https://api.openai.com/v1",
        "api_key": "api-key",
        "model": "gpt-image-1",
        "image_size": "1024x1024",
        "aspect_ratio": "1:1",
        "output_format": "png",
        "image_quality": "auto",
        "background": "auto",
        "timeout": 60,
        "proxy": "socks5://provider-proxy:1080",
    }

    assert asyncio.run(drawing_client._call_images_api("漫画提示词", provider=provider))

    assert requests[0]["proxy"] == "socks5://provider-proxy:1080"
    drawing_client._extract_image_from_response.assert_awaited_once_with(
        {"data": [{"url": "https://image.example.com/comic.png"}]},
        "socks5://provider-proxy:1080",
    )
    assert drawing_client._get_request_proxy({}) == "http://global-proxy:7890"


def test_openai_images_request_applies_advanced_controls_and_reference_limit(
    monkeypatch,
):
    """OpenAI Images 的 JSON 和 multipart 请求应使用相同的关键控制参数。"""
    requests = []

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}]}

    class AsyncClient:
        def __init__(self, **kwargs):
            del kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            del args

        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        images_module = sys.modules["src.infrastructure.drawing.api_requests.images"]
        monkeypatch.setattr(images_module.httpx, "AsyncClient", AsyncClient)
        drawing_client = drawing_client_class(SimpleNamespace())
        provider = {
            "api_url": "https://api.openai.com/v1",
            "api_key": "api-key",
            "model": "gpt-image-1",
            "image_size": "1024x1024",
            "aspect_ratio": "1:1",
            "output_format": "webp",
            "quality": "auto",
            "background": "transparent",
            "response_format": "b64_json",
            "output_compression": 75,
            "moderation": "low",
            "max_reference_images": 2,
            "timeout": 60,
        }
        references = [
            (f"reference-{index}".encode(), "image/png") for index in range(3)
        ]

        assert await drawing_client._call_images_api("漫画提示词", provider=provider)
        generation_url, generation_request = requests[-1]
        assert generation_url.endswith("/images/generations")
        assert generation_request["json"] == {
            "prompt": "漫画提示词",
            "model": "gpt-image-1",
            "n": 1,
            "size": "1024x1024",
            "output_format": "webp",
            "quality": "auto",
            "background": "transparent",
            "response_format": "b64_json",
            "output_compression": 75,
            "moderation": "low",
        }

        assert await drawing_client._call_images_api("漫画提示词", references, provider)
        edits_url, edits_request = requests[-1]
        assert edits_url.endswith("/images/edits")
        assert len(edits_request["files"]) == 2
        assert edits_request["data"] == {
            "prompt": "漫画提示词",
            "model": "gpt-image-1",
            "n": "1",
            "size": "1024x1024",
            "output_format": "webp",
            "quality": "auto",
            "background": "transparent",
            "response_format": "b64_json",
            "output_compression": "75",
            "moderation": "low",
        }

        provider["generations_only"] = True
        assert await drawing_client._call_images_api("漫画提示词", references, provider)
        assert requests[-1][0].endswith("/images/generations")

    asyncio.run(scenario())


def test_preset_requests_apply_provider_specific_advanced_controls():
    """各原生供应商只发送其模型支持的专属字段，并正确限制数量。"""

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        drawing_client = drawing_client_class(SimpleNamespace())
        drawing_client._post_json_for_image = AsyncMock(return_value=PNG_BYTES)
        references = [
            (f"reference-{index}".encode(), "image/png") for index in range(15)
        ]

        doubao_provider = {
            "api_url": "https://ark.cn-beijing.volces.com",
            "api_key": "doubao-key",
            "model": "ignored-model",
            "endpoint_id": "ep-20260812",
            "image_size": "1K",
            "aspect_ratio": "4:3",
            "size_mode": "custom",
            "custom_size": "2304x1728",
            "output_format": "webp",
            "watermark": True,
            "optimize_prompt_mode": "fast",
            "sequential_image_generation": "auto",
            "sequential_max_images": 8,
            "max_reference_images": 12,
            "timeout": 60,
        }
        assert await drawing_client._call_preset_api(
            "漫画提示词", references, doubao_provider, "doubao"
        )
        doubao_payload = drawing_client._post_json_for_image.await_args.args[2]
        assert doubao_payload["model"] == "ep-20260812"
        assert doubao_payload["size"] == "2304x1728"
        assert doubao_payload["watermark"] is True
        assert len(doubao_payload["image"]) == 12
        assert doubao_payload["optimize_prompt_options"] == {"mode": "fast"}
        assert doubao_payload["sequential_image_generation"] == "auto"
        assert doubao_payload["sequential_image_generation_options"] == {
            "max_images": 8
        }

        drawing_client._post_json_for_image.reset_mock()
        doubao_provider.update(
            {
                "model_capability": "seedream_5_pro",
                "max_reference_images": 14,
            }
        )
        assert await drawing_client._call_preset_api(
            "漫画提示词", references, doubao_provider, "doubao"
        )
        seedream_payload = drawing_client._post_json_for_image.await_args.args[2]
        assert len(seedream_payload["image"]) == 10
        assert "sequential_image_generation" not in seedream_payload

        drawing_client._post_json_for_image.reset_mock()
        dashscope_provider = {
            "api_url": "https://dashscope.aliyuncs.com",
            "api_key": "dashscope-key",
            "model": "wan2.7-image-pro",
            "image_size": "2K",
            "aspect_ratio": "16:9",
            "output_format": "png",
            "size_mode": "custom",
            "custom_size": "1536x1024",
            "max_reference_images": 2,
            "n": 99,
            "watermark": True,
            "negative_prompt": "模糊",
            "thinking_mode": True,
            "enable_sequential": False,
            "timeout": 60,
        }
        assert await drawing_client._call_preset_api(
            "漫画提示词", references, dashscope_provider, "dashscope"
        )
        dashscope_payload = drawing_client._post_json_for_image.await_args.args[2]
        dashscope_parameters = dashscope_payload["parameters"]
        assert dashscope_parameters["size"] == "1536*1024"
        assert dashscope_parameters["n"] == 4
        assert dashscope_parameters["watermark"] is True
        assert dashscope_parameters["thinking_mode"] is True
        assert "negative_prompt" not in dashscope_parameters
        assert len(dashscope_payload["input"]["messages"][0]["content"]) == 3

        drawing_client._post_json_for_image.reset_mock()
        dashscope_provider["enable_sequential"] = True
        assert await drawing_client._call_preset_api(
            "漫画提示词", references, dashscope_provider, "dashscope"
        )
        sequential_parameters = drawing_client._post_json_for_image.await_args.args[2][
            "parameters"
        ]
        assert sequential_parameters["n"] == 12
        assert sequential_parameters["enable_sequential"] is True
        assert "thinking_mode" not in sequential_parameters

        drawing_client._post_json_for_image.reset_mock()
        qwen_provider = {
            **dashscope_provider,
            "model": "qwen-image-2.0-pro",
            "n": 10,
            "enable_sequential": False,
            "prompt_extend": True,
        }
        assert await drawing_client._call_preset_api(
            "漫画提示词", [], qwen_provider, "dashscope"
        )
        qwen_parameters = drawing_client._post_json_for_image.await_args.args[2][
            "parameters"
        ]
        assert qwen_parameters["n"] == 6
        assert qwen_parameters["negative_prompt"] == "模糊"
        assert qwen_parameters["prompt_extend"] is True

        drawing_client._post_json_for_image.reset_mock()
        sensenova_provider = {
            "api_url": "https://token.sensenova.cn",
            "api_key": "sensenova-key",
            "model": "sensenova-u1-fast",
            "image_size": "2K",
            "aspect_ratio": "9:21",
            "output_format": "png",
            "default_size": "2048x2048",
            "n": 9,
            "timeout": 60,
        }
        assert await drawing_client._call_preset_api(
            "漫画提示词", references, sensenova_provider, "sensenova"
        )
        sensenova_payload = drawing_client._post_json_for_image.await_args.args[2]
        assert sensenova_payload["size"] == "1344x3136"
        assert sensenova_payload["n"] == 4

        drawing_client._post_json_for_image.reset_mock()
        sensenova_provider["aspect_ratio"] = "invalid"
        assert await drawing_client._call_preset_api(
            "漫画提示词", None, sensenova_provider, "sensenova"
        )
        assert (
            drawing_client._post_json_for_image.await_args.args[2]["size"]
            == "2048x2048"
        )

    asyncio.run(scenario())


def test_image_url_download_uses_request_proxy_before_download_proxy():
    """生图响应的图片 URL 应优先使用生图请求的代理。"""

    async def scenario():
        drawing_client_class = _load_drawing_client_class()
        drawing_client = drawing_client_class(
            SimpleNamespace(get_drawing_download_proxy=lambda: "http://download:7890")
        )
        drawing_client.download_public_image = AsyncMock(return_value=PNG_BYTES)

        assert (
            await drawing_client._extract_image_from_response(
                {"data": [{"url": "https://image.example.com/comic.png"}]},
                "http://request-proxy:7890",
            )
            == PNG_BYTES
        )
        drawing_client.download_public_image.assert_awaited_once_with(
            "https://image.example.com/comic.png", "http://request-proxy:7890"
        )

    asyncio.run(scenario())


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


def test_validate_image_url_allows_localhost_and_private_urls():
    """本地自建或容器内的绘图服务（如 grok2api、SD 等）返回的 URL 应允许通过校验。"""
    drawing_image_response = _load_module(
        "src.infrastructure.drawing.drawing_image_response",
        "src/infrastructure/drawing/drawing_image_response.py",
    )
    handler = drawing_image_response.DrawingImageResponseService(
        hooks=SimpleNamespace(config_manager=SimpleNamespace(get_drawing_download_proxy=lambda: None)),
        download_image=AsyncMock(),
    )

    # 应该正常通过校验，不抛出异常
    asyncio.run(handler._validate_public_image_url("http://127.0.0.1:8000/v1/media/images/test.png"))
    asyncio.run(handler._validate_public_image_url("http://localhost:8000/images/test.jpg"))
    asyncio.run(handler._validate_public_image_url("http://192.168.1.100:7860/outputs/img.png"))
    asyncio.run(handler._validate_public_image_url("https://images.example.com/generated.png"))

    # 非法协议或包含凭据应被拒绝
    with pytest.raises(ValueError, match="HTTP/HTTPS"):
        asyncio.run(handler._validate_public_image_url("ftp://127.0.0.1/test.png"))
    with pytest.raises(ValueError, match="用户凭据"):
        asyncio.run(handler._validate_public_image_url("http://user:pass@127.0.0.1/test.png"))

