"""外部绘图插件接入的正常响应与失败回退契约。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.drawing.external_drawing_adapter import ExternalDrawingAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "inactive",
        "missing_api",
        "exception",
        "rejected",
        "empty",
        "bad_paths",
        "missing_file",
    ],
)
async def test_general_drawing_plugin_returns_bytes_or_none(tmp_path, mode):
    output = tmp_path / "comic.png"
    output.write_bytes(b"rendered-image")
    paths = [str(output)]
    if mode == "empty":
        paths = []
    elif mode == "bad_paths":
        paths = 42
    elif mode == "missing_file":
        paths = [str(tmp_path / "missing.png")]
    call = AsyncMock(
        return_value=SimpleNamespace(ok=mode != "rejected", code="timeout", paths=paths)
    )
    if mode == "exception":
        call.side_effect = RuntimeError("network")
    plugin = SimpleNamespace(public_api=SimpleNamespace(generate_image_files=call))
    if mode == "missing_api":
        plugin = SimpleNamespace()
    meta = SimpleNamespace(activated=mode != "inactive", star_cls=plugin)
    context = SimpleNamespace(get_registered_star=lambda name: meta)
    adapter = ExternalDrawingAdapter(context)
    result = await adapter.generate_general("scene", [(b"reference", "image/png")])
    assert result == (b"rendered-image" if mode == "success" else None)
    if mode == "success":
        assert call.await_args.kwargs["reference_image_data"] == [
            (b"reference", "image/png")
        ]
        assert call.await_args.kwargs["prompt"] == "scene"


@pytest.mark.asyncio
async def test_cancelled_external_render_propagates_cancellation():
    import asyncio

    call = AsyncMock(side_effect=asyncio.CancelledError)
    context = SimpleNamespace(
        get_registered_star=lambda name: SimpleNamespace(
            activated=True,
            star_cls=SimpleNamespace(
                public_api=SimpleNamespace(generate_image_files=call)
            ),
        )
    )
    with pytest.raises(asyncio.CancelledError):
        await ExternalDrawingAdapter(context).generate_general("scene", None)
