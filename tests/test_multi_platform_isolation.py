"""Tests for strict multi-platform adapter matching and scheduler isolation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.platform.adapters.onebot_adapter import OneBotAdapter
from src.infrastructure.platform.bot_manager import BotManager
from src.infrastructure.scheduler.auto_scheduler import AutoScheduler


class FakeConfigManager:
    """Mock ConfigManager for testing scheduler and bot manager."""

    def __init__(self, whitelist: list[str] | None = None) -> None:
        self.whitelist = whitelist or ["*"]

    def get_filter_bot_messages(self) -> bool:
        return False

    def get_bot_self_ids(self) -> list[str]:
        return ["12345678"]

    def is_auto_analysis_enabled(self) -> bool:
        return True

    def is_scheduled_group_allowed(self, umo: str) -> bool:
        if "*" in self.whitelist:
            return True
        parts = umo.split(":")
        group_id = parts[-1] if len(parts) >= 3 else umo
        return umo in self.whitelist or group_id in self.whitelist

    def is_incremental_group_allowed(self, umo: str) -> bool:
        return False

    def get_incremental_enabled(self) -> bool:
        return False

    def get_max_concurrent_tasks(self) -> int:
        return 2

    def get_stagger_seconds(self) -> int:
        return 0

    def get_llm_max_concurrent(self) -> int:
        return 1

    def get_analysis_days(self) -> int:
        return 1


class FakePlatformMetadata:
    def __init__(self, platform_id: str, platform_type: str) -> None:
        self.id = platform_id
        self.type = platform_type
        self.name = platform_type


class FakePlatform:
    def __init__(self, platform_id: str, platform_type: str, client: Any) -> None:
        self.metadata = FakePlatformMetadata(platform_id, platform_type)
        self.client = client
        self.config = {"plugin_set": ["*"]}

    def get_client(self) -> Any:
        return self.client


def test_get_adapter_exact_and_case_insensitive_match():
    """Verify get_adapter precisely matches registered platform instance IDs."""
    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    mock_onebot_client = MagicMock()
    mock_onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        mock_onebot_client, platform_id="onebot_main", platform_name="aiocqhttp"
    )

    # 1. Exact match
    adapter = bot_mgr.get_adapter("onebot_main")
    assert adapter is not None
    assert isinstance(adapter, OneBotAdapter)
    assert bot_mgr.get_adapter_platform_id(adapter) == "onebot_main"

    # 2. Case-insensitive and trimmed whitespace match
    adapter_ci = bot_mgr.get_adapter("  ONEBOT_MAIN  ")
    assert adapter_ci is adapter

    # 3. Supports platform ID named 'default'
    bot_mgr.set_bot_instance(
        mock_onebot_client, platform_id="default", platform_name="aiocqhttp"
    )
    adapter_default = bot_mgr.get_adapter("default")
    assert adapter_default is not None
    assert bot_mgr.get_adapter_platform_id(adapter_default) == "default"


def test_get_adapter_protocol_type_match():
    """Verify get_adapter matches registered adapters by supported protocol type name."""
    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    mock_onebot_client = MagicMock()
    mock_onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        mock_onebot_client, platform_id="custom_qq_bot", platform_name="aiocqhttp"
    )

    # Matches by standard protocol names
    adapter_aiocq = bot_mgr.get_adapter("aiocqhttp")
    assert adapter_aiocq is not None
    assert isinstance(adapter_aiocq, OneBotAdapter)

    adapter_onebot = bot_mgr.get_adapter("onebot")
    assert adapter_onebot is adapter_aiocq


def test_get_adapter_rejects_unsupported_and_unknown_platforms():
    """Verify get_adapter strictly returns None for unsupported/unknown platforms without falling back."""
    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    mock_onebot_client = MagicMock()
    mock_onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        mock_onebot_client, platform_id="onebot_main", platform_name="aiocqhttp"
    )

    # Single OneBot adapter is active; querying other platforms MUST return None
    assert bot_mgr.get_adapter("lark-main") is None
    assert bot_mgr.get_adapter("lark") is None
    assert bot_mgr.get_adapter("feishu") is None
    assert bot_mgr.get_adapter("webchat") is None
    assert bot_mgr.get_adapter("slack") is None
    assert bot_mgr.get_adapter("non_existent_platform_id") is None


def test_get_adapter_rejects_empty_and_wildcard_placeholders():
    """Verify get_adapter strictly rejects empty or wildcard IDs (precise matching rule)."""
    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    mock_onebot_client = MagicMock()
    mock_onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        mock_onebot_client, platform_id="onebot_main", platform_name="aiocqhttp"
    )

    assert bot_mgr.get_adapter(None) is None
    assert bot_mgr.get_adapter("") is None
    assert bot_mgr.get_adapter("   ") is None
    assert bot_mgr.get_adapter("none") is None
    assert bot_mgr.get_adapter("null") is None
    assert bot_mgr.get_adapter("unknown_platform_id") is None


@pytest.mark.asyncio
async def test_auto_scheduler_multi_platform_scanning_isolation():
    """Verify AutoScheduler scans only supported platforms and prevents duplicate targets (#223)."""
    config_mgr = FakeConfigManager(whitelist=["10001", "10002", "10003"])
    bot_mgr = BotManager(config_mgr)

    # 1. Simulate AstrBot with 1 OneBot platform and 1 Lark platform
    onebot_client = MagicMock()
    onebot_client.call_action = AsyncMock()
    lark_client = MagicMock()  # Unsupported client without adapter support

    onebot_platform = FakePlatform("onebot_main", "aiocqhttp", onebot_client)
    lark_platform = FakePlatform("lark_main", "lark", lark_client)

    fake_context = MagicMock()
    fake_context.platform_manager = MagicMock()
    fake_context.platform_manager.get_insts.return_value = [
        onebot_platform,
        lark_platform,
    ]

    bot_mgr.set_context(fake_context)
    await bot_mgr.auto_discover_bot_instances()

    # Verify adapter creation status
    assert "onebot_main" in bot_mgr._adapters
    assert "lark_main" not in bot_mgr._adapters

    # Mock OneBotAdapter get_group_list
    onebot_adapter = bot_mgr.get_adapter("onebot_main")
    assert onebot_adapter is not None
    onebot_adapter.get_group_list = AsyncMock(
        return_value=["10001", "10002", "10003", "10004"]
    )

    # 2. Instantiate AutoScheduler and scan groups
    scheduler = AutoScheduler(
        config_manager=config_mgr,
        analysis_service=MagicMock(),
        bot_manager=bot_mgr,
    )

    all_groups = await scheduler._get_all_groups()

    # Verify that only OneBot groups are present
    assert len(all_groups) == 4
    for pid, gid in all_groups:
        assert pid == "onebot_main"
        assert pid != "lark_main"

    # 3. Resolve scheduled targets
    scheduled_targets = await scheduler._get_scheduled_targets()

    # Only 3 groups match the whitelist (10001, 10002, 10003), each should appear exactly once
    assert len(scheduled_targets) == 3
    target_groups = [t[0] for t in scheduled_targets]
    target_platforms = [t[1] for t in scheduled_targets]

    assert sorted(target_groups) == ["10001", "10002", "10003"]
    assert set(target_platforms) == {"onebot_main"}


@pytest.mark.asyncio
async def test_get_platform_id_for_group_validates_adapter_presence():
    """Verify get_platform_id_for_group precisely validates group existence via adapter."""
    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    onebot_client = MagicMock()
    onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        onebot_client, platform_id="onebot_main", platform_name="aiocqhttp"
    )

    adapter = bot_mgr.get_adapter("onebot_main")
    assert adapter is not None

    async def fake_get_group_info(group_id: str):
        if group_id == "valid_group":
            info = MagicMock()
            info.group_name = "Valid Group"
            return info
        return None

    adapter.get_group_info = AsyncMock(side_effect=fake_get_group_info)

    scheduler = AutoScheduler(
        config_manager=config_mgr,
        analysis_service=MagicMock(),
        bot_manager=bot_mgr,
    )

    # Valid group returns the verified platform ID
    pid = await scheduler.get_platform_id_for_group("valid_group")
    assert pid == "onebot_main"

    # Non-existent group returns None (no blind return of the 0th platform)
    unknown_pid = await scheduler.get_platform_id_for_group("non_existent_group")
    assert unknown_pid is None


