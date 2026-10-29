"""漫画参考图加载的输入边界与文件路径回归。"""

import pytest

from src.application.services.comic_application_service import ComicApplicationService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference",
    [
        "data:image/png;base64,!!!",
        "data:image/png;base64,",
        "data:image/png;base64",
        "data:image/png;base64,aW1hZ2U=!!!",
        "base64://!!!",
        "base64://",
        "base64://aW1hZ2U=!!!",
    ],
)
async def test_reference_rejects_empty_or_malformed_base64(reference):
    service = object.__new__(ComicApplicationService)
    assert await service._fetch_reference_image(reference) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference,mime",
    [
        ("data:image/webp;base64,aW1hZ2U=", "image/webp"),
        ("base64://aW1hZ2U=", "image/png"),
    ],
)
async def test_reference_preserves_valid_base64(reference, mime):
    service = object.__new__(ComicApplicationService)
    assert await service._fetch_reference_image(reference) == (b"image", mime)
