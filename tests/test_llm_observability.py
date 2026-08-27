import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from astrbot.api.provider import LLMResponse

from src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from src.domain.models.data_models import TokenUsage
from src.domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.infrastructure.analysis.utils import llm_utils
from src.infrastructure.analysis.utils.llm_utils import call_provider_with_retry
from src.shared.trace_context import TraceContext
from src.utils.resilience import GlobalRateLimiter


def _reset_global_limiter():
    """重置全局限流器，避免测试之间共享信号量状态。"""
    GlobalRateLimiter._instance = None
    GlobalRateLimiter._semaphore = None
    GlobalRateLimiter._max_concurrency = None


def test_global_rate_limiter_keeps_configured_limit_when_slot_is_busy():
    """忙碌中的信号量不应因为可用槽位变化而被误判为需要重建。"""

    async def scenario():
        _reset_global_limiter()
        limiter = GlobalRateLimiter.get_instance(2)
        semaphore = limiter.semaphore
        await semaphore.acquire()
        try:
            assert limiter.available_slots == 1
            same_limiter = GlobalRateLimiter.get_instance(2)
            assert same_limiter.semaphore is semaphore
            assert same_limiter.max_concurrency == 2
            assert same_limiter.available_slots == 1
        finally:
            semaphore.release()
            _reset_global_limiter()

    asyncio.run(scenario())


def test_analysis_service_llm_slot_releases_after_success():
    """插件级 LLM 槽位应在分析代码块退出后释放。"""
    service = AnalysisApplicationService(
        config_manager=SimpleNamespace(get_llm_max_concurrent=lambda: 1),
        bot_manager=None,
        history_manager=None,
        report_generator=None,
        llm_analyzer=None,
        statistics_service=None,
        analysis_domain_service=None,
    )

    async def scenario():
        async with service._llm_slot("group-1", "test"):
            assert getattr(service.llm_semaphore, "_value", None) == 0
        assert getattr(service.llm_semaphore, "_value", None) == 1

    asyncio.run(scenario())


def test_llm_slot_exposes_stage_metadata_to_trace_context():
    """LLM 槽位应把阶段与群号写入 Trace 元数据，供 Provider 日志追溯。"""
    service = AnalysisApplicationService(
        config_manager=SimpleNamespace(get_llm_max_concurrent=lambda: 1),
        bot_manager=None,
        history_manager=None,
        report_generator=None,
        llm_analyzer=None,
        statistics_service=None,
        analysis_domain_service=None,
    )

    async def scenario():
        with TraceContext(trace_id="trace-for-llm-slot") as trace:
            async with service._llm_slot("group-1", "full_manual"):
                assert trace.metadata["llm_stage"] == "full_manual"
                assert trace.metadata["llm_group_id"] == "group-1"

            assert "llm_stage" not in trace.metadata
            assert "llm_group_id" not in trace.metadata

    asyncio.run(scenario())


