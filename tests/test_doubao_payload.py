"""豆包模型能力差异及参考图请求形态的回归。"""

from types import SimpleNamespace

import pytest

from src.infrastructure.drawing.api_requests.context import DrawingRequestContext
from src.infrastructure.drawing.api_requests.doubao import build_doubao_payload


@pytest.mark.parametrize("pro,limit", [(False, 14), (True, 10)])
def test_doubao_model_limits_and_sequential_capability(pro, limit):
    context = DrawingRequestContext(
        SimpleNamespace(_get_provider_value=lambda key, provider: provider.get(key)),
        None,
        None,
    )
    provider = {
        "model": "seedream-5.0-pro" if pro else "seedream-4.0",
        "image_size": "2K",
        "sequential_image_generation": "auto",
        "sequential_max_images": 3,
    }
    references = [f"data:image/png;base64,ref{index}" for index in range(20)]
    payload = build_doubao_payload(context, "提示词", references, provider)
    assert len(payload["image"]) == limit
    assert payload["size"] == "2K"
    assert ("sequential_image_generation" in payload) is not pro
    if not pro:
        assert payload["sequential_image_generation_options"] == {"max_images": 3}


def test_doubao_single_reference_and_endpoint_model_override():
    context = DrawingRequestContext(
        SimpleNamespace(_get_provider_value=lambda key, provider: provider.get(key)),
        None,
        None,
    )
    payload = build_doubao_payload(
        context,
        "提示词",
        ["first", "second"],
        {"model": "seedream", "endpoint_id": "ep-model", "max_reference_images": 1, "image_size": "2K"},
    )
    assert payload["model"] == "ep-model"
    assert payload["image"] == "first"
