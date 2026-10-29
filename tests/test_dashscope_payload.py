"""DashScope 各模型的张数和提示词能力回归。"""

from types import SimpleNamespace

import pytest

from src.infrastructure.drawing.api_requests.context import DrawingRequestContext
from src.infrastructure.drawing.api_requests.dashscope import build_dashscope_payload


@pytest.mark.parametrize(
    "model,sequential,limit",
    [("wan2.7-image", False, 4), ("wan2.7-image", True, 12), ("qwen-image-2.0-pro", False, 6), ("older-model", False, 1)],
)
def test_dashscope_preserves_model_capabilities(model, sequential, limit):
    context = DrawingRequestContext(
        SimpleNamespace(_get_provider_value=lambda key, provider: provider.get(key)), None, None
    )
    payload = build_dashscope_payload(context, "提示词", ["reference"], {
        "model": model, "image_size": "2K", "aspect_ratio": "1:1", "n": 20,
        "enable_sequential": sequential, "negative_prompt": "模糊", "thinking_mode": True,
    })
    parameters = payload["parameters"]
    assert parameters["n"] == limit
    assert parameters["size"] == "2048*2048"
    assert payload["input"]["messages"][0]["content"] == [{"text": "提示词"}, {"image": "reference"}]
    assert ("negative_prompt" in parameters) is not model.startswith("wan2.7")
    assert ("enable_sequential" in parameters) is sequential
    assert ("thinking_mode" in parameters) is (model.startswith("wan2.7") and not sequential)
