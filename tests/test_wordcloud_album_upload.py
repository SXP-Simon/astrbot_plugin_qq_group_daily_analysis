"""词云普通发送先于相册归档，归档失败不引发重复消息。"""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.wordcloud_command_handler import WordCloudCommandHandler
from src.application.services.wordcloud_delivery_service import WordCloudDeliveryService
from src.domain.value_objects.wordcloud import WordCloudData, WordFrequency
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.persistence.wordcloud_store import WordCloudStore
from src.infrastructure.platform.adapters.onebot.group_file_manager import (
    OneBotGroupFileManager,
)
from src.infrastructure.platform.adapters.onebot.standard_driver import (
    StandardOneBotDriver,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def setup_delivery(
    tmp_path, *, upload_config=None, image=b"wordcloud", send_result=True
):
    """建立生产发送用例，替换实际网络和渲染边界。"""
    config = object.__new__(ConfigManager)
    config.config = {
        "qq_group_upload": upload_config
        if upload_config is not None
        else {
            "enable_wordcloud_album_upload": True,
            "group_album_name": "群分析",
            "group_album_strict_mode": True,
        }
    }
    calls = []
    store = WordCloudStore(tmp_path / "wordcloud.db")

    async def send(*_args, **_kwargs):
        calls.append("send-image")
        if isinstance(send_result, Exception):
            raise send_result
        return send_result

    async def find(*_args):
        calls.append("find-album")
        return "album-id"

    async def upload(**_kwargs):
        # 相册调用前，普通消息成功已经持久化，之后即使归档失败也不自动重发。
        with sqlite3.connect(store.path) as conn:
            assert (
                conn.execute(
                    "SELECT status FROM wordcloud_delivery ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()[0]
                == "sent"
            )
        calls.append("upload-album")
        return True

    adapter = SimpleNamespace(
        find_album_id=AsyncMock(side_effect=find),
        upload_group_album=AsyncMock(side_effect=upload),
        get_group_album_list=AsyncMock(return_value=[]),
    )
    bot_manager = SimpleNamespace(
        get_adapter=Mock(return_value=adapter), update_from_event=Mock()
    )
    sender = SimpleNamespace(
        bot_manager=bot_manager, send_image_smart=AsyncMock(side_effect=send)
    )
    renderer = SimpleNamespace(render=AsyncMock(return_value=image))
    service = WordCloudDeliveryService(config, renderer, store, sender)
    data = WordCloudData(
        (WordFrequency("高性能", 12, 8),), message_count=8, group_id="123"
    )
    return service, data, adapter, calls


def test_album_config_is_default_off_and_kept_in_existing_upload_group():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    setting = schema["qq_group_upload"]["items"]["enable_wordcloud_album_upload"]
    assert setting["type"] == "bool"
    assert setting["default"] is False
    assert "enable_wordcloud_album_upload" not in schema["wordcloud"]["items"]
    name_setting = schema["qq_group_upload"]["items"]["wordcloud_album_name"]
    assert name_setting["type"] == "string"
    assert name_setting["default"] == ""
    assert "wordcloud_album_name" not in schema["wordcloud"]["items"]
    config = object.__new__(ConfigManager)
    config.config = {
        "qq_group_upload": {
            "enable_group_album_upload": True,
            "enable_comic_album_upload": True,
        }
    }
    assert not config.get_enable_wordcloud_album_upload()
    assert config.get_wordcloud_album_name() == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (
            {"group_album_name": "日报相册", "wordcloud_album_name": "  词云相册  "},
            "词云相册",
        ),
        ({"group_album_name": "  日报相册  "}, "日报相册"),
        ({"group_album_name": "日报相册", "wordcloud_album_name": ""}, "日报相册"),
        (
            {"group_album_name": "日报相册", "wordcloud_album_name": " \t "},
            "日报相册",
        ),
        ({"group_album_name": "", "wordcloud_album_name": "词云相册"}, "词云相册"),
    ],
)
async def test_wordcloud_album_name_resolves_independently_and_preserves_config(
    tmp_path: Path, names: dict[str, str], expected: str
) -> None:
    """独立名称优先，空值兼容继承日报相册，解析不回写用户配置。"""
    upload_config = {
        "enable_wordcloud_album_upload": True,
        "group_album_strict_mode": True,
        "comic_album_name": "漫画相册",
        **names,
    }
    original = upload_config.copy()
    service, data, adapter, calls = setup_delivery(
        tmp_path, upload_config=upload_config
    )

    assert service.config_manager.get_wordcloud_album_name() == expected
    assert await service.send(data, "123", "bot")

    assert calls == ["send-image", "find-album", "upload-album"]
    adapter.find_album_id.assert_awaited_once_with("123", expected)
    adapter.upload_group_album.assert_awaited_once_with(
        group_id="123",
        image_path="base64://" + base64.b64encode(b"wordcloud").decode(),
        album_id="album-id",
        album_name=expected,
        strict_mode=True,
    )
    assert service.config_manager.config["qq_group_upload"] == original


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["report", "standalone", "retry"])
async def test_all_wordcloud_entry_points_send_before_album(tmp_path, entry):
    service, data, adapter, calls = setup_delivery(tmp_path)
    if entry == "report":
        assert await service.send_with_report(data, "123", "bot")
    else:
        service.config_manager.is_group_allowed = lambda _umo: True
        analysis = SimpleNamespace(
            collect_wordcloud=AsyncMock(return_value=data),
            bot_manager=service.message_sender.bot_manager,
        )
        handler = WordCloudCommandHandler(analysis, service)
        event = SimpleNamespace(
            should_call_llm=Mock(),
            get_group_id=lambda: "123",
            get_platform_id=lambda: "bot",
            unified_msg_origin="bot:GroupMessage:123",
            plain_result=lambda value: value,
        )
        if entry == "retry":
            service.store.save(event.unified_msg_origin, "cached", data, "cached")
        result = [item async for item in handler.handle(event, retry=entry == "retry")]
        assert result == ([] if entry == "retry" else ["正在提取群聊词频并生成词云……"])
        assert analysis.collect_wordcloud.await_count == (0 if entry == "retry" else 1)
    assert calls == ["send-image", "find-album", "upload-album"]
    adapter.upload_group_album.assert_awaited_once_with(
        group_id="123",
        image_path="base64://" + base64.b64encode(b"wordcloud").decode(),
        album_id="album-id",
        album_name="群分析",
        strict_mode=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("send_result", [False, RuntimeError("发送失败")])
@pytest.mark.parametrize("wordcloud_album_name", ["", "词云相册"])
async def test_failed_image_send_never_uploads_album(
    tmp_path, send_result, wordcloud_album_name
):
    service, data, adapter, calls = setup_delivery(
        tmp_path,
        send_result=send_result,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_name": "日报相册",
            "wordcloud_album_name": wordcloud_album_name,
            "group_album_strict_mode": True,
        },
    )
    assert not await service.send(data, "123", "bot")
    assert calls == ["send-image"]
    adapter.find_album_id.assert_not_awaited()
    adapter.upload_group_album.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [False, RuntimeError("相册拒绝访问")])
