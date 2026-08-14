import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from astrbot.api.provider import LLMResponse

from src.domain.models.data_models import TokenUsage
from src.domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.application.services.analysis_application_service import AnalysisApplicationService
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


def test_call_provider_with_retry_logs_stage_area_and_slow_block_point(capsys):
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
    messages = capsys.readouterr().out
    assert "group=group-1" in messages
    assert "stage=full_manual" in messages
    assert "area=话题" in messages
    assert "Provider 请求仍在运行超过" in messages
    assert "block_point=context.llm_generate" in messages
