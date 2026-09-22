import asyncio
from pathlib import Path
from typing import Any

from src.infrastructure.platform.adapters.onebot import (
    LLOneBotDriver,
    NapCatDriver,
    OneBotDriverFactory,
    SnowLumaDriver,
    StandardOneBotDriver,
)
from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter


class MockBot:
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}
        self.action_calls: list[tuple[str, dict[str, Any]]] = []

    async def call_action(self, action: str, **params):
        self.action_calls.append((action, params))
        if action in self.responses:
            val = self.responses[action]
            if isinstance(val, BaseException):
                raise val
            return val
        return {}


# ==========================================
# 1. 驱动工厂探测与识别测试
# ==========================================


def test_driver_factory_detection():
    # 1. SnowLuma 识别
    d1 = OneBotDriverFactory.create_driver_by_app_name("SnowLuma")
    assert isinstance(d1, SnowLumaDriver)
    assert d1.name == "snowluma"

    # 2. LLOneBot 识别 (支持多种常见命名)
    d2_1 = OneBotDriverFactory.create_driver_by_app_name("LLOneBot")
    d2_2 = OneBotDriverFactory.create_driver_by_app_name("LuckyLilliaBot")
    d2_3 = OneBotDriverFactory.create_driver_by_app_name("llbot")
    assert isinstance(d2_1, LLOneBotDriver)
    assert isinstance(d2_2, LLOneBotDriver)
    assert isinstance(d2_3, LLOneBotDriver)
    assert d2_1.name == "llonebot"

    # 3. NapCat 识别
    d3 = OneBotDriverFactory.create_driver_by_app_name("NapCat.Onebot")
    assert isinstance(d3, NapCatDriver)
    assert d3.name == "napcat"

    # 4. 标准/onebots 识别
    d4 = OneBotDriverFactory.create_driver_by_app_name("onebots")
    assert isinstance(d4, StandardOneBotDriver)
    assert d4.name == "standard"

    # 5. 空/None 默认标准驱动
    d5 = OneBotDriverFactory.create_driver_by_app_name(None)
    assert isinstance(d5, StandardOneBotDriver)


def test_driver_factory_detect_driver_with_mock_bot():
    # 异步通过 get_version_info 探测
    bot_snow = MockBot({"get_version_info": {"app_name": "SnowLuma"}})
    driver_snow = asyncio.run(OneBotDriverFactory.detect_driver(bot_snow))
    assert isinstance(driver_snow, SnowLumaDriver)

    bot_napcat = MockBot({"get_version_info": {"app_name": "NapCat.Onebot"}})
    driver_napcat = asyncio.run(OneBotDriverFactory.detect_driver(bot_napcat))
    assert isinstance(driver_napcat, NapCatDriver)

    bot_fail = MockBot({"get_version_info": TimeoutError("Timeout")})
    driver_fail = asyncio.run(OneBotDriverFactory.detect_driver(bot_fail))
    assert isinstance(driver_fail, StandardOneBotDriver)


# ==========================================
# 2. SnowLuma 专有行为测试
# ==========================================


def test_snowluma_history_pagination_params_and_anchor():
    driver = SnowLumaDriver()
    params = driver.build_history_params(
        group_id="123456", count=50, anchor_id="msg_999"
    )
    assert params == {"group_id": 123456, "count": 50, "message_id": "msg_999"}
    assert "reverseOrder" not in params

    anchor = driver.extract_history_anchor({"message_id": "mid_100", "message_seq": 88})
    assert anchor == "mid_100"


def test_snowluma_mute_and_rejection_error_handling():
    driver = SnowLumaDriver()

    # 1. SnowLuma 特有 result=120 错误
    exc1 = RuntimeError("send group message rejected: result=120 err=group mute")
    assert driver.is_mute_exception(exc1) is True

    # 2. SnowLuma retcode=100 + rejected + muted
    exc2 = Exception("retcode=100 send group message rejected: muted")
    assert driver.is_mute_exception(exc2) is True

    # 3. 普通错误不误判
    exc3 = Exception("network connection reset")
    assert driver.is_mute_exception(exc3) is False


# ==========================================
# 3. LLOneBot (LuckyLilliaBot) 专有行为测试
# ==========================================