async def test_album_failure_preserves_sent_state_and_prevents_automatic_resend(
    tmp_path, result
):
    service, data, adapter, _ = setup_delivery(tmp_path)
    adapter.upload_group_album.side_effect = (
        result if isinstance(result, Exception) else None
    )
    adapter.upload_group_album.return_value = result
    assert await service.send(data, "123", "bot")
    assert await service.send_with_report(data, "123", "bot")
    assert service.message_sender.send_image_smart.await_count == 1
    assert adapter.upload_group_album.await_count == 1
    with sqlite3.connect(service.store.path) as conn:
        assert conn.execute(
            "SELECT status,error FROM wordcloud_delivery"
        ).fetchone() == ("sent", "")


@pytest.mark.asyncio
async def test_cancelled_album_is_not_swallowed_or_marked_failed(tmp_path):
    service, data, adapter, _ = setup_delivery(tmp_path)
    adapter.upload_group_album.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await service.send(data, "123", "bot")
    assert await service.send(data, "123", "bot")
    assert service.message_sender.send_image_smart.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("album_name", ["", "不存在的相册"])
async def test_strict_mode_skips_unresolved_album_without_fallback(
    tmp_path, album_name
):
    service, data, adapter, _ = setup_delivery(
        tmp_path,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_name": album_name,
            "group_album_strict_mode": True,
        },
    )
    adapter.find_album_id.side_effect = None
    adapter.find_album_id.return_value = None
    assert await service.send(data, "123", "bot")
    adapter.upload_group_album.assert_not_awaited()
    assert adapter.find_album_id.await_count == (1 if album_name else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "names",
    [
        {},
        {"group_album_name": "", "wordcloud_album_name": ""},
        {"group_album_name": " \t ", "wordcloud_album_name": " \t "},
    ],
)
async def test_strict_mode_skips_album_when_both_names_are_empty(
    tmp_path: Path, names: dict[str, str]
) -> None:
    """严格模式找不到可用名称时，仅发送普通图片，不触碰默认相册。"""
    service, data, adapter, calls = setup_delivery(
        tmp_path,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_strict_mode": True,
            **names,
        },
    )

    assert service.config_manager.get_wordcloud_album_name() == ""
    assert await service.send(data, "123", "bot")
    assert calls == ["send-image"]
    adapter.find_album_id.assert_not_awaited()
    adapter.upload_group_album.assert_not_awaited()


