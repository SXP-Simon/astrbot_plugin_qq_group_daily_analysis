"""绘图回退后的阶段记录应对应真正执行的后端。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_comic_regressions import _comic_config_manager, _comic_service

from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_backend", ["big_banana", "general_plugin"])
async def test_external_fallback_records_builtin_backend(monkeypatch, configured_backend):
    trace = TraceContext(trace_id="comic-backend")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    service = _comic_service(
        _comic_config_manager(get_drawing_backend=lambda: configured_backend),
        SimpleNamespace(generate_image=AsyncMock(return_value=(b"comic", None))),
    )
    image, url = await service.generate_comic([{"topic": "话题"}], "123", "umo")
    assert image == b"comic"
    assert url is None
    payload = next(span["payload"] for span in trace._spans if span["stage_name"] == "COMIC_DRAWING")
    assert payload["backend"] == "builtin"
    assert payload["prompts"]["comic_drawing"]["provider_type"] == "builtin"
    assert "绘图引擎: builtin" in payload["prompts"]["comic_drawing"]["system_prompt"]
