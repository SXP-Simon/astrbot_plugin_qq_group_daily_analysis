"""漫画重写后的最终请求与错误必须反映在任务诊断中。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_comic_regressions import _comic_config_manager, _comic_service

from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("image,error", [(None, "最终服务错误"), (b"reference", "绘图服务原样返回了参考图"), (b"comic", None)])
async def test_rewrite_records_actual_prompt_and_final_error(monkeypatch, image, error):
    trace = TraceContext(trace_id="comic-retry")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    service = _comic_service(
        _comic_config_manager(
            get_drawing_backend=lambda: "builtin",
            get_drawing_reference_images=lambda: ["reference.png"],
            get_drawing_output_exception_retry_keywords=lambda: ["blocked"],
        ),
        SimpleNamespace(generate_image=AsyncMock(side_effect=[(None, "blocked"), (image, None if image else error)])),
        _fetch_reference_image=AsyncMock(return_value=(b"reference", "image/png")),
    )
    service.llm_analyzer.analyze_retry_prompt = AsyncMock(return_value="实际重写提示词")
    result, url = await service.generate_comic([{"topic": "话题"}], "123", "umo")
    assert result == (image if image == b"comic" else None)
    assert url is None
    payload = next(span["payload"] for span in trace._spans if span["stage_name"] == "COMIC_DRAWING")
    assert payload["last_error"] == error
    assert payload["prompts"]["comic_drawing"]["prompt"] == "实际重写提示词"
    assert payload["scene_prompt_len"] == len("实际重写提示词")
