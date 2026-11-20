"""外部绘图插件接入的正常响应与失败回退契约。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.drawing.external_drawing_adapter import ExternalDrawingAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "reference_count"),
    [
        ("success", 0),
        ("success", 1),
        ("success", 2),
        ("inactive", 1),
        ("missing_api", 1),
        ("exception", 1),
        ("rejected", 1),
        ("empty", 1),
        ("bad_paths", 1),
        ("missing_file", 1),
    ],
)
async def test_general_drawing_plugin_returns_bytes_or_none(
    tmp_path, mode, reference_count
):
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
    scene = "The protagonist wears a blue flower."
    references = [(f"reference-{i}".encode(), "image/png") for i in range(reference_count)]
    result = await adapter.generate_general(scene, references or None)
    assert result == (b"rendered-image" if mode == "success" else None)
    if mode == "success":
        assert call.await_args.kwargs["reference_image_data"] == (references or None)
        prompt = call.await_args.kwargs["prompt"]
        if not references:
            assert prompt == scene
        else:
            prefix = (
                "The attached image shows"
                if reference_count == 1
                else "The attached images show"
            )
            assert prompt.startswith(f"{prefix} the recurring protagonist")
            assert scene in prompt


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
