"""内置绘图的提示词重写与下载失败兜底回归。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.comic_application_service import ComicApplicationService
from src.infrastructure.drawing.drawing_client import ImageDownloadFailedError


@pytest.mark.asyncio
async def test_builtin_rewrites_once_and_reuses_reference_images():
    service = object.__new__(ComicApplicationService)
    service.config_manager = SimpleNamespace(get_drawing_output_exception_retry_keywords=lambda: ["blocked"])
    service.llm_analyzer = SimpleNamespace(analyze_retry_prompt=AsyncMock(return_value="重写提示词"))
    service.drawing_client = SimpleNamespace(generate_image=AsyncMock(side_effect=[(None, "blocked"), (b"comic", None)]))
    references = [(b"reference", "image/png")]
    image, _, url, used_prompt = await service._generate_builtin_comic("原提示词", references, "umo")
    assert image == b"comic"
    assert used_prompt == "重写提示词"
    assert url is None
    service.llm_analyzer.analyze_retry_prompt.assert_awaited_once_with("原提示词", "blocked", "umo")
    assert service.drawing_client.generate_image.await_count == 2
    assert service.drawing_client.generate_image.await_args.args == ("重写提示词",)
    assert service.drawing_client.generate_image.await_args.kwargs == {"images_data": references, "disable_retry": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("after_rewrite", [True, False])
async def test_builtin_preserves_download_fallback_url(after_rewrite):
    service = object.__new__(ComicApplicationService)
    service.config_manager = SimpleNamespace(get_drawing_output_exception_retry_keywords=lambda: ["blocked"])
    service.llm_analyzer = SimpleNamespace(analyze_retry_prompt=AsyncMock(return_value="重写提示词"))
    error = ImageDownloadFailedError("下载失败", fallback_url="https://example.com/comic.png")
    responses = [(None, "blocked"), error] if after_rewrite else [error]
    service.drawing_client = SimpleNamespace(generate_image=AsyncMock(side_effect=responses))
    image, reason, url, used_prompt = await service._generate_builtin_comic("原提示词", [], "umo")
    assert image is None
    assert reason
    assert used_prompt == ("重写提示词" if after_rewrite else "原提示词")
    assert url == "https://example.com/comic.png"
    assert service.drawing_client.generate_image.await_count == (2 if after_rewrite else 1)
