"""分析日志的用户摘要、重试诊断与故障可见性。"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot.api.provider import LLMResponse

from src.infrastructure.analysis.analyzers.topic_analyzer import TopicAnalyzer
from src.infrastructure.analysis.utils import llm_utils
from src.infrastructure.config.config_manager import ConfigManager
from src.utils.resilience import GlobalRateLimiter


@pytest.fixture
def llm_setup(monkeypatch, caplog):
    """使用真实配置读取和请求编排，只替换宿主 Provider。"""
    monkeypatch.setattr(llm_utils, "_circuit_breakers", {})
    monkeypatch.setattr(GlobalRateLimiter, "_instance", None)
    monkeypatch.setattr(GlobalRateLimiter, "_semaphore", None)
    monkeypatch.setattr(GlobalRateLimiter, "_max_concurrency", None)
    monkeypatch.setattr(llm_utils.random, "uniform", lambda *_: 0)
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    config = object.__new__(ConfigManager)
    config.config = {"llm": {"topic_provider_id": "primary", "llm_provider_id": "backup", "llm_retries": 1, "llm_backoff": 0}}
    providers = {
        pid: SimpleNamespace(provider_config={"model": f"{pid}-model"})
        for pid in ("primary", "backup")
    }
    context = SimpleNamespace(
        get_provider_by_id=lambda provider_id: providers.get(provider_id),
        llm_generate=AsyncMock(return_value=LLMResponse(completion_text="ok")),
    )
    return config, context


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_success_logs_one_request_summary_and_keeps_details_at_debug(llm_setup, monkeypatch, caplog, streaming):
    config, context = llm_setup
    config.config["llm"]["enable_streaming_llm_call"] = streaming
    if streaming:
        monkeypatch.setattr(llm_utils, "_call_provider_stream", context.llm_generate)
    result = await llm_utils.call_provider_with_retry(context, config, "hello", provider_id_key="topic_provider_id", observation_label="话题")
    assert result.completion_text == "ok"
    info = [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]
    assert len(info) == 1
    assert "话题 | Provider: primary | 模型: primary-model" in info[0]
    debug = "\n".join(record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG)
    assert "回退策略顺序" in debug
    assert "LLM 超时配置" in debug
    assert "Provider 请求完成" in debug


@pytest.mark.asyncio
async def test_retries_keep_one_summary_but_failures_are_warnings(llm_setup, caplog):
    config, context = llm_setup
    config.config["llm"]["llm_retries"] = 2
    context.llm_generate.side_effect = [RuntimeError("temporary failure"), LLMResponse(completion_text="ok")]
    assert await llm_utils.call_provider_with_retry(context, config, "hello", provider_id_key="topic_provider_id")
    assert context.llm_generate.await_count == 2
    assert len([r for r in caplog.records if r.levelno == logging.INFO]) == 1
    assert any(r.levelno == logging.WARNING and "temporary failure" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_actual_fallback_keeps_provider_and_model_visible_as_warning(llm_setup, caplog):
    config, context = llm_setup
    context.llm_generate.side_effect = [RuntimeError("primary unavailable"), LLMResponse(completion_text="backup result")]
    result = await llm_utils.call_provider_with_retry(context, config, "hello", provider_id_key="topic_provider_id", observation_label="话题")
    assert result.completion_text == "backup result"
    warnings = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert "primary unavailable" in warnings
    assert "Provider: backup | 模型: backup-model | 已切换备用 Provider" in warnings
    assert len([r for r in caplog.records if r.levelno == logging.INFO]) == 1


@pytest.mark.asyncio
async def test_missing_configured_provider_is_not_silent(llm_setup, caplog):
    config, context = llm_setup
    config.config["llm"]["topic_provider_id"] = "missing"
    assert await llm_utils.call_provider_with_retry(context, config, "hello", provider_id_key="topic_provider_id")
    assert any(r.levelno == logging.WARNING and "missing" in r.getMessage() for r in caplog.records)
    assert context.llm_generate.await_args.kwargs["chat_provider_id"] == "backup"


@pytest.mark.asyncio
async def test_timeout_and_final_failure_remain_errors(llm_setup, monkeypatch, caplog):
    config, context = llm_setup
    config.config["llm"]["llm_provider_id"] = "primary"
    monkeypatch.setattr(llm_utils.ProviderMetadata, "from_provider_id", lambda *_: llm_utils.ProviderMetadata("primary", "primary-model", "test", 0.01))

    async def blocked(**_):
        await asyncio.Event().wait()

    context.llm_generate.side_effect = blocked
    assert await llm_utils.call_provider_with_retry(context, config, "hello", provider_id_key="topic_provider_id") is None
    errors = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert "硬超时截断" in errors
    assert "最终失败" in errors


@pytest.mark.asyncio
async def test_analyzer_keeps_result_count_without_prompt_and_parse_noise(llm_setup, monkeypatch, caplog):
    config, context = llm_setup
    context.llm_generate.return_value = LLMResponse(completion_text='[{"topic":"测试话题","detail":"测试内容","contributors":["甲"]}]')
    analyzer = TopicAnalyzer(context, config)
    monkeypatch.setattr(config, "get_topic_analysis_prompt", lambda: "请提取 ${max_topics} 个话题：${messages_text}")
    monkeypatch.setattr(analyzer, "_build_system_prompt", AsyncMock(return_value="测试人格"))
    messages = [{"sender": {"user_id": "1", "nickname": "甲"}, "time": 0, "message": [{"type": "text", "data": {"text": "今天讨论一个测试话题"}}]}]
    topics, _ = await analyzer.analyze(messages)
    assert len(topics) == 1
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert len(info) == 2
    assert any("话题分析成功，解析到 1 条数据" in message for message in info)
    assert any("Provider: primary | 模型: primary-model" in message for message in info)
    debug = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG)
    assert "已启用人格设定" in debug
    assert "直接解析成功" in debug