def test_daily_analysis_stage_distinguishes_manual_and_scheduled():
    """普通全量分析观测应区分手动命令和定时调度来源。"""
    stages = []

    class FakeConfig:
        def get_llm_max_concurrent(self):
            return 1

        def get_analysis_days(self):
            return 1

        def get_max_messages(self):
            return 10

        def get_filter_bot_messages(self):
            return True

        def get_bot_self_ids(self):
            return []

        def get_min_messages_threshold(self):
            return 1

        def get_max_user_titles(self):
            return 3

        def get_topic_analysis_enabled(self):
            return True

        def get_user_title_analysis_enabled(self):
            return False

        def get_golden_quote_analysis_enabled(self):
            return False

        def get_chat_quality_analysis_enabled(self):
            return False

    class FakeAdapter:
        platform_id = "onebot-main"

        async def fetch_messages(self, **kwargs):
            return [
                UnifiedMessage(
                    message_id="1",
                    sender_id="user-1",
                    sender_name="用户甲",
                    group_id="group-1",
                    text_content="测试消息",
                    contents=(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text="测试消息",
                        ),
                    ),
                    timestamp=1,
                    platform="onebot",
                )
            ]

    class FakeStatisticsService:
        def calculate_group_statistics(self, messages):
            return SimpleNamespace()

        def _convert_to_legacy_dict(self, messages):
            return [{"message": [{"type": "text", "data": {"text": "测试消息"}}]}]

    class FakeDomainService:
        def analyze_user_activity(self, messages, bot_self_ids):
            return {}

        def get_top_users(self, user_activity, limit):
            return []

    class FakeAnalyzer:
        async def analyze_all_concurrent(self, *args, **kwargs):
            return (
                [SimpleNamespace(topic="测试话题", contributors=[], detail="", contributor_ids=[])],
                [],
                [],
                TokenUsage(),
                None,
            )

    class FakeHistoryManager:
        async def save_analysis(self, group_id, analysis_result):
            return None

    service = AnalysisApplicationService(
        config_manager=FakeConfig(),
        bot_manager=SimpleNamespace(get_adapter=lambda platform_id: FakeAdapter()),
        history_manager=FakeHistoryManager(),
        report_generator=None,
        llm_analyzer=FakeAnalyzer(),
        statistics_service=FakeStatisticsService(),
        analysis_domain_service=FakeDomainService(),
    )

    @asynccontextmanager
    async def capture_llm_slot(group_id: str, stage: str):
        stages.append(stage)
        yield

    service._llm_slot = capture_llm_slot

    async def scenario():
        manual_result = await service.execute_daily_analysis(
            "group-1", "onebot-main", manual=True
        )
        scheduled_result = await service.execute_daily_analysis(
            "group-1", "onebot-main", manual=False
        )
        assert manual_result["success"] is True
        assert scheduled_result["success"] is True
        assert stages == ["full_manual", "full_scheduled"]

    asyncio.run(scenario())


def test_call_provider_with_retry_releases_global_slot_on_provider_error():
    """Provider 调用失败时也必须释放全局限流槽位。"""

    class FakeConfig:
        def get_llm_retries(self):
            return 1

        def get_llm_backoff(self):
            return 0

        def get_enable_streaming_llm_call(self):
            return False

        def get_llm_provider_id(self):
            return ""

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object()

        async def llm_generate(self, **kwargs):
            raise RuntimeError("provider timeout")

    async def scenario():
        _reset_global_limiter()
        llm_utils._circuit_breakers.clear()
        GlobalRateLimiter.get_instance(1)

        result = await call_provider_with_retry(
            context=FakeContext(),
            config_manager=FakeConfig(),
            prompt="hello",
            provider_id="provider-a",
        )

        limiter = GlobalRateLimiter.get_instance()
        assert result is None
        assert limiter.available_slots == 1
        _reset_global_limiter()
        llm_utils._circuit_breakers.clear()

    asyncio.run(scenario())


def test_call_provider_with_retry_logs_stage_area_and_slow_block_point(caplog):
    """慢 Provider 调用应持续输出阶段、业务区域和具体阻塞点。"""

    class FakeConfig:
        def get_llm_retries(self):
            return 1

        def get_llm_backoff(self):
            return 0

        def get_enable_streaming_llm_call(self):
            return False

        def get_llm_provider_id(self):
            return ""

    class FakeContext:
        def get_provider_by_id(self, provider_id):
            return object()

        async def llm_generate(self, **kwargs):
            await asyncio.sleep(0.02)
            return LLMResponse(completion_text="ok")

    async def scenario():
        _reset_global_limiter()
        llm_utils._circuit_breakers.clear()
        original_warn_seconds = llm_utils._LLM_REQUEST_WARN_SECONDS
        llm_utils._LLM_REQUEST_WARN_SECONDS = 0.005
        try:
            GlobalRateLimiter.get_instance(1)
            with TraceContext(trace_id="trace-for-provider") as trace:
                trace.metadata["llm_stage"] = "full_manual"
                trace.metadata["llm_group_id"] = "group-1"
                result = await call_provider_with_retry(
                    context=FakeContext(),
                    config_manager=FakeConfig(),
                    prompt="hello",
                    provider_id="provider-a",
                    observation_label="话题",
                )
                assert result is not None
        finally:
            llm_utils._LLM_REQUEST_WARN_SECONDS = original_warn_seconds
            _reset_global_limiter()
            llm_utils._circuit_breakers.clear()

    asyncio.run(scenario())
    messages = caplog.text
    assert "group=group-1" in messages
    assert "stage=full_manual" in messages
    assert "area=话题" in messages
    assert "Provider 请求仍在运行超过" in messages
    assert "block_point=context.llm_generate" in messages


