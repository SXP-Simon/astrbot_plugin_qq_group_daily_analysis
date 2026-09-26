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
    # 1. OneBot v11 异步通过 get_version_info 探测
    bot_snow = MockBot({"get_version_info": {"app_name": "SnowLuma"}})
    driver_snow = asyncio.run(OneBotDriverFactory.detect_driver(bot_snow))
    assert isinstance(driver_snow, SnowLumaDriver)

    bot_napcat = MockBot({"get_version_info": {"app_name": "NapCat.Onebot"}})
    driver_napcat = asyncio.run(OneBotDriverFactory.detect_driver(bot_napcat))
    assert isinstance(driver_napcat, NapCatDriver)

    # 1.1 兼容包装在 data 字典中的响应形态
    bot_wrapped = MockBot(
        {
            "get_version_info": {
                "status": "ok",
                "retcode": 0,
                "data": {"app_name": "NapCat.Onebot"},
            }
        }
    )
    driver_wrapped = asyncio.run(OneBotDriverFactory.detect_driver(bot_wrapped))
    assert isinstance(driver_wrapped, NapCatDriver)

    bot_v12_wrapped = MockBot(
        {
            "get_version_info": Exception("Action not found"),
            "get_version": {"status": "ok", "data": {"impl": "SnowLuma"}},
        }
    )
    driver_v12_wrapped = asyncio.run(OneBotDriverFactory.detect_driver(bot_v12_wrapped))
    assert isinstance(driver_v12_wrapped, SnowLumaDriver)

    # 2. OneBot v12 异步通过 get_version + impl 字段探测
    bot_v12 = MockBot(
        {
            "get_version_info": Exception("Action not found"),
            "get_version": {
                "impl": "SnowLuma",
                "version": "1.0",
                "onebot_version": "12",
            },
        }
    )
    driver_v12 = asyncio.run(OneBotDriverFactory.detect_driver(bot_v12))
    assert isinstance(driver_v12, SnowLumaDriver)

    # 3. 失败/超时回退标准驱动
    bot_fail = MockBot(
        {
            "get_version_info": TimeoutError("Timeout"),
            "get_version": TimeoutError("Timeout"),
        }
    )
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
# 6. Avatar CDN 与相册列表行为测试
# ==========================================


def test_standard_driver_avatar_cdn_url_building():
    driver = StandardOneBotDriver()
    # 1. 用户头像尺寸匹配（<=160 使用 q1.qlogo.cn，640 使用 q.qlogo.cn HD 模板）
    url_100 = driver.build_user_avatar_cdn_url("10001", size=100)
    assert url_100 == "https://q1.qlogo.cn/g?b=qq&nk=10001&s=100"

    url_640 = driver.build_user_avatar_cdn_url("10001", size=640)
    assert (
        url_640 == "https://q.qlogo.cn/headimg_dl?dst_uin=10001&spec=640&img_type=jpg"
    )

    url_nearest = driver.build_user_avatar_cdn_url("10001", size=120)
    assert url_nearest in (
        "https://q1.qlogo.cn/g?b=qq&nk=10001&s=100",
        "https://q1.qlogo.cn/g?b=qq&nk=10001&s=140",
    )

    # 2. 群头像 CDN URL
    group_url = driver.build_group_avatar_cdn_url("123456", size=100)
    assert group_url == "https://p.qlogo.cn/gh/123456/123456/100/"


def test_standard_driver_get_group_album_list():
    # 1. 测试从 data.album_list 中提取
    bot1 = MockBot(
        {
            "get_qun_album_list": {
                "data": {
                    "album_list": [
                        {"album_id": "alb_1", "name": "相册1"},
                        {"album_id": "alb_2", "name": "相册2"},
                    ]
                }
            }
        }
    )
    driver = StandardOneBotDriver()
    albums = asyncio.run(driver.get_group_album_list(bot1, "123456"))
    assert len(albums) == 2
    assert albums[0]["album_id"] == "alb_1"

    # 2. 测试从顶层 list 中提取（当 get_qun_album_list 失败，get_group_album_list 成功）
    bot2 = MockBot(
        {
            "get_qun_album_list": Exception("Not found"),
            "get_group_album_list": [{"album_id": "alb_3", "name": "相册3"}],
        }
    )
    albums2 = asyncio.run(driver.get_group_album_list(bot2, "123456"))
    assert len(albums2) == 1
    assert albums2[0]["album_id"] == "alb_3"


