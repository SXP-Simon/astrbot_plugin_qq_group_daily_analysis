import asyncio
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


def test_driver_factory_detection():
    # 1. SnowLuma 识别
    d1 = OneBotDriverFactory.create_driver_by_app_name("SnowLuma")
    assert isinstance(d1, SnowLumaDriver)

    # 2. LLOneBot 识别
    d2 = OneBotDriverFactory.create_driver_by_app_name("LLOneBot")
    assert isinstance(d2, LLOneBotDriver)

    # 3. NapCat 识别
    d3 = OneBotDriverFactory.create_driver_by_app_name("NapCat.Onebot")
    assert isinstance(d3, NapCatDriver)

    # 4. 标准/onebots 识别
    d4 = OneBotDriverFactory.create_driver_by_app_name("onebots")
    assert isinstance(d4, StandardOneBotDriver)

    # 5. 空/None 默认标准驱动
    d5 = OneBotDriverFactory.create_driver_by_app_name(None)
    assert isinstance(d5, StandardOneBotDriver)


def test_snowluma_history_pagination_params_and_anchor():
    driver = SnowLumaDriver()
    params = driver.build_history_params(
        group_id="123456", count=50, anchor_id="msg_999"
    )
    assert params == {"group_id": 123456, "count": 50, "message_id": "msg_999"}
    assert "reverseOrder" not in params

    anchor = driver.extract_history_anchor({"message_id": "mid_100", "message_seq": 88})
    assert anchor == "mid_100"


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


def test_adapter_auto_detects_and_binds_driver():
    bot = MockBot({"get_version_info": {"app_name": "SnowLuma", "app_version": "1.0"}})
    adapter = OneBotAdapter(bot)

    async def run_fetch():
        return await adapter.fetch_messages(group_id="123456", days=1, max_count=10)

    _ = asyncio.run(run_fetch())
    assert isinstance(adapter._driver, SnowLumaDriver)
    assert adapter._driver.name == "snowluma"