def test_daily_analysis_aborts_when_all_enabled_llm_tasks_fail():
    """当开启了 LLM 分析且所有子任务均失败时，任务必须立即中断并返回失败。"""

    class FakeConfig:
        def get_llm_max_concurrent(self):
            return 1

        def get_analysis_days(self):
            return 1

        def get_max_messages(self):
            return 10

        def get_filter_bot_messages(self):
            return True

        def get_bot_self_ids(self):
            return []

        def get_min_messages_threshold(self):
            return 1

        def get_max_user_titles(self):
            return 3

        def get_topic_analysis_enabled(self):
            return True

        def get_user_title_analysis_enabled(self):
            return True

        def get_golden_quote_analysis_enabled(self):
            return False

        def get_chat_quality_analysis_enabled(self):
            return False

    class FakeAdapter:
        platform_id = "onebot-main"

        async def fetch_messages(self, **kwargs):
            return [
                UnifiedMessage(
                    message_id="1",
                    sender_id="user-1",
                    sender_name="用户甲",
                    group_id="group-1",
                    text_content="测试消息",
                    contents=(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text="测试消息",
                        ),
                    ),
                    timestamp=1,
                    platform="onebot",
                )
            ]

    class FakeStatisticsService:
        def calculate_group_statistics(self, messages):
            return SimpleNamespace()

        def _convert_to_legacy_dict(self, messages):
            return [{"message": [{"type": "text", "data": {"text": "测试消息"}}]}]

    class FakeDomainService:
        def analyze_user_activity(self, messages, bot_self_ids):
            return {}

        def get_top_users(self, user_activity, limit):
            return []

    class FakeAnalyzer:
        async def analyze_all_concurrent(self, *args, **kwargs):
            # 所有子任务均返回空（失败）
            return [], [], [], TokenUsage(), None

    class FakeHistoryManager:
        async def save_analysis(self, group_id, analysis_result):
            return None

    service = AnalysisApplicationService(
        config_manager=FakeConfig(),
        bot_manager=SimpleNamespace(get_adapter=lambda platform_id: FakeAdapter()),
        history_manager=FakeHistoryManager(),
        report_generator=None,
        llm_analyzer=FakeAnalyzer(),
        statistics_service=FakeStatisticsService(),
        analysis_domain_service=FakeDomainService(),
    )

    async def scenario():
        with TraceContext(trace_id="test-abort-trace") as trace:
            result = await service.execute_daily_analysis(
                "group-1", "onebot-main", manual=True
            )
            assert result["success"] is False
            assert result["reason"] == "llm_analysis_failed"
            # 验证 span 状态
            llm_span = next(s for s in trace._spans if s["stage_name"] == "LLM_ANALYSIS")
            assert llm_span["status"] == "failed"

    asyncio.run(scenario())


