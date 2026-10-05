import functools
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter
from src.infrastructure.platform.adapters.telegram_adapter import TelegramAdapter
from src.infrastructure.platform.bot_manager import BotManager


@pytest.fixture
def mock_config_manager():
    cfg = Mock()
    cfg.get_filter_bot_messages.return_value = True
    cfg.get_bot_self_ids.return_value = ["111222333"]
    return cfg


# ==========================================
# 1. 跨平台 Bot 自身 ID 提取逻辑测试
# ==========================================


def test_extract_bot_self_id_direct_attributes(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # OneBot direct self_id
    bot_onebot = SimpleNamespace(self_id="10001")
    assert bm._extract_bot_self_id(bot_onebot) == "10001"

    # Numeric user_id
    bot_user_id = SimpleNamespace(user_id=20002)
    assert bm._extract_bot_self_id(bot_user_id) == "20002"

    # Telegram / Generic id
    bot_id = SimpleNamespace(id=30003)
    assert bm._extract_bot_self_id(bot_id) == "30003"


def test_extract_bot_self_id_nested_discord_user(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Discord client.user.id
    bot_discord = SimpleNamespace(user=SimpleNamespace(id=999888777))
    assert bm._extract_bot_self_id(bot_discord) == "999888777"


def test_extract_bot_self_id_telegram_token_prefix(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Telegram token prefix: <bot_id>:<secret>
    bot_tg = SimpleNamespace(token="987654321:AAEklnasdf897asdf")
    assert bm._extract_bot_self_id(bot_tg) == "987654321"

    # Invalid token formats
    bot_invalid_1 = SimpleNamespace(token="invalid_token_no_colon")
    assert bm._extract_bot_self_id(bot_invalid_1) is None

    bot_invalid_2 = SimpleNamespace(token="not_digits:token_secret")
    assert bm._extract_bot_self_id(bot_invalid_2) is None


def test_extract_bot_self_id_property_exception_handling(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Simulate uninitialized python-telegram-bot ExtBot.id raising RuntimeError
    class UninitializedBot:
        @property
        def id(self):
            raise RuntimeError("Bot not initialized")

        @property
        def user(self):
            raise RuntimeError("User not initialized")

        token = "55667788:SecretToken"

    bot = UninitializedBot()
    # Should safely catch RuntimeError and fall back to token prefix
    assert bm._extract_bot_self_id(bot) == "55667788"


def test_extract_bot_self_id_callable_and_partial_guards(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Aiocqhttp dynamic proxy might return callable or partial
    bot_callable = SimpleNamespace(self_id=lambda: "12345")
    assert bm._extract_bot_self_id(bot_callable) is None

    bot_partial = SimpleNamespace(
        self_id=functools.partial(lambda x: x, "dynamic_proxy")
    )
    assert bm._extract_bot_self_id(bot_partial) is None


# ==========================================
# 2. 适配器生命周期与状态保持测试
# ==========================================


def test_set_bot_instance_state_preservation(mock_config_manager):
    bm = BotManager(mock_config_manager)
    bot = Mock()
    bot.call_action = Mock()
    bot.self_id = "12345"

    bm.set_bot_instance(bot, platform_id="aiocqhttp_1", platform_name="aiocqhttp")
    adapter1 = bm.get_adapter("aiocqhttp_1")
    assert adapter1 is not None

    # Setting identical instance must preserve existing adapter instance (no re-creation)
    bm.set_bot_instance(bot, platform_id="aiocqhttp_1", platform_name="aiocqhttp")
    adapter2 = bm.get_adapter("aiocqhttp_1")
    assert adapter1 is adapter2


def test_set_bot_instance_qq_official_appid(mock_config_manager):
    bm = BotManager(mock_config_manager)
    bm._platforms["official_1"] = SimpleNamespace(config={"appid": "10203040"})

    bot = SimpleNamespace(platform="qq_official")
    bm.set_bot_instance(bot, platform_id="official_1", platform_name="qq_official")

    adapter = bm.get_adapter("official_1")
    assert adapter is not None
    assert getattr(adapter, "appid", None) == "10203040"


def test_set_bot_self_ids_synchronization(mock_config_manager):
    bm = BotManager(mock_config_manager)
    bot = Mock()
    bot.call_action = Mock()
    bm.set_bot_instance(bot, platform_id="aiocqhttp_1", platform_name="aiocqhttp")

    adapter = bm.get_adapter("aiocqhttp_1")
    bm.set_bot_self_ids(["999", "888"])
    assert bm._bot_self_ids == ["999", "888"]
    assert adapter.bot_self_ids == ["999", "888"]


# ==========================================
# 3. 适配器检索与平台 ID 解析测试
# ==========================================


def test_get_adapter_resolution_modes(mock_config_manager):
    bm = BotManager(mock_config_manager)
    onebot = Mock()
    onebot.call_action = Mock()
    tg_bot = SimpleNamespace(token="12345:token")

    bm.set_bot_instance(onebot, platform_id="my_cqhttp", platform_name="aiocqhttp")
    bm.set_bot_instance(tg_bot, platform_id="my_tg", platform_name="telegram")

    # 1. Exact match
    assert isinstance(bm.get_adapter("my_cqhttp"), OneBotAdapter)
    assert isinstance(bm.get_adapter("my_tg"), TelegramAdapter)

    # 2. Case and whitespace insensitive match
    assert isinstance(bm.get_adapter("  MY_CQHTTP  "), OneBotAdapter)
    assert isinstance(bm.get_adapter("MY_TG"), TelegramAdapter)

    # 3. Protocol type alias matching
    assert isinstance(bm.get_adapter("aiocqhttp"), OneBotAdapter)
    assert isinstance(bm.get_adapter("telegram"), TelegramAdapter)

    # 4. Unmatched or empty
    assert bm.get_adapter("non_existent") is None
    assert bm.get_adapter("") is None
    assert bm.get_adapter(None) is None


def test_get_adapter_platform_id(mock_config_manager):
    bm = BotManager(mock_config_manager)
    bot = Mock()
    bot.call_action = Mock()
    bm.set_bot_instance(bot, platform_id="custom_platform_id", platform_name="aiocqhttp")

    adapter = bm.get_adapter("custom_platform_id")
    assert bm.get_adapter_platform_id(adapter) == "custom_platform_id"
    assert bm.get_adapter_platform_id(None) == ""


# ==========================================
# 4. 自动发现平台与懒加载测试
# ==========================================


@pytest.mark.asyncio
async def test_auto_discover_bot_instances(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Mock ready platform
    ready_bot = Mock()
    ready_bot.call_action = Mock()
    platform_ready = SimpleNamespace(
        get_client=lambda: ready_bot,
        metadata=SimpleNamespace(id="cq_ready", type="aiocqhttp", name="aiocqhttp"),
    )

    # Mock lazy platform (client is not ready yet)
    platform_lazy = SimpleNamespace(
        get_client=lambda: None,
        bot=None,
        client=None,
        metadata={"id": "lazy_plat", "type": "discord", "name": "discord"},
    )

    context = SimpleNamespace(
        platform_manager=SimpleNamespace(
            get_insts=lambda: [platform_ready, platform_lazy]
        )
    )
    bm.set_context(context)

    discovered = await bm.auto_discover_bot_instances()
    assert "cq_ready" in discovered
    assert "lazy_plat" in discovered
    assert bm.has_adapter("cq_ready") is True
    assert bm.has_adapter("lazy_plat") is False

    # Simulate lazy platform becoming ready later
    discord_bot = SimpleNamespace(user=SimpleNamespace(id=667788))
    platform_lazy.client = discord_bot
    bm._refresh_from_stored_platforms()
    assert bm.has_adapter("lazy_plat") is True


# ==========================================
# 5. 插件启用检查与消息过滤测试
# ==========================================


def test_is_plugin_enabled(mock_config_manager):
    bm = BotManager(mock_config_manager)

    # Platform not registered -> defaults to enabled
    assert bm.is_plugin_enabled("unknown_plat", "any_plugin") is True

    # Wildcard config
    bm._platforms["p_wildcard"] = SimpleNamespace(config={"plugin_set": ["*"]})
    assert bm.is_plugin_enabled("p_wildcard", "qq_group_daily_analysis") is True

    # Disabled config (plugin_set is None)
    bm._platforms["p_disabled"] = SimpleNamespace(config={"plugin_set": None})
    assert bm.is_plugin_enabled("p_disabled", "qq_group_daily_analysis") is False

    # Whitelist config
    bm._platforms["p_whitelist"] = SimpleNamespace(
        config={"plugin_set": ["qq_group_daily_analysis", "other_plugin"]}
    )
    assert bm.is_plugin_enabled("p_whitelist", "qq_group_daily_analysis") is True
    assert bm.is_plugin_enabled("p_whitelist", "disallowed_plugin") is False


def test_is_plugin_enabled_with_acm_multi_profile(mock_config_manager):
    """验证通过 AstrBot 核心 AstrBotConfigManager (ACM) 进行多配置文件与 UMO 路由鉴权。"""
    bm = BotManager(mock_config_manager)

    class FakeACM:
        def __init__(self):
            self.confs = {
                "default": {"plugin_set": ["*"]},
                "atri_profile_2": {"plugin_set": ["astrbot_plugin_chat_history"]},
                "custom_group_profile": {
                    "plugin_set": ["astrbot_plugin_qq_group_daily_analysis"]
                },
            }

        def get_conf(self, umo: str | None) -> dict:
            if not umo:
                return self.confs["default"]
            if umo.startswith("qq_bot_2:"):
                # 机器人2号绑定了 atri_profile_2
                return self.confs["atri_profile_2"]
            if umo == "qq_bot_1:GroupMessage:999":
                # 群999单独配置
                return self.confs["custom_group_profile"]
            return self.confs["default"]

    fake_context = SimpleNamespace(astrbot_config_mgr=FakeACM())
    bm.set_context(fake_context)

    # 1. 默认机器人 (qq_bot_1) 启用了所有插件
    assert bm.is_plugin_enabled("qq_bot_1", "astrbot_plugin_qq_group_daily_analysis") is True
    assert (
        bm.is_plugin_enabled(
            "qq_bot_1", "astrbot_plugin_qq_group_daily_analysis", group_id="123"
        )
        is True
    )

    # 2. 机器人2号 (qq_bot_2 / 亚托莉2号) 未开启该插件
    assert (
        bm.is_plugin_enabled("qq_bot_2", "astrbot_plugin_qq_group_daily_analysis") is False
    )
    assert (
        bm.is_plugin_enabled(
            "qq_bot_2", "astrbot_plugin_qq_group_daily_analysis", group_id="123"
        )
        is False
    )

    # 3. 群级会话精准路由覆盖
    assert (
        bm.is_plugin_enabled(
            "qq_bot_1", "astrbot_plugin_qq_group_daily_analysis", group_id="999"
        )
        is True
    )


def test_is_plugin_enabled_various_data_types(mock_config_manager):
    """测试 plugin_set 支持 tuple, set, 大小写不敏感及空配置。"""
    bm = BotManager(mock_config_manager)

    # tuple
    bm._platforms["p_tuple"] = SimpleNamespace(
        config={"plugin_set": ("astrbot_plugin_qq_group_daily_analysis",)}
    )
    assert bm.is_plugin_enabled("p_tuple", "astrbot_plugin_qq_group_daily_analysis") is True

    # set
    bm._platforms["p_set"] = SimpleNamespace(
        config={"plugin_set": {"astrbot_plugin_qq_group_daily_analysis"}}
    )
    assert bm.is_plugin_enabled("p_set", "astrbot_plugin_qq_group_daily_analysis") is True

    # Case-insensitive match
    bm._platforms["p_case"] = SimpleNamespace(
        config={"plugin_set": ["ASTRBOT_PLUGIN_QQ_GROUP_DAILY_ANALYSIS"]}
    )
    assert (
        bm.is_plugin_enabled("p_case", "astrbot_plugin_qq_group_daily_analysis") is True
    )

    # Wildcard prefix patterns
    bm._platforms["p_wildcard_prefix"] = SimpleNamespace(
        config={"plugin_set": ["astrbot_plugin_*"]}
    )
    assert (
        bm.is_plugin_enabled("p_wildcard_prefix", "astrbot_plugin_qq_group_daily_analysis")
        is True
    )
    assert (
        bm.is_plugin_enabled("p_wildcard_prefix", "other_plugin")
        is False
    )

    # Wildcard substring patterns
    bm._platforms["p_wildcard_sub"] = SimpleNamespace(
        config={"plugin_set": ["*group_daily*"]}
    )
    assert (
        bm.is_plugin_enabled("p_wildcard_sub", "astrbot_plugin_qq_group_daily_analysis")
        is True
    )

    # Empty list (disabled all)
    bm._platforms["p_empty"] = SimpleNamespace(config={"plugin_set": []})
    assert (
        bm.is_plugin_enabled("p_empty", "astrbot_plugin_qq_group_daily_analysis") is False
    )


def test_should_filter_bot_message(mock_config_manager):
    bm = BotManager(mock_config_manager)
    bm.set_bot_self_ids(["12345", "67890"])

    assert bm.should_filter_bot_message("12345") is True
    assert bm.should_filter_bot_message(67890) is True
    assert bm.should_filter_bot_message("11111") is False


# ==========================================
# 6. 从事件更新 Bot 实例测试
# ==========================================


def test_update_from_event(mock_config_manager):
    bm = BotManager(mock_config_manager)

    event = MagicMock()
    bot = Mock()
    bot.call_action = Mock()
    bot.self_id = "54321"
    event.bot = bot
    event.get_platform_id.return_value = "event_platform_1"
    event.get_self_id.return_value = "54321"

    ok = bm.update_from_event(event)
    assert ok is True
    assert "event_platform_1" in bm.get_platform_ids()
    assert bm.should_filter_bot_message("54321") is True


def test_is_plugin_enabled_deduplicated_logging_and_fifo_cache(
    mock_config_manager, monkeypatch
):
    """验证鉴权日志去重输出机制与 FIFO 淘汰防内存膨胀。"""
    bm = BotManager(mock_config_manager)
    bm.MAX_AUTH_LOG_CACHE_SIZE = 3  # 缩小上限以便测试 FIFO 淘汰

    log_records = []
    monkeypatch.setattr(
        "src.infrastructure.platform.bot_manager.logger.debug",
        lambda msg: log_records.append(msg),
    )

    # 1. 首次调用 -> 记录日志并写入缓存
    assert bm.is_plugin_enabled("p1", "plugin_a", group_id="1001") is True
    assert len(log_records) == 1
    assert "[BotManager鉴权]" in log_records[0]
    assert "生效规则: 未设置插件限制规则 (缺省默认启用)" in log_records[0]

    # 2. 第二次相同目标相同规则 -> 静默，不再产生日志
    assert bm.is_plugin_enabled("p1", "plugin_a", group_id="1001") is True
    assert len(log_records) == 1

    # 3. 填入其他群组填满缓存并触发 FIFO 淘汰
    bm.is_plugin_enabled("p2", "plugin_a", group_id="1002")  # 2nd
    bm.is_plugin_enabled("p3", "plugin_a", group_id="1003")  # 3rd
    assert len(log_records) == 3
    assert len(bm._auth_log_cache) == 3

    # 第 4 个加入，使最旧的 p1/1001 被逐出
    bm.is_plugin_enabled("p4", "plugin_a", group_id="1004")  # 4th
    assert len(log_records) == 4
    assert len(bm._auth_log_cache) == 3
    assert "平台 'p1' / 群 '1001'::plugin_a" not in bm._auth_log_cache

    # 再次访问 p1/1001，由于已被逐出，会重新触发一次日志记录
    bm.is_plugin_enabled("p1", "plugin_a", group_id="1001")
    assert len(log_records) == 5

