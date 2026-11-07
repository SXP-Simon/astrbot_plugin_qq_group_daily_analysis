"""验证日志的功能分类、冲突优先级与查询接口。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.infrastructure.logging.plugin_log_buffer import PluginLogBuffer


@pytest.mark.parametrize("filename,tag", [
    ("typst_renderer.py", "Typst"),
    ("custom_t2i_client.py", "T2I"),
    ("image_rendering.py", "T2I"),
    ("typst_fonts.py", "Resources"),
    ("template_resources.py", "Resources"),
    ("avatar_service.py", "Resources"),
    ("config_migrator.py", "Config"),
    ("config_routes.py", "Config"),
    ("checkpoint_store.py", "Storage"),
    ("incremental_store.py", "Storage"),
    ("history_repository.py", "Storage"),
    ("message_processing_service.py", "Messages"),
    ("incremental_analysis_service.py", "Incremental"),
    ("incremental_trigger.py", "Incremental"),
    ("analysis_recovery_service.py", "Tasks"),
    ("active_task_manager.py", "Tasks"),
    ("message_sender.py", "Dispatch"),
    ("group_file_manager.py", "Dispatch"),
    ("satori_adapter.py", "Satori"),
    ("discord_adapter.py", "Discord"),
    ("telegram_message_converter.py", "Telegram"),
    ("qq_official_adapter.py", "QQOfficial"),
    ("napcat_driver.py", "OneBot"),
    ("bot_manager.py", "Platform"),
    ("auto_scheduler.py", "Scheduler"),
    ("task_guard.py", "Resilience"),
    ("comic_analyzer.py", "Comic"),
    ("llm_analyzer.py", "LLM"),
    ("trace_context.py", "Trace"),
    ("generators.py", "Render"),
    ("plugin_page_bridge.py", "WebUI"),
])
def test_source_category_wins_over_incidental_message_words(filename, tag):
    buffer = PluginLogBuffer()
    entry = buffer.record_log("WARNING", "请求失败：token image guild retry", location=f"{filename}:42")
    assert entry.tag == tag
    assert buffer.query(tag=tag.lower())[1] == 1
    assert buffer.query(tag="General") == ([], 0)


@pytest.mark.parametrize("message,tag", [
    ("Typst 编译失败", "Typst"), ("T2I 服务超时", "T2I"),
    ("标题字体下载完成", "Resources"), ("配置备份完成", "Config"),
    ("SQLite 保存检查点失败", "Storage"), ("消息清洗完成", "Messages"),
    ("增量分析完成", "Incremental"), ("任务取消", "Tasks"),
    ("发送报告成功", "Dispatch"), ("[Satori] guild.get 失败", "Satori"),
    ("Discord guild 请求失败", "Discord"), ("未知来源启动完成", "General"),
    ("clock ready", "General"),
])
def test_legacy_logs_keep_keyword_fallback(message, tag):
    assert PluginLogBuffer().record_log("INFO", message).tag == tag


def test_trace_prefix_does_not_turn_group_name_into_category():
    buffer = PluginLogBuffer()
    entry = buffer.record_log("INFO", "[manual_typst_123] [群分析插件] 启动完成", trace_id="manual_typst_123")
    assert entry.tag == "General"
    assert entry.trace_id == "manual_typst_123"
    assert entry.message == "[群分析插件] 启动完成"
    assert buffer.record_log("INFO", "启动", logger_name="plugin.typst_renderer").tag == "Typst"
    assert buffer.record_log("INFO", "启动", location="C:/plugin/typst_renderer.py:20").tag == "Typst"


@pytest.mark.asyncio
async def test_log_api_offers_every_source_category_and_filters_streamed_entries(monkeypatch):
    from src.infrastructure.webui.routes import log_routes

    buffer = PluginLogBuffer()
    streamed = []
    buffer.register_listener(streamed.append)
    entry = buffer.record_log("INFO", "排版完成", location="typst_renderer.py:42")
    buffer.record_log("INFO", "启动完成")
    monkeypatch.setattr(log_routes, "global_log_buffer", buffer)
    monkeypatch.setattr(log_routes, "request", SimpleNamespace(query={"tag": "Typst"}))
    monkeypatch.setattr(log_routes, "json_response", lambda data: data)
    result = await log_routes.LogRoutes(MagicMock()).api_get_plugin_logs()
    data = result["data"]
    tags = {tag["key"] for tag in data["available_tags"]}
    assert tags >= set(buffer.SOURCE_TAGS) | {"General"}
    assert len(tags) == len(data["available_tags"])
    assert data["total"] == 1 and data["items"] == [entry.to_dict()]
    assert streamed[0].tag == "Typst"