def test_napcat_driver_get_group_album_list():
    # NapCat 优先调用 get_qun_album_list 且返回顶层 album_list 结构
    bot = MockBot(
        {
            "get_qun_album_list": {
                "album_list": [
                    {"album_id": "napcat_alb_1", "album_name": "NapCat相册"}
                ],
                "attach_info": "",
                "has_more": False,
            }
        }
    )
    driver = NapCatDriver()
    albums = asyncio.run(driver.get_group_album_list(bot, "123456"))
    assert len(albums) == 1
    assert albums[0]["album_id"] == "napcat_alb_1"
    assert bot.action_calls[0][0] == "get_qun_album_list"


def test_llonebot_driver_get_group_album_list():
    # LLOneBot 优先调用 get_group_album_list 且返回 data.album_list 结构
    bot = MockBot(
        {
            "get_group_album_list": {
                "status": "ok",
                "data": {
                    "album_list": [
                        {"album_id": "llbot_alb_1", "album_name": "LLOneBot相册"}
                    ]
                },
            }
        }
    )
    driver = LLOneBotDriver()
    albums = asyncio.run(driver.get_group_album_list(bot, "123456"))
    assert len(albums) == 1
    assert albums[0]["album_id"] == "llbot_alb_1"
    assert bot.action_calls[0][0] == "get_group_album_list"


def test_llonebot_driver_get_group_album_list_array_data():
    # LLOneBot ntGroupApi 映射直接将数组置于 data 字段中: { status: "ok", data: [ { album_id: "...", name: "群分析" } ] }
    bot = MockBot(
        {
            "get_group_album_list": {
                "status": "ok",
                "retcode": 0,
                "data": [{"album_id": "alb_999", "name": "群分析", "desc": "每日分析"}],
            }
        }
    )
    driver = LLOneBotDriver()
    albums = asyncio.run(driver.get_group_album_list(bot, "2167050964"))
    assert len(albums) == 1
    assert albums[0]["album_id"] == "alb_999"
    assert albums[0]["name"] == "群分析"


def test_adapter_find_album_id_matches_name():
    bot = MockBot(
        {
            "get_group_album_list": {
                "status": "ok",
                "data": [
                    {"album_id": "alb_other", "name": "其他相册"},
                    {"album_id": "alb_target", "name": "群分析"},
                ],
            }
        }
    )
    adapter = OneBotAdapter(bot)
    adapter._driver = LLOneBotDriver()
    adapter._driver_detected = True

    found_id = asyncio.run(adapter.find_album_id("2167050964", "群分析"))
    assert found_id == "alb_target"

    not_found = asyncio.run(adapter.find_album_id("2167050964", "不存在的相册"))
    assert not_found is None


# ==========================================
# 7. Adapter 端到端与驱动协同测试
# ==========================================


def test_adapter_auto_detects_and_binds_driver():
    bot = MockBot({"get_version_info": {"app_name": "SnowLuma", "app_version": "1.0"}})
    adapter = OneBotAdapter(bot)

    async def run_fetch():
        return await adapter.fetch_messages(group_id="123456", days=1, max_count=10)

    _ = asyncio.run(run_fetch())
    assert isinstance(adapter._driver, SnowLumaDriver)
    assert adapter._driver.name == "snowluma"


# ==========================================
# 8. 群文件管理与结构解包测试
# ==========================================