def test_daily_analysis_warns_when_partial_llm_tasks_fail():
    """当开启了多个 LLM 任务且部分成功时，任务应继续执行并标记为 warning。"""

    class FakeConfig:
        def get_llm_max_concurrent(self):
            return 1

        def get_analysis_days(self):
            return 1

        def get_max_messages(self):
            return 10

        def get_filter_bot_messages(self):
            return True

        def get_bot_self_ids(self):
            return []

        def get_min_messages_threshold(self):
            return 1

        def get_max_user_titles(self):
            return 3

        def get_topic_analysis_enabled(self):
            return True

        def get_user_title_analysis_enabled(self):
            return True

        def get_golden_quote_analysis_enabled(self):
            return False

        def get_chat_quality_analysis_enabled(self):
            return False

    class FakeAdapter:
        platform_id = "onebot-main"

        async def fetch_messages(self, **kwargs):
            return [
                UnifiedMessage(
                    message_id="1",
                    sender_id="user-1",
                    sender_name="用户甲",
                    group_id="group-1",
                    text_content="测试消息",
                    contents=(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text="测试消息",
                        ),
                    ),
                    timestamp=1,
                    platform="onebot",
                )
            ]

    class FakeStatisticsService:
        def calculate_group_statistics(self, messages):
            return SimpleNamespace()

        def _convert_to_legacy_dict(self, messages):
            return [{"message": [{"type": "text", "data": {"text": "测试消息"}}]}]

    class FakeDomainService:
        def analyze_user_activity(self, messages, bot_self_ids):
            return {}

        def get_top_users(self, user_activity, limit):
            return []

    class FakeAnalyzer:
        async def analyze_all_concurrent(self, *args, **kwargs):
            # 话题成功，画像失败
            return (
                [SimpleNamespace(topic="测试话题", contributors=[], detail="", contributor_ids=[])],
                [],
                [],
                TokenUsage(),
                None,
            )

    class FakeHistoryManager:
        async def save_analysis(self, group_id, analysis_result):
            return None

    service = AnalysisApplicationService(
        config_manager=FakeConfig(),
        bot_manager=SimpleNamespace(get_adapter=lambda platform_id: FakeAdapter()),
        history_manager=FakeHistoryManager(),
        report_generator=None,
        llm_analyzer=FakeAnalyzer(),
        statistics_service=FakeStatisticsService(),
        analysis_domain_service=FakeDomainService(),
    )

    async def scenario():
        with TraceContext(trace_id="test-warn-trace") as trace:
            result = await service.execute_daily_analysis(
                "group-1", "onebot-main", manual=True
            )
            assert result["success"] is True
            assert trace.metadata.get("has_warnings") is True
            llm_span = next(s for s in trace._spans if s["stage_name"] == "LLM_ANALYSIS")
            assert llm_span["status"] == "warning"
            trace.finish()
            assert trace.status == "warning"

    asyncio.run(scenario())


def test_daily_analysis_succeeds_when_all_llm_disabled():
    """当 4 个 LLM 分析全部未开启时，算正常运行，整体判定为 succeeded。"""

    class FakeConfig:
        def get_llm_max_concurrent(self):
            return 1

        def get_analysis_days(self):
            return 1

        def get_max_messages(self):
            return 10

        def get_filter_bot_messages(self):
            return True

        def get_bot_self_ids(self):
            return []

        def get_min_messages_threshold(self):
            return 1

        def get_max_user_titles(self):
            return 3

        def get_topic_analysis_enabled(self):
            return False

        def get_user_title_analysis_enabled(self):
            return False

        def get_golden_quote_analysis_enabled(self):
            return False

        def get_chat_quality_analysis_enabled(self):
            return False

    class FakeAdapter:
        platform_id = "onebot-main"

        async def fetch_messages(self, **kwargs):
            return [
                UnifiedMessage(
                    message_id="1",
                    sender_id="user-1",
                    sender_name="用户甲",
                    group_id="group-1",
                    text_content="测试消息",
                    contents=(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text="测试消息",
                        ),
                    ),
                    timestamp=1,
                    platform="onebot",
                )
            ]

    class FakeStatisticsService:
        def calculate_group_statistics(self, messages):
            return SimpleNamespace()

        def _convert_to_legacy_dict(self, messages):
            return [{"message": [{"type": "text", "data": {"text": "测试消息"}}]}]

    class FakeDomainService:
        def analyze_user_activity(self, messages, bot_self_ids):
            return {}

        def get_top_users(self, user_activity, limit):
            return []

    class FakeAnalyzer:
        async def analyze_all_concurrent(self, *args, **kwargs):
            return [], [], [], TokenUsage(), None

    class FakeHistoryManager:
        async def save_analysis(self, group_id, analysis_result):
            return None

    service = AnalysisApplicationService(
        config_manager=FakeConfig(),
        bot_manager=SimpleNamespace(get_adapter=lambda platform_id: FakeAdapter()),
        history_manager=FakeHistoryManager(),
        report_generator=None,
        llm_analyzer=FakeAnalyzer(),
        statistics_service=FakeStatisticsService(),
        analysis_domain_service=FakeDomainService(),
    )

    async def scenario():
        with TraceContext(trace_id="test-no-llm-trace") as trace:
            result = await service.execute_daily_analysis(
                "group-1", "onebot-main", manual=True
            )
            assert result["success"] is True
            trace.finish()
            assert trace.status == "succeeded"

    asyncio.run(scenario())


