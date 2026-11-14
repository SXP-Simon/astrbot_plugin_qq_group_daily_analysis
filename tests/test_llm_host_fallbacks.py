"""继承 AstrBot 回退对话模型的回归测试（#297）。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from astrbot.api.provider import LLMResponse, Provider

from src.infrastructure.analysis.utils import llm_utils
from src.shared.trace_context import TraceContext
from src.utils.resilience import GlobalRateLimiter


@pytest.fixture(autouse=True)
def reset_request_state(monkeypatch):
    monkeypatch.setattr(llm_utils, "_circuit_breakers", {})
    monkeypatch.setattr(GlobalRateLimiter, "_instance", None)
    monkeypatch.setattr(GlobalRateLimiter, "_semaphore", None)
    monkeypatch.setattr(GlobalRateLimiter, "_max_concurrency", None)
    monkeypatch.setattr(llm_utils.random, "uniform", lambda *_: 0)


class Config:
    def __init__(self, *, primary="", specific="", retries=2, streaming=False):
        self.primary = primary
        self.specific = specific
        self.retries = retries
        self.streaming = streaming

    def get_llm_provider_id(self):
        return self.primary

    def get_topic_provider_id(self):
        return self.specific

    def get_llm_retries(self):
        return self.retries

    def get_llm_backoff(self):
        return 0

    def get_enable_streaming_llm_call(self):
        return self.streaming


class Context:
    def __init__(self, config, *, succeeds="backup-2", failures=None):
        self.get_config = Mock(return_value=config)
        self.get_current_chat_provider_id = AsyncMock(return_value="primary")
        self.providers = {
            pid: Mock(
                spec=Provider,
                provider_config={"id": pid, "model": pid, "timeout": 1},
                text_chat=AsyncMock(),
            )
            for pid in ("primary", "backup-1", "backup-2", "custom")
        }
        self.providers["primary"].meta = lambda: SimpleNamespace(id="primary")
        self.get_using_provider_async = AsyncMock(
            return_value=self.providers["primary"]
        )
        self.succeeds = succeeds
        self.failures = failures or {}
        self.calls = []

    def get_provider_by_id(self, provider_id):
        return self.providers.get(provider_id)

    async def llm_generate(self, **kwargs):
        self.calls.append(kwargs)
        pid = kwargs["chat_provider_id"]
        if pid in self.failures:
            raise RuntimeError(self.failures[pid])
        if pid != self.succeeds:
            raise RuntimeError("Error code: 429 - insufficient balance")
        return LLMResponse(role="assistant", completion_text="report")


@pytest.mark.parametrize("schema", ["legacy", "runner", "agent"])
@pytest.mark.parametrize("streaming", [False, True])
def test_inherited_chain_uses_session_config_and_preserves_request(
    schema, streaming, monkeypatch
):
    ids = ["primary", "backup-1", "backup-1", "missing", "embedding", "backup-2"]
    if schema == "legacy":
        host_config = {"provider_settings": {"fallback_chat_models": ids}}
    else:
        host_config = {
            "agent" if schema == "agent" else "agent_runner": {
                "config": {"model": {"fallback_provider_ids": ids}}
            }
        }
    ctx = Context(host_config)
    # 即使非对话模型恰好有同名方法，也不应被识别成宿主对话 Provider。
    ctx.providers["embedding"] = SimpleNamespace(text_chat=AsyncMock())
    cfg = Config(streaming=streaming)
    stream_calls = []

    async def stream(context, pid, kwargs):
        stream_calls.append(pid)
        return await context.llm_generate(**kwargs)

    monkeypatch.setattr(llm_utils, "_call_provider_stream", stream)
    response_format = {"type": "json_object"}

    async def scenario():
        with TraceContext(trace_id="host-fallback") as trace:
            result = await llm_utils.call_provider_with_retry(
                ctx,
                cfg,
                "summarize",
                umo="qq:GroupMessage:123",
                provider_id_key="topic_provider_id",
                provider_id="primary",
                system_prompt="system",
                response_format=response_format,
                extra_generate_kwargs={"temperature": 0.2},
            )
            assert result.completion_text == "report"
            attempts = trace.metadata["llm_attempts"]
            assert [a["is_fallback"] for a in attempts] == [
                False,
                False,
                True,
                True,
                True,
            ]
            assert attempts[-1]["provider_id"] == "backup-2"

    asyncio.run(scenario())
    expected = ["primary", "primary", "backup-1", "backup-1", "backup-2"]
    assert [call["chat_provider_id"] for call in ctx.calls] == expected
    assert stream_calls == (expected if streaming else [])
    ctx.get_config.assert_called_once_with(umo="qq:GroupMessage:123")
    assert all(
        call["prompt"] == "summarize"
        and call["system_prompt"] == "system"
        and call["response_format"] == response_format
        and call["temperature"] == 0.2
        for call in ctx.calls
    )


@pytest.mark.parametrize("umo", ["qq:GroupMessage:123", None])
def test_default_entry_without_task_key_inherits_fallbacks(umo):
    ctx = Context({"provider_settings": {"fallback_chat_models": ["backup-2"]}})
    result = asyncio.run(
        llm_utils.call_provider_with_retry(ctx, Config(retries=1), "report", umo=umo)
    )
    assert result.completion_text == "report"
    assert [c["chat_provider_id"] for c in ctx.calls] == ["primary", "backup-2"]
    ctx.get_config.assert_called_once_with(umo=umo)
    if umo is None:
        ctx.get_using_provider_async.assert_awaited_once()


@pytest.mark.parametrize("setting", ["main", "override"])
@pytest.mark.parametrize("initially_inherited", [False, True])
def test_inheritance_policy_is_fixed_while_request_is_running(
    setting, initially_inherited
):
    """等待响应时修改配置不影响本次继承资格，下次调用才采用新配置。"""
    initial_value = "" if initially_inherited else "primary"
    changed_value = "primary" if initially_inherited else ""
    cfg = Config(primary=initial_value if setting == "main" else "", retries=1)
    ctx = Context({"provider_settings": {"fallback_chat_models": ["backup-2"]}})

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        original_generate = ctx.llm_generate

        async def delayed_generate(**kwargs):
            if kwargs["chat_provider_id"] == "primary":
                started.set()
                await release.wait()
            return await original_generate(**kwargs)

        ctx.llm_generate = delayed_generate
        with TraceContext(trace_id="config-during-request") as trace:
            if setting == "override":
                trace.metadata["override_provider_id"] = initial_value
            task = asyncio.create_task(
                llm_utils.call_provider_with_retry(
                    ctx, cfg, "report", umo="group", provider_id_key="topic_provider_id"
                )
            )
            await asyncio.wait_for(started.wait(), timeout=1)
            # 只固定继承资格，宿主回退列表仍在首选模型失败后才读取。
            ctx.get_config.assert_not_called()
            if setting == "main":
                cfg.primary = changed_value
            else:
                trace.metadata["override_provider_id"] = changed_value
            release.set()
            result = await task
            assert (result is not None) == initially_inherited
            expected = ["primary", "backup-2"] if initially_inherited else ["primary"]
            assert [c["chat_provider_id"] for c in ctx.calls] == expected
            assert ctx.get_config.call_count == int(initially_inherited)

            # 新调用读取新配置，不将上次调用的继承资格缓存到全局。
            ctx.calls.clear()
            ctx.get_config.reset_mock()
            result = await llm_utils.call_provider_with_retry(
                ctx, cfg, "report", umo="group", provider_id_key="topic_provider_id"
            )
            assert (result is not None) != initially_inherited
            expected = ["primary"] if initially_inherited else ["primary", "backup-2"]
            assert [c["chat_provider_id"] for c in ctx.calls] == expected
            assert ctx.get_config.call_count == int(not initially_inherited)

    asyncio.run(scenario())


def test_primary_success_does_not_read_fallback_configuration():
    ctx = Context({}, succeeds="primary")
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx, Config(), "report", provider_id="primary"
        )
    )
    assert result.completion_text == "report"
    assert len(ctx.calls) == 1
    ctx.get_config.assert_not_called()


def test_explicit_plugin_primary_keeps_existing_fallback():
    ctx = Context({}, succeeds="primary")
    cfg = Config(primary="primary", specific="custom", retries=1)
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx, cfg, "report", provider_id_key="topic_provider_id"
        )
    )
    assert result.completion_text == "report"
    assert [c["chat_provider_id"] for c in ctx.calls] == ["custom", "primary"]
    ctx.get_config.assert_not_called()


def test_custom_task_falls_back_to_session_then_host_list():
    ctx = Context({"provider_settings": {"fallback_chat_models": ["backup-2"]}})
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx,
            Config(specific="custom", retries=1),
            "report",
            umo="group",
            provider_id_key="topic_provider_id",
        )
    )
    assert result.completion_text == "report"
    assert [c["chat_provider_id"] for c in ctx.calls] == [
        "custom",
        "primary",
        "backup-2",
    ]


def test_manual_override_does_not_append_host_models():
    ctx = Context({"provider_settings": {"fallback_chat_models": ["backup-2"]}})

    async def scenario():
        with TraceContext(trace_id="override") as trace:
            trace.metadata["override_provider_id"] = "custom"
            return await llm_utils.call_provider_with_retry(
                ctx,
                Config(retries=1),
                "report",
                umo="group",
                provider_id_key="topic_provider_id",
            )

    assert asyncio.run(scenario()) is None
    assert [c["chat_provider_id"] for c in ctx.calls] == ["custom"]
    ctx.get_config.assert_not_called()


@pytest.mark.parametrize(
    "host_config",
    [
        {},
        {
            "agent": {"config": {"model": {"fallback_provider_ids": []}}},
            "provider_settings": {"fallback_chat_models": ["backup-2"]},
        },
        {
            "agent_runner": {"config": {"model": {"fallback_provider_ids": []}}},
            "provider_settings": {"fallback_chat_models": ["backup-2"]},
        },
    ],
)
def test_missing_or_empty_current_list_does_not_revive_old_models(host_config):
    ctx = Context(host_config)
    assert (
        asyncio.run(
            llm_utils.call_provider_with_retry(
                ctx, Config(retries=1), "report", provider_id="primary"
            )
        )
        is None
    )
    assert [c["chat_provider_id"] for c in ctx.calls] == ["primary"]


def test_all_models_fail_with_bounded_retries():
    ctx = Context(
        {"provider_settings": {"fallback_chat_models": ["backup-1", "backup-2"]}},
        succeeds=None,
    )
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx, Config(), "report", provider_id="primary"
        )
    )
    assert result is None
    assert [c["chat_provider_id"] for c in ctx.calls] == [
        "primary",
        "primary",
        "backup-1",
        "backup-1",
        "backup-2",
        "backup-2",
    ]


def test_content_rejection_skips_retries_and_continues_entire_chain():
    ctx = Context(
        {"provider_settings": {"fallback_chat_models": ["backup-1", "backup-2"]}},
        failures={"primary": "content_filter", "backup-1": "content_filter"},
    )
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx, Config(), "report", provider_id="primary"
        )
    )
    assert result.completion_text == "report"
    assert [c["chat_provider_id"] for c in ctx.calls] == [
        "primary",
        "backup-1",
        "backup-2",
    ]


def test_schema_downgrade_is_reset_for_next_provider():
    ctx = Context(
        {"provider_settings": {"fallback_chat_models": ["backup-2"]}},
        failures={"primary": "response_format is not supported"},
    )
    schema = {"type": "json_object"}
    result = asyncio.run(
        llm_utils.call_provider_with_retry(
            ctx,
            Config(retries=1),
            "report",
            provider_id="primary",
            response_format=schema,
        )
    )
    assert result.completion_text == "report"
    assert [c.get("response_format") for c in ctx.calls] == [schema, None, schema]


def test_cancellation_does_not_try_fallbacks():
    ctx = Context({"provider_settings": {"fallback_chat_models": ["backup-2"]}})
    ctx.llm_generate = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            llm_utils.call_provider_with_retry(
                ctx, Config(), "report", provider_id="primary"
            )
        )
    ctx.llm_generate.assert_awaited_once()
    ctx.get_config.assert_not_called()