def test_llonebot_album_upload_uses_files_array():
    bot = MockBot()
    driver = LLOneBotDriver()
    asyncio.run(
        driver.upload_group_album(
            bot=bot,
            group_id="123456",
            album_id="album_1",
            album_name="相册",
            file_content="base64://demo",
        )
    )
    assert len(bot.action_calls) == 1
    action, params = bot.action_calls[0]
    assert action == "upload_group_album"
    assert params == {
        "group_id": 123456,
        "album_id": "album_1",
        "files": ["base64://demo"],
    }


def test_llonebot_album_upload_fallback_on_error():
    # 当 files 模式失败时回退到通用 API 轮询
    class FailingFilesBot(MockBot):
        async def call_action(self, action: str, **params):
            self.action_calls.append((action, params))
            if "files" in params:
                raise RuntimeError("files array not supported")
            if action == "upload_image_to_qun_album":
                return {"status": "ok"}
            return {}

    bot = FailingFilesBot()
    driver = LLOneBotDriver()
    asyncio.run(
        driver.upload_group_album(
            bot=bot,
            group_id="123456",
            album_id="album_1",
            album_name="相册",
            file_content="base64://demo",
        )
    )
    # 应先尝试带 files 的 upload_group_album，失败后尝试 upload_image_to_qun_album
    assert len(bot.action_calls) == 2
    assert bot.action_calls[0][0] == "upload_group_album"
    assert bot.action_calls[1][0] == "upload_image_to_qun_album"


# ==========================================
# 4. NapCat 专有行为测试
# ==========================================


def test_napcat_stream_upload_delegation(tmp_path: Path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"fake image content")

    # upload_file_stream 分两阶段：分块上传返回字典/None，完成上传返回 {"data": {"file_path": ...}}
    class StreamBot(MockBot):
        async def call_action(self, action: str, **params):
            self.action_calls.append((action, params))
            if action == "upload_file_stream":
                if params.get("is_complete"):
                    return {"data": {"file_path": "/tmp/napcat_uploaded.jpg"}}
                return {"status": "ok", "retcode": 0}
            return {}

    bot = StreamBot()
    driver = NapCatDriver()

    res = asyncio.run(driver.upload_stream_file(bot, dummy_file))
    assert res == "/tmp/napcat_uploaded.jpg"


def test_standard_driver_no_stream_upload(tmp_path: Path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"fake image content")

    bot = MockBot()
    driver = StandardOneBotDriver()
    # 标准驱动 upload_stream_file 默认返回 None
    res = asyncio.run(driver.upload_stream_file(bot, dummy_file))
    assert res is None


# ==========================================
# 5. Standard / 通用行为测试 (全群禁言判定与分页)
# ==========================================


def test_standard_history_pagination_params_and_anchor():
    driver = StandardOneBotDriver()
    params = driver.build_history_params(group_id="123456", count=50, anchor_id=1234)
    assert params == {
        "group_id": 123456,
        "count": 50,
        "reverseOrder": True,
        "message_seq": 1234,
    }

    anchor = driver.extract_history_anchor({"message_id": "mid_100", "message_seq": 88})
    assert anchor == 88


def test_standard_whole_ban_detection():
    driver = StandardOneBotDriver()
    # 兼容各平台不同字段名
    assert driver.is_whole_ban({"group_all_shut": True}) is True
    assert driver.is_whole_ban({"shutup_all": True}) is True
    assert driver.is_whole_ban({"is_whole_ban": True}) is True
    assert driver.is_whole_ban({"whole_ban": True}) is True
    assert driver.is_whole_ban({"shut_up": True}) is True
    assert driver.is_whole_ban({"shutup": True}) is True
    assert driver.is_whole_ban({"max_member_count": 500}) is False


# ==========================================
# 6. Adapter 端到端与驱动协同测试
# ==========================================


def test_adapter_auto_detects_and_binds_driver():
    bot = MockBot({"get_version_info": {"app_name": "SnowLuma", "app_version": "1.0"}})
    adapter = OneBotAdapter(bot)

    async def run_fetch():
        return await adapter.fetch_messages(group_id="123456", days=1, max_count=10)

    _ = asyncio.run(run_fetch())
    assert isinstance(adapter._driver, SnowLumaDriver)
    assert adapter._driver.name == "snowluma"
