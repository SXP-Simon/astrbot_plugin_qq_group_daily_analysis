"""漫画分镜阶段的 Token 诊断与空结果回归。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.comic_application_service import ComicApplicationService
from src.domain.value_objects import TokenUsage
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("scene", ["分镜提示词", None])
async def test_storyboard_records_usage_and_missing_scene_warning(monkeypatch, scene):
    trace = TraceContext(trace_id="comic-storyboard")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    service = object.__new__(ComicApplicationService)
    usage = TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8)
    service.llm_analyzer = SimpleNamespace(analyze_comic_storyboards=AsyncMock(
        return_value=([{"scene": scene}] if scene else [], usage)
    ))
    result = await service._generate_scene_prompt([], "umo", "角色", "persona", "模板")
    assert result == scene
    payload = trace._spans[0]["payload"]
    assert payload["prompt_tokens"] == 3
    assert payload["completion_tokens"] == 5
    assert payload["total_tokens"] == 8
    assert ("warning" in payload) is (scene is None)
    if scene:
        prompt = payload["prompts"]["comic_storyboards"]
        assert prompt["prompt"] == "模板"
        assert prompt["completion"] == scene
        assert prompt["tokens"] == 8