def test_adapter_group_file_root_folders_unpacking():
    # 1. 结构被包裹在 data.folders 中 (如 NapCat/LLOneBot 标准响应)
    bot1 = MockBot(
        {
            "get_group_root_files": {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "folders": [
                        {"folder_id": "f_1", "folder_name": "日报归档"},
                        {"folder_id": "f_2", "folder_name": "群相册备份"},
                    ],
                    "files": [],
                },
            }
        }
    )
    adapter1 = OneBotAdapter(bot1)
    folders1 = asyncio.run(adapter1.get_group_file_root_folders("123456"))
    assert len(folders1) == 2
    assert folders1[0]["folder_id"] == "f_1"

    # 2. 顶层包含 folders 字段
    bot2 = MockBot(
        {
            "get_group_root_files": {
                "folders": [{"id": "f_3", "name": "图片"}],
            }
        }
    )
    adapter2 = OneBotAdapter(bot2)
    folders2 = asyncio.run(adapter2.get_group_file_root_folders("123456"))
    assert len(folders2) == 1
    assert folders2[0]["id"] == "f_3"


def test_adapter_create_group_file_folder_and_find():
    # 1. 创建群文件夹并从 data.folder_id 返回 ID
    bot = MockBot(
        {
            "create_group_file_folder": {
                "status": "ok",
                "data": {"folder_id": "f_created_123"},
            },
            "get_group_root_files": {
                "data": {
                    "folders": [
                        {"folder_id": "f_created_123", "folder_name": "新建归档"}
                    ]
                }
            },
        }
    )
    adapter = OneBotAdapter(bot)
    fid = asyncio.run(adapter.create_group_file_folder("123456", "新建归档"))
    assert fid == "f_created_123"

    # 2. find_or_create_folder 能够直接找到已有文件夹
    matched_id = asyncio.run(adapter.find_or_create_folder("123456", "新建归档"))
    assert matched_id == "f_created_123"


# ==========================================
# 9. 群信息与成员列表 data 结构解包测试
# ==========================================


def test_adapter_group_and_member_info_data_unboxing():
    bot = MockBot(
        {
            "get_group_info": {
                "status": "ok",
                "data": {
                    "group_id": 987654,
                    "group_name": "测试群聊",
                    "member_count": 42,
                },
            },
            "get_group_list": {
                "status": "ok",
                "data": [
                    {"group_id": 111, "group_name": "群1"},
                    {"group_id": 222, "group_name": "群2"},
                ],
            },
            "get_group_member_list": {
                "status": "ok",
                "data": [
                    {"user_id": 1001, "nickname": "Alice", "role": "admin"},
                    {"user_id": 1002, "nickname": "Bob", "role": "member"},
                ],
            },
            "get_group_member_info": {
                "status": "ok",
                "data": {
                    "user_id": 1001,
                    "nickname": "Alice",
                    "card": "管理员Alice",
                    "role": "admin",
                },
            },
        }
    )
    adapter = OneBotAdapter(bot)

    group_info = asyncio.run(adapter.get_group_info("987654"))
    assert group_info is not None
    assert group_info.group_name == "测试群聊"
    assert group_info.member_count == 42

    groups = asyncio.run(adapter.get_group_list())
    assert groups == ["111", "222"]

    members = asyncio.run(adapter.get_member_list("987654"))
    assert len(members) == 2
    assert members[0].user_id == "1001"
    assert members[0].nickname == "Alice"

    member_info = asyncio.run(adapter.get_member_info("987654", "1001"))
    assert member_info is not None
    assert member_info.card == "管理员Alice"


# ==========================================
# 10. 表情回应与禁言状态测试
# ==========================================


def test_adapter_set_reaction_success_and_mapping():
    bot = MockBot({"set_msg_emoji_like": {"status": "ok"}})
    adapter = OneBotAdapter(bot)

    ok = asyncio.run(
        adapter.set_reaction(
            group_id="123456",
            message_id="778899",
            emoji="analysis_started",
            is_add=True,
        )
    )
    assert ok is True
    assert len(bot.action_calls) == 1
    action, params = bot.action_calls[0]
    assert action == "set_msg_emoji_like"
    assert params["message_id"] == 778899
    assert params["emoji_id"] == "289"
    assert params["set"] is True


