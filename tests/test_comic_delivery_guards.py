"""漫画交付的 URL 兜底及相册上传门槛应保持一致。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.comic_command_handler import ComicCommandHandler
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fallback", "send_failure", "success"])
async def test_comic_delivery_preserves_fallback_and_album_gate(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    adapter = SimpleNamespace(send_image=AsyncMock(return_value=mode == "success"))
    output = (None, "https://example.com/comic.png") if mode == "fallback" else (b"comic", None)
    handler = ComicCommandHandler(
        SimpleNamespace(get_t2i_max_concurrent=lambda: 1, get_show_report_caption=lambda: False),
        SimpleNamespace(get_adapter=Mock(return_value=adapter)),
        SimpleNamespace(generate_comic=AsyncMock(return_value=output)),
        None,
        plugin_data_dir=tmp_path,
    )
    handler._try_upload_image = AsyncMock()
    await handler._trigger_comic_generation([], "123", "platform", "umo")
    adapter.send_image.assert_awaited_once()
    if mode == "fallback":
        assert adapter.send_image.await_args.args == ("123", "https://example.com/comic.png")
        assert not (tmp_path / "reports").exists()
    else:
        assert len(list((tmp_path / "reports").iterdir())) == 1
    assert handler._try_upload_image.await_count == (1 if mode == "success" else 0)