@pytest.mark.asyncio
async def test_multiple_supported_platforms_scanning_and_routing():
    """Verify multiple supported platforms (e.g. 2 OneBot accounts) scan and route independently."""
    config_mgr = FakeConfigManager(whitelist=["*"])
    bot_mgr = BotManager(config_mgr)

    bot1_client = MagicMock()
    bot1_client.call_action = AsyncMock()
    bot2_client = MagicMock()
    bot2_client.call_action = AsyncMock()

    bot1_platform = FakePlatform("onebot_account_1", "aiocqhttp", bot1_client)
    bot2_platform = FakePlatform("onebot_account_2", "aiocqhttp", bot2_client)

    fake_context = MagicMock()
    fake_context.platform_manager = MagicMock()
    fake_context.platform_manager.get_insts.return_value = [
        bot1_platform,
        bot2_platform,
    ]

    bot_mgr.set_context(fake_context)
    await bot_mgr.auto_discover_bot_instances()

    adapter1 = bot_mgr.get_adapter("onebot_account_1")
    adapter2 = bot_mgr.get_adapter("onebot_account_2")

    assert adapter1 is not None
    assert adapter2 is not None
    assert adapter1 is not adapter2

    adapter1.get_group_list = AsyncMock(return_value=["101", "102"])
    adapter2.get_group_list = AsyncMock(return_value=["201", "202"])

    scheduler = AutoScheduler(
        config_manager=config_mgr,
        analysis_service=MagicMock(),
        bot_manager=bot_mgr,
    )

    all_groups = await scheduler._get_all_groups()
    assert len(all_groups) == 4
    assert ("onebot_account_1", "101") in all_groups
    assert ("onebot_account_1", "102") in all_groups
    assert ("onebot_account_2", "201") in all_groups
    assert ("onebot_account_2", "202") in all_groups


@pytest.mark.asyncio
async def test_analysis_service_rejects_unmatched_platform():
    """Verify AnalysisApplicationService raises ValueError when an unconfigured platform_id is passed."""
    from src.application.services.analysis_application_service import (
        AnalysisApplicationService,
    )

    config_mgr = FakeConfigManager()
    bot_mgr = BotManager(config_mgr)

    onebot_client = MagicMock()
    onebot_client.call_action = AsyncMock()
    bot_mgr.set_bot_instance(
        onebot_client, platform_id="onebot_main", platform_name="aiocqhttp"
    )

    service = AnalysisApplicationService(
        config_manager=config_mgr,
        bot_manager=bot_mgr,
        history_manager=MagicMock(),
        report_generator=None,
        llm_analyzer=MagicMock(),
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
    )

    with pytest.raises(ValueError, match="未找到平台 lark_main 的适配器"):
        await service.execute_daily_analysis("10001", platform_id="lark_main")

