"""
单元测试：main.py 中 GroupDailyAnalysis 主类的所有命令与事件监听器
包括: /群分析, /群漫画, /设置格式, /设置模板, /查看模板, /分析设置, /增量状态, 事件拦截及生命周期
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# 确保父路径在 sys.path 中以支持相对包导入
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(PLUGIN_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT.parent))

from astrbot_plugin_qq_group_daily_analysis.main import GroupDailyAnalysis
from astrbot_plugin_qq_group_daily_analysis.src.application.services.analysis_application_service import (
    DuplicateGroupTaskError,
)
from astrbot_plugin_qq_group_daily_analysis.src.shared.constants import PLUGIN_NAME


class FakeAstrBotConfig(dict):
    """支持 save_config 的模拟 AstrBotConfig"""

    def save_config(self):
        pass


class MockEvent:
    """模拟 AstrBot 消息事件"""

    def __init__(
        self,
        group_id: str | None = "123456",
        platform_id: str = "aiocqhttp_1",
        platform_name: str = "aiocqhttp",
        sender_id: str = "10001",
        sender_name: str = "TestUser",
        unified_msg_origin: str | None = None,
        message_id: str = "msg_999",
    ):
        self._group_id = group_id
        self._platform_id = platform_id
        self._platform_name = platform_name
        self._sender_id = sender_id
        self._sender_name = sender_name
        self.unified_msg_origin = (
            unified_msg_origin
            or (f"{platform_id}:GroupMessage:{group_id}" if group_id else None)
        )
        self.message_obj = SimpleNamespace(
            message_id=message_id,
            raw_message={},
        )
        self.platform_meta = SimpleNamespace(id=platform_id, name=platform_name)
        self._llm_called = False

    def get_group_id(self) -> str | None:
        return self._group_id

    def get_platform_id(self) -> str:
        return self._platform_id

    def get_platform_name(self) -> str:
        return self._platform_name

    def get_sender_id(self) -> str:
        return self._sender_id

    def get_sender_name(self) -> str:
        return self._sender_name

    def get_self_id(self) -> str:
        return "bot_10000"

    def should_call_llm(self, val: bool):
        self._llm_called = val

    def plain_result(self, text: str) -> dict:
        return {"type": "plain", "text": text}

    def chain_result(self, components: list) -> dict:
        return {"type": "chain", "components": components}


@pytest.fixture
def mock_context(tmp_path: Path):
    """创建模拟 Context 并配置 StarTools 数据目录"""
    ctx = MagicMock()
    with patch(
        "astrbot_plugin_qq_group_daily_analysis.main.StarTools.get_data_dir"
    ) as mock_get_dir:
        mock_get_dir.return_value = tmp_path / "plugin_data"
        yield ctx


@pytest.fixture
def default_config():
    """默认测试配置字典（分组结构）"""
    cfg = FakeAstrBotConfig(
        {
            "basic": {
                "group_list_mode": "whitelist",
                "group_list": ["123456", "aiocqhttp_1:GroupMessage:123456"],
                "output_format": ["image"],
                "report_template": "scrapbook",
                "auto_analysis": False,
                "auto_analysis_time": ["23:55"],
                "min_messages_threshold": 10,
                "filter_bot_messages": True,
                "analysis_days": 1,
                "enable_analysis_reply": True,
            },
            "daily_comic": {
                "enable_daily_comic": True,
                "comic_group_list": ["123456", "aiocqhttp_1:GroupMessage:123456"],
                "comic_group_list_mode": "whitelist",
                "comic_album_name": "漫画相册",
            },
            "incremental": {
                "incremental_group_list_mode": "whitelist",
                "incremental_group_list": [
                    "123456",
                    "aiocqhttp_1:GroupMessage:123456",
                ],
                "incremental_min_messages": 50,
                "incremental_report_immediately": False,
            },
            "upload": {
                "enable_group_file_upload": False,
                "enable_group_album_upload": False,
                "group_album_name": "群相册",
                "group_album_strict_mode": False,
                "group_file_folder": "日报",
            },
            "system": {
                "enable_analysis_reply": True,
                "llm_max_concurrent": 3,
                "t2i_max_concurrent": 2,
            },
        }
    )
    return cfg


@pytest.fixture
def plugin(mock_context, default_config, tmp_path: Path):
    """初始化 GroupDailyAnalysis 插件实例"""
    with patch(
        "astrbot_plugin_qq_group_daily_analysis.main.StarTools.get_data_dir",
        return_value=tmp_path / "plugin_data",
    ):
        p = GroupDailyAnalysis(mock_context, default_config)
        p.plugin_id = "astrbot_plugin_qq_group_daily_analysis"
        p.get_kv_data = AsyncMock(return_value={})
        p.put_kv_data = AsyncMock()
        p._initialized = True
        return p


# ==============================================================================
# 1. /群分析 (analyze_group_daily) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_analyze_group_daily_not_in_group(plugin):
    event = MockEvent(group_id=None)
    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    assert len(results) == 1
    assert "请在群聊中使用此命令" in results[0]["text"]


@pytest.mark.asyncio
async def test_analyze_group_daily_not_allowed(plugin):
    event = MockEvent(group_id="999999", unified_msg_origin="qq:GroupMessage:999999")
    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    assert len(results) == 1
    assert "此群未启用日常分析功能" in results[0]["text"]


@pytest.mark.asyncio
async def test_analyze_group_daily_success_image_flow(plugin):
    event = MockEvent(group_id="123456")

    mock_adapter = AsyncMock(
        get_platform_name=Mock(return_value="aiocqhttp"),
        get_user_avatar_url=AsyncMock(return_value=None),
        get_member_info=AsyncMock(return_value=None),
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name="测试群")),
        send_image=AsyncMock(return_value=True),
    )
    plugin.bot_manager.get_adapter = Mock(return_value=mock_adapter)

    mock_analysis_result = {
        "success": True,
        "group_id": "123456",
        "platform_id": "aiocqhttp_1",
        "analysis_result": {
            "topics": ["测试话题1"],
            "user_titles": [],
            "golden_quotes": [],
            "statistics": {},
        },
        "adapter": mock_adapter,
    }

    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        return_value=mock_analysis_result
    )
    plugin.report_generator.generate_image_report = AsyncMock(
        return_value=("file:///tmp/report.jpg", "<html></html>")
    )
    plugin.html_render = AsyncMock()

    with patch.object(plugin, "_save_report_to_history"):
        results = []
        async for res in plugin.analyze_group_daily(event):
            results.append(res)

        assert len(results) >= 1
        assert "正在启动分析引擎" in results[0]["text"]
        mock_adapter.send_image.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_group_daily_success_text_flow(plugin):
    plugin.config_manager.set_output_format(["text"])
    event = MockEvent(group_id="123456")

    mock_adapter = AsyncMock(
        get_platform_name=Mock(return_value="aiocqhttp"),
        send_text_report=AsyncMock(return_value=True),
        get_user_avatar_url=AsyncMock(return_value=None),
        get_member_info=AsyncMock(return_value=None),
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name="测试群")),
    )
    plugin.bot_manager.get_adapter = Mock(return_value=mock_adapter)

    mock_analysis_result = {
        "success": True,
        "group_id": "123456",
        "platform_id": "aiocqhttp_1",
        "analysis_result": {"topics": ["测试话题"]},
        "adapter": mock_adapter,
    }

    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        return_value=mock_analysis_result
    )
    plugin.report_generator.generate_text_report = Mock(
        return_value="今日群聊总结: 大家都聊得很开心"
    )

    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    mock_adapter.send_text_report.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_group_daily_no_messages(plugin):
    event = MockEvent(group_id="123456")
    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        return_value={"success": False, "reason": "no_messages"}
    )

    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    assert any("未找到足够的群聊记录" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_analyze_group_daily_llm_failed(plugin):
    event = MockEvent(group_id="123456")
    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        return_value={"success": False, "reason": "llm_analysis_failed"}
    )

    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    assert any("大模型文本分析失败" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_analyze_group_daily_duplicate_task(plugin):
    event = MockEvent(group_id="123456")
    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        side_effect=DuplicateGroupTaskError("Task already running")
    )

    results = []
    async for res in plugin.analyze_group_daily(event):
        results.append(res)

    assert any("该群的分析任务正在执行中" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_analyze_group_daily_reaction_mode(plugin):
    plugin.config_manager.set_enable_analysis_reply(False)
    event = MockEvent(group_id="123456", message_id="msg_001")

    mock_adapter = AsyncMock(
        get_platform_name=Mock(return_value="onebot"),
        set_reaction=AsyncMock(return_value=True),
        get_user_avatar_url=AsyncMock(return_value=None),
        get_member_info=AsyncMock(return_value=None),
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name="测试群")),
        send_image=AsyncMock(return_value=True),
    )
    plugin.bot_manager.get_adapter = Mock(return_value=mock_adapter)


    mock_analysis_result = {
        "success": True,
        "group_id": "123456",
        "platform_id": "aiocqhttp_1",
        "analysis_result": {"topics": []},
        "adapter": mock_adapter,
    }
    plugin.analysis_service.execute_daily_analysis = AsyncMock(
        return_value=mock_analysis_result
    )
    plugin.report_generator.generate_image_report = AsyncMock(
        return_value=("file:///tmp/rep.jpg", "<html></html>")
    )

    with patch.object(plugin, "_save_report_to_history"):
        results = []
        async for res in plugin.analyze_group_daily(event):
            results.append(res)

        mock_adapter.set_reaction.assert_any_call(
            "123456", "msg_001", "analysis_started"
        )
        mock_adapter.set_reaction.assert_any_call("123456", "msg_001", "analysis_done")


# ==============================================================================
# 2. /群漫画 (generate_group_comic) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_generate_group_comic_not_in_group(plugin):
    event = MockEvent(group_id=None)
    results = []
    async for res in plugin.generate_group_comic(event):
        results.append(res)

    assert len(results) == 1
    assert "请在群聊中使用此命令" in results[0]["text"]


@pytest.mark.asyncio
async def test_generate_group_comic_feature_disabled(plugin):
    plugin.config_manager._ensure_group("daily_comic")["enable_daily_comic"] = False
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.generate_group_comic(event):
        results.append(res)

    assert any("漫画生成功能未启用" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_generate_group_comic_group_not_allowed(plugin):
    plugin.config_manager._ensure_group("daily_comic")["comic_group_list"] = ["999999"]
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.generate_group_comic(event):
        results.append(res)

    assert any("此群未启用漫画生成功能" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_generate_group_comic_duplicate_task(plugin):
    event = MockEvent(group_id="123456")
    fake_task = Mock(done=Mock(return_value=False))
    plugin._comic_group_tasks["aiocqhttp_1:123456"] = fake_task

    results = []
    async for res in plugin.generate_group_comic(event):
        results.append(res)

    assert any("该群已有漫画任务正在执行" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_generate_group_comic_success_trigger(plugin):
    event = MockEvent(group_id="123456")
    plugin.analysis_service.execute_comic_topic_analysis = AsyncMock(
        return_value={"success": True, "topics": ["话题1", "话题2"]}
    )

    with patch.object(
        plugin, "_try_trigger_comic_generation", return_value="started"
    ) as mock_trigger:
        results = []
        async for res in plugin.generate_group_comic(event):
            results.append(res)

        mock_trigger.assert_called_once()
        assert any("漫画生成任务已启动" in r.get("text", "") for r in results)


# ==============================================================================
# 3. /设置格式 (set_output_format) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_set_output_format_query(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_output_format(event, format_input=""):
        results.append(res)

    assert len(results) == 1
    assert "当前输出格式: image" in results[0]["text"]
    assert "可用格式:" in results[0]["text"]


@pytest.mark.asyncio
async def test_set_output_format_by_index(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_output_format(event, format_input="2"):
        results.append(res)

    assert any("输出格式已设置为: text" in r.get("text", "") for r in results)
    assert plugin.config_manager.get_output_format() == ["text"]


@pytest.mark.asyncio
async def test_set_output_format_by_name(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_output_format(event, format_input="html"):
        results.append(res)

    assert any("输出格式已设置为: html" in r.get("text", "") for r in results)
    assert plugin.config_manager.get_output_format() == ["html"]


@pytest.mark.asyncio
async def test_set_output_format_multiple(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_output_format(event, format_input="image,text"):
        results.append(res)

    assert any("输出格式已设置为: image, text" in r.get("text", "") for r in results)
    assert plugin.config_manager.get_output_format() == ["image", "text"]


@pytest.mark.asyncio
async def test_set_output_format_invalid(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_output_format(event, format_input="pdf_invalid"):
        results.append(res)

    assert "无效的格式类型" in results[0]["text"]


# ==============================================================================
# 4. /设置模板 (set_report_template) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_set_report_template_query(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_report_template(event, template_input=""):
        results.append(res)

    assert len(results) == 1
    assert "当前报告模板:" in results[0]["text"]
    assert "可用模板:" in results[0]["text"]


@pytest.mark.asyncio
async def test_set_report_template_valid(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_report_template(event, template_input="ATRI"):
        results.append(res)

    assert any("报告模板已设置为: ATRI" in r.get("text", "") for r in results)
    assert plugin.config_manager.get_report_template() == "ATRI"


@pytest.mark.asyncio
async def test_set_report_template_invalid(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.set_report_template(
        event, template_input="non_existent_template"
    ):
        results.append(res)

    assert "不存在" in results[0]["text"] or "无法解析" in results[0]["text"]


# ==============================================================================
# 5. /查看模板 (view_templates) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_view_templates_default(plugin):
    event = MockEvent(group_id="123456")
    plugin.template_preview_router.handle_view_templates = AsyncMock(
        return_value=(False, [])
    )

    results = []
    async for res in plugin.view_templates(event):
        results.append(res)

    assert len(results) == 1
    assert results[0]["type"] == "chain"


@pytest.mark.asyncio
async def test_view_templates_router_handled(plugin):
    event = MockEvent(group_id="123456")
    plugin.template_preview_router.handle_view_templates = AsyncMock(
        return_value=(True, [{"type": "plain", "text": "Telegram preview keyboard"}])
    )

    results = []
    async for res in plugin.view_templates(event):
        results.append(res)

    assert len(results) == 1
    assert results[0]["text"] == "Telegram preview keyboard"


# ==============================================================================
# 6. /分析设置 (analysis_settings) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_analysis_settings_not_in_group(plugin):
    event = MockEvent(group_id=None)
    results = []
    async for res in plugin.analysis_settings(event, action="status"):
        results.append(res)

    assert "请在群聊中使用此命令" in results[0]["text"]


@pytest.mark.asyncio
async def test_analysis_settings_status(plugin):
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.analysis_settings(event, action="status"):
        results.append(res)

    assert any("当前群分析功能状态:" in r.get("text", "") for r in results)
    assert any("群分析功能:" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_analysis_settings_enable_and_disable_whitelist(plugin):
    event = MockEvent(group_id="777888", unified_msg_origin="qq:GroupMessage:777888")

    # 1. 启用
    results_enable = []
    async for res in plugin.analysis_settings(event, action="enable"):
        results_enable.append(res)
    assert any("已将当前群加入白名单" in r.get("text", "") for r in results_enable)

    # 2. 再次启用提示已在白名单
    results_enable_again = []
    async for res in plugin.analysis_settings(event, action="enable"):
        results_enable_again.append(res)
    assert any("已在白名单中" in r.get("text", "") for r in results_enable_again)

    # 3. 禁用
    results_disable = []
    async for res in plugin.analysis_settings(event, action="disable"):
        results_disable.append(res)
    assert any("已将当前群从白名单移除" in r.get("text", "") for r in results_disable)


@pytest.mark.asyncio
async def test_analysis_settings_enable_and_disable_blacklist(plugin):
    plugin.config_manager._ensure_group("basic")["group_list_mode"] = "blacklist"
    plugin.config_manager._ensure_group("basic")["group_list"] = []
    event = MockEvent(group_id="777888", unified_msg_origin="qq:GroupMessage:777888")

    # 1. 禁用 -> 加入黑名单
    results_disable = []
    async for res in plugin.analysis_settings(event, action="disable"):
        results_disable.append(res)
    assert any("已将当前群加入黑名单" in r.get("text", "") for r in results_disable)

    # 2. 启用 -> 从黑名单移除
    results_enable = []
    async for res in plugin.analysis_settings(event, action="enable"):
        results_enable.append(res)
    assert any("已将当前群从黑名单移除" in r.get("text", "") for r in results_enable)


@pytest.mark.asyncio
async def test_analysis_settings_reload(plugin):
    event = MockEvent(group_id="123456")
    plugin.auto_scheduler.schedule_jobs = Mock()
    plugin._refresh_incremental_target_states = AsyncMock()

    results = []
    async for res in plugin.analysis_settings(event, action="reload"):
        results.append(res)

    assert any("已重新加载配置并重启定时任务" in r.get("text", "") for r in results)
    plugin.auto_scheduler.schedule_jobs.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_settings_toggle_filter_bot(plugin):
    event = MockEvent(group_id="123456")
    orig_val = plugin.config_manager.get_filter_bot_messages()

    results = []
    async for res in plugin.analysis_settings(event, action="filter_bot"):
        results.append(res)

    new_val = plugin.config_manager.get_filter_bot_messages()
    assert new_val != orig_val


@pytest.mark.asyncio
async def test_analysis_settings_toggle_incremental_debug(plugin):
    event = MockEvent(group_id="123456")
    orig_val = plugin.config_manager.get_incremental_report_immediately()

    results = []
    async for res in plugin.analysis_settings(event, action="incremental_debug"):
        results.append(res)

    new_val = plugin.config_manager.get_incremental_report_immediately()
    assert new_val != orig_val


# ==============================================================================
# 7. /增量状态 (incremental_status) 单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_incremental_status_not_in_group(plugin):
    event = MockEvent(group_id=None)
    results = []
    async for res in plugin.incremental_status(event):
        results.append(res)

    assert "请在群聊中使用此命令" in results[0]["text"]


@pytest.mark.asyncio
async def test_incremental_status_disabled(plugin):
    plugin.config_manager._ensure_group("incremental")[
        "incremental_group_list"
    ] = []
    event = MockEvent(group_id="123456")
    results = []
    async for res in plugin.incremental_status(event):
        results.append(res)

    assert "增量分析模式未启用" in results[0]["text"]


@pytest.mark.asyncio
async def test_incremental_status_no_batches(plugin):
    event = MockEvent(group_id="123456")
    plugin.incremental_store.query_batches = AsyncMock(return_value=[])

    results = []
    async for res in plugin.incremental_status(event):
        results.append(res)

    assert any("尚无增量分析数据" in r.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_incremental_status_with_batches(plugin):
    event = MockEvent(group_id="123456")
    fake_batches = [
        SimpleNamespace(
            batch_id="b1",
            message_count=100,
            start_time=time.time() - 3600,
            end_time=time.time(),
        )
    ]
    plugin.incremental_store.query_batches = AsyncMock(return_value=fake_batches)

    mock_state = MagicMock()
    mock_state.get_summary.return_value = {
        "window": "最近24小时",
        "total_analyses": 1,
        "total_messages": 100,
        "topics_count": 3,
        "quotes_count": 2,
        "participants": 15,
        "peak_hours": "14:00-16:00",
    }
    plugin.incremental_merge_service.merge_batches = Mock(return_value=mock_state)

    results = []
    async for res in plugin.incremental_status(event):
        results.append(res)

    assert any("增量分析状态" in r.get("text", "") for r in results)
    assert any("累计消息: 100" in r.get("text", "") for r in results)
    assert any("话题数: 3" in r.get("text", "") for r in results)


# ==============================================================================
# 8. 事件监听器与生命周期单元测试
# ==============================================================================


@pytest.mark.asyncio
async def test_count_incremental_group_message_skips_qq_and_telegram(plugin):
    qq_event = MockEvent(platform_name="qq_official")
    tg_event = MockEvent(platform_name="telegram")
    other_event = MockEvent(platform_name="aiocqhttp")

    plugin.auto_scheduler.record_incremental_message = AsyncMock()

    await plugin.count_incremental_group_message(qq_event)
    await plugin.count_incremental_group_message(tg_event)
    assert plugin.auto_scheduler.record_incremental_message.call_count == 0

    await plugin.count_incremental_group_message(other_event)
    assert plugin.auto_scheduler.record_incremental_message.call_count == 1


@pytest.mark.asyncio
async def test_intercept_telegram_messages(plugin):
    event = MockEvent(platform_name="telegram", platform_id="tg_1")
    plugin.message_processing_service.process_message = AsyncMock(return_value=True)
    plugin.auto_scheduler.record_incremental_message = AsyncMock()

    await plugin.intercept_telegram_messages(event)

    plugin.message_processing_service.process_message.assert_called_once_with(event)
    plugin.auto_scheduler.record_incremental_message.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_intercept_qq_official_messages(plugin):
    event = MockEvent(
        platform_name="qq_official",
        platform_id="qq_official_1",
        sender_name="QQ用户A",
    )
    event.message_obj.raw_message = {
        "group_openid": "grp_openid_001",
        "author": {
            "member_openid": "mem_openid_001",
            "username": "QQ用户A",
            "avatar": "http://avatar/1.jpg",
        },
    }

    mock_adapter = MagicMock()
    mock_adapter.remember_user_profile = Mock()
    plugin.bot_manager.get_adapter = Mock(return_value=mock_adapter)
    plugin.message_processing_service.process_message = AsyncMock(return_value=True)
    plugin.auto_scheduler.record_incremental_message = AsyncMock()

    await plugin.intercept_qq_official_messages(event)

    mock_adapter.remember_user_profile.assert_called_once_with(
        "mem_openid_001", nickname="QQ用户A", avatar_url="http://avatar/1.jpg"
    )
    plugin.message_processing_service.process_message.assert_called_once_with(event)
    plugin.auto_scheduler.record_incremental_message.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_plugin_terminate(plugin):
    plugin.auto_scheduler.shutdown = AsyncMock()
    plugin.template_preview_router.unregister_handlers = AsyncMock()
    plugin.report_generator.close = AsyncMock()

    await plugin.terminate()

    assert plugin._terminating is True
    plugin.auto_scheduler.shutdown.assert_called_once()
    plugin.template_preview_router.unregister_handlers.assert_called_once()
    plugin.report_generator.close.assert_called_once()