def test_schema_retry_prompt_and_completion_updated_in_trace(monkeypatch):
    """测试当大模型第一次返回空/格式错误时，通过格式纠错重试后，Trace 中的产物与纠错次数正确更新。"""
    from src.infrastructure.analysis.analyzers.topic_analyzer import TopicAnalyzer

    class MockConfig:
        def get_max_topics(self):
            return 5

        def get_llm_max_retries(self):
            return 1

        def get_llm_retry_delay(self):
            return 0.0

        def get_topic_prompt(self):
            return "请分析话题"

        def get_topic_analysis_prompt(self):
            return "请分析话题 ${max_topics} ${messages_text}"

        def get_prompt_override(self, key):
            return None

        def get_persona_id(self, key):
            return None

        def get_topic_provider_id(self):
            return "test_provider"

        def get_llm_provider_id(self):
            return "test_provider"

        def get_debug_mode(self):
            return False

        def get_bot_self_ids(self):
            return []

        def get_custom_nicknames(self):
            return {}

        def get_sender_preference(self):
            return "nickname"

        def get_anonymous_noise_filtering(self):
            return False

        def get_anonymous_fallback_card_prefix(self):
            return []

        def get_anonymous_fallback_nickname_prefix(self):
            return []

        def get_enable_user_card(self):
            return True

        def get_anonymous_fallback_user_id_prefix(self):
            return []

    class MockContext:
        pass

    analyzer = TopicAnalyzer(context=MockContext(), config_manager=MockConfig())

    r1 = LLMResponse(role="assistant", completion_text="[]")
    r1.raw_completion = {"usage": {"total_tokens": 100, "prompt_tokens": 80, "completion_tokens": 20}}
    r2 = LLMResponse(
        role="assistant",
        completion_text='[{"topic": "高考交流", "contributors": ["123"], "detail": "讨论高考志愿"}]',
    )
    r2.raw_completion = {"usage": {"total_tokens": 150, "prompt_tokens": 90, "completion_tokens": 60}}
    responses = [r1, r2]
    call_idx = 0

    async def fake_call(*args, **kwargs):
        nonlocal call_idx
        res = responses[min(call_idx, len(responses) - 1)]
        call_idx += 1
        return res

    monkeypatch.setattr("src.infrastructure.analysis.analyzers.base_analyzer.call_provider_with_retry", fake_call)
    monkeypatch.setattr(analyzer, "_build_system_prompt", lambda *a, **k: asyncio.sleep(0, result=None))

    async def scenario():
        with TraceContext(trace_id="test-retry-trace") as trace:
            messages = [
                {
                    "sender": {"user_id": "123", "nickname": "Alice", "card": ""},
                    "time": 1787671466,
                    "message": [{"type": "text", "data": {"text": "高考完打算去哪"}}],
                }
            ]
            data_objects, usage = await analyzer.analyze(messages)
            assert len(data_objects) == 1
            assert data_objects[0].topic == "高考交流"

            # 验证 Trace 中主模块槽位被更新为最终纠错后的产物
            prompts = trace.metadata.get("llm_prompts", {})
            assert "话题" in prompts
            assert "话题#schema_retry_1" not in prompts  # 不应产生污染子模块
            assert prompts["话题"]["retry_count"] == 1
            assert "高考交流" in prompts["话题"]["completion"]

    asyncio.run(scenario())