def test_adapter_concurrent_ensure_driver_deduplication():
    bot = MockBot({"get_version_info": {"app_name": "NapCat.Onebot"}})
    adapter = OneBotAdapter(bot)

    async def run_concurrent():
        drivers = await asyncio.gather(
            adapter._ensure_driver(),
            adapter._ensure_driver(),
            adapter._ensure_driver(),
            adapter._ensure_driver(),
        )
        return drivers

    drivers = asyncio.run(run_concurrent())
    assert len(drivers) == 4
    for d in drivers:
        assert isinstance(d, NapCatDriver)
    # 确保并发调用只触发了一次 get_version_info 调用
    version_calls = [c for c in bot.action_calls if c[0] == "get_version_info"]
    assert len(version_calls) == 1


def test_adapter_cold_start_mute_exception_recognition():
    # 验证标准驱动与 cold-start 下对 SnowLuma result=120 / rejected 异常识别
    adapter = OneBotAdapter(MockBot())
    exc_snowluma = RuntimeError("send group message rejected: result=120 err=")
    assert adapter._is_mute_exception(exc_snowluma) is True


# ==========================================
# 11. NapCat 流式上传与相册结构变体测试
# ==========================================


def test_napcat_driver_album_list_structure_variations():
    driver = NapCatDriver()

    # 1. 响应结构包含 data.albums 字段
    bot1 = MockBot(
        {
            "get_qun_album_list": {
                "status": "ok",
                "data": {
                    "albums": [{"album_id": "alb_var_1", "name": "变体相册1"}]
                },
            }
        }
    )
    albums1 = asyncio.run(driver.get_group_album_list(bot1, "123456"))
    assert len(albums1) == 1
    assert albums1[0]["album_id"] == "alb_var_1"

    # 2. 响应结构直接返回相册字典列表
    bot2 = MockBot(
        {
            "get_qun_album_list": [
                {"album_id": "alb_var_2", "album_name": "变体相册2"}
            ]
        }
    )
    albums2 = asyncio.run(driver.get_group_album_list(bot2, "123456"))
    assert len(albums2) == 1
    assert albums2[0]["album_id"] == "alb_var_2"

    # 3. get_qun_album_list 异常时回退到标准驱动的 get_group_album_list
    bot3 = MockBot(
        {
            "get_qun_album_list": RuntimeError("Action not found"),
            "get_group_album_list": {
                "status": "ok",
                "data": {
                    "album_list": [{"album_id": "alb_var_3", "name": "回退相册"}]
                },
            },
        }
    )
    albums3 = asyncio.run(driver.get_group_album_list(bot3, "123456"))
    assert len(albums3) == 1
    assert albums3[0]["album_id"] == "alb_var_3"


def test_napcat_upload_stream_file_success(tmp_path: Path):
    test_file = tmp_path / "test_report.png"
    test_file.write_bytes(b"dummy image data content" * 1000)

    bot = MockBot(
        {
            "upload_file_stream": {
                "status": "ok",
                "retcode": 0,
                "data": {"file_path": "/remote/temp/test_report.png"},
            }
        }
    )
    driver = NapCatDriver()
    remote_path = asyncio.run(driver.upload_stream_file(bot, test_file))
    assert remote_path == "/remote/temp/test_report.png"
    # 验证触发了分块上传动作以及最终 complete 上传调用
    actions = [call[0] for call in bot.action_calls]
    assert "upload_file_stream" in actions
    complete_call = [
        call[1]
        for call in bot.action_calls
        if call[0] == "upload_file_stream" and call[1].get("is_complete") is True
    ]
    assert len(complete_call) == 1


def test_napcat_upload_stream_file_invalid_file(tmp_path: Path):
    driver = NapCatDriver()
    bot = MockBot()

    # 不存在的文件
    assert (
        asyncio.run(
            driver.upload_stream_file(bot, tmp_path / "non_existent.png")
        )
        is None
    )

    # 空文件
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")
    assert asyncio.run(driver.upload_stream_file(bot, empty_file)) is None