@pytest.mark.asyncio
async def test_strict_mode_missing_wordcloud_album_never_uses_report_album(
    tmp_path: Path,
) -> None:
    """独立相册不存在时遵守严格模式，不退回到存在的日报相册。"""
    service, data, adapter, calls = setup_delivery(
        tmp_path,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_name": "日报相册",
            "wordcloud_album_name": "不存在的词云相册",
            "group_album_strict_mode": True,
        },
    )
    adapter.find_album_id.side_effect = None
    adapter.find_album_id.return_value = None

    assert await service.send(data, "123", "bot")
    assert calls == ["send-image"]
    adapter.find_album_id.assert_awaited_once_with("123", "不存在的词云相册")
    adapter.upload_group_album.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_strict_missing_wordcloud_album_uses_platform_default(
    tmp_path: Path,
) -> None:
    """独立词云相册缺失时交由平台回退默认相册，不改用存在的日报相册。"""
    service, data, adapter, calls = setup_delivery(
        tmp_path,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_name": "日报相册",
            "wordcloud_album_name": "不存在的词云相册",
            "group_album_strict_mode": False,
        },
    )

    async def find_album(group_id: str, album_name: str) -> str | None:
        calls.append("find-album")
        assert group_id == "123"
        return "report-album-id" if album_name == "日报相册" else None

    adapter.find_album_id.side_effect = find_album

    assert await service.send(data, "123", "bot")
    assert calls == ["send-image", "find-album", "upload-album"]
    adapter.find_album_id.assert_awaited_once_with("123", "不存在的词云相册")
    adapter.upload_group_album.assert_awaited_once_with(
        group_id="123",
        image_path="base64://" + base64.b64encode(b"wordcloud").decode(),
        album_id=None,
        album_name="不存在的词云相册",
        strict_mode=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("strict_mode", [True, False])
async def test_real_onebot_manager_honors_strict_mode_and_default_album(
    strict_mode: bool,
) -> None:
    """真实相册管理器严格时中止，非严格时选择列表首项而不是日报相册。"""
    requests: list[tuple[str, dict[str, object]]] = []
    transmissions: list[tuple[str, str]] = []

    class BotNetworkStub:
        """仅替换 OneBot 网络边界，相册查找与回退仍执行生产逻辑。"""

        async def call_action(self, action: str, **params: object) -> object:
            requests.append((action, params))
            if action == "get_qun_album_list":
                return {
                    "status": "ok",
                    "data": {
                        "album_list": [
                            {"album_id": "first-album-id", "name": "其他相册"},
                            {"album_id": "report-album-id", "name": "日报相册"},
                        ]
                    },
                }
            if action == "upload_image_to_qun_album":
                return {"status": "ok"}
            raise AssertionError(f"出现非预期的网络动作：{action}")

    driver = StandardOneBotDriver()

    async def get_driver() -> StandardOneBotDriver:
        return driver

    async def transmit(
        image_path: str,
        upload: Callable[[str, str], Awaitable[None]],
        label: str,
    ) -> bool:
        transmissions.append((image_path, label))
        await upload(image_path, label)
        return True

    manager = OneBotGroupFileManager(BotNetworkStub(), get_driver, transmit)
    image = "base64://" + base64.b64encode(b"wordcloud").decode()
    result = await manager.upload_group_album(
        group_id="123",
        image_path=image,
        album_name="不存在的词云相册",
        strict_mode=strict_mode,
    )

    if strict_mode:
        assert result is False
        assert transmissions == []
        assert requests == [("get_qun_album_list", {"group_id": 123})]
    else:
        assert result is True
        assert transmissions == [(image, "OneBot 相册")]
        assert requests == [
            ("get_qun_album_list", {"group_id": 123}),
            ("get_qun_album_list", {"group_id": 123}),
            (
                "upload_image_to_qun_album",
                {
                    "group_id": 123,
                    "file": image,
                    "album_id": "first-album-id",
                    "album_name": "不存在的词云相册",
                },
            ),
        ]


@pytest.mark.asyncio
async def test_non_strict_mode_preserves_existing_default_album_behavior(tmp_path):
    service, data, adapter, _ = setup_delivery(
        tmp_path,
        upload_config={
            "enable_wordcloud_album_upload": True,
            "group_album_name": "",
            "group_album_strict_mode": False,
        },
    )
    assert await service.send(data, "123", "bot")
    assert adapter.upload_group_album.call_args.kwargs["album_id"] is None
    assert adapter.upload_group_album.call_args.kwargs["album_name"] == ""
    assert adapter.upload_group_album.call_args.kwargs["strict_mode"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [True, False])
async def test_disabled_or_unsupported_platform_skips_album(tmp_path, disabled):
    service, data, adapter, _ = setup_delivery(tmp_path)
    if disabled:
        service.config_manager.config["qq_group_upload"][
            "enable_wordcloud_album_upload"
        ] = False
    else:
        service.message_sender.bot_manager.get_adapter.return_value = SimpleNamespace(
            get_platform_name=lambda: "qq_official"
        )
    assert await service.send(data, "123", "bot")
    adapter.find_album_id.assert_not_awaited()
    adapter.upload_group_album.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["path", "url", "base64", "data"])
async def test_upload_reuses_rendered_image_and_retains_cached_file(tmp_path, source):
    cached = tmp_path / "rendered.png"
    cached.write_bytes(b"wordcloud")
    encoded = base64.b64encode(cached.read_bytes()).decode()
    image = {
        "path": str(cached),
        "url": "https://example.com/wordcloud.png",
        "base64": "base64://" + encoded,
        "data": "data:image/png;base64," + encoded,
    }[source]
    service, data, adapter, _ = setup_delivery(tmp_path, image=image)
    assert await service.send(data, "123", "bot")
    expected = "base64://" + encoded if source == "data" else image
    assert adapter.upload_group_album.call_args.kwargs["image_path"] == expected
    assert cached.read_bytes() == b"wordcloud"
    service.renderer.render.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_retry_can_send_and_archive_again(tmp_path):
    service, data, adapter, calls = setup_delivery(tmp_path)
    assert await service.send(data, "123", "bot")
    assert await service.send(data, "123", "bot", force=True)
    assert calls == ["send-image", "find-album", "upload-album"] * 2
    assert adapter.upload_group_album.await_count == 2
