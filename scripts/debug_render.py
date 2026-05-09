import argparse
import asyncio
import os
import sys
import types
from pathlib import Path

# ==========================================
# 1. Environment Setup
# ==========================================
# Add src to path so we can import our modules
# Assuming we are in scripts/
current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, plugin_root)


class MockLogger:
    def info(self, msg, *args, **kwargs):
        print(f"[INFO] {msg}")

    def error(self, msg, *args, **kwargs):
        print(f"[ERROR] {msg}")

    def warning(self, msg, *args, **kwargs):
        print(f"[WARN] {msg}")

    def debug(self, msg, *args, **kwargs):
        print(f"[DEBUG] {msg}")

    def log(self, level, msg, *args, **kwargs):
        print(f"[LOG {level}] {msg}")

    def isEnabledFor(self, level):
        return True


# Mock astrbot.api before importing our modules
astrbot_api = types.ModuleType("astrbot.api")
astrbot_api.__path__ = []  # Mark as package
astrbot_api.logger = MockLogger()
astrbot_api.AstrBotConfig = dict
sys.modules["astrbot.api"] = astrbot_api

# Mock submodules
astrbot_api_provider = types.ModuleType("astrbot.api.provider")
astrbot_api_provider.LLMResponse = type(
    "LLMResponse", (), {"__init__": lambda self, **kwargs: None}
)
sys.modules["astrbot.api.provider"] = astrbot_api_provider

astrbot_api_star = types.ModuleType("astrbot.api.star")
sys.modules["astrbot.api.star"] = astrbot_api_star

# Mock astrbot.core.utils.astrbot_path
astrbot_core_utils = types.ModuleType("astrbot.core.utils")
astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_path.get_astrbot_data_path = lambda: Path(".")
sys.modules["astrbot.core.utils"] = astrbot_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path

from src.application.services.analysis_application_service import (  # noqa: E402
    AnalysisApplicationService,
)
from src.domain.models.data_models import (  # noqa: E402
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    ImageSummaryItem,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from src.domain.services.statistics_service import StatisticsService  # noqa: E402
from src.domain.value_objects.unified_message import (  # noqa: E402
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.infrastructure.reporting.generators import ReportGenerator  # noqa: E402


class MockConfigManager:
    def __init__(
        self,
        template_name: str = "scrapbook",
        profile_mode: str = "mbti",
        profile_image_opacity: float = 0.20,
        profile_mapping_config: str = "",
    ) -> None:
        self.template_name = template_name
        self.profile_mode = profile_mode
        self.profile_image_opacity = profile_image_opacity
        self.profile_mapping_config = profile_mapping_config

    def get_report_template(self) -> str:
        return self.template_name

    def get_max_topics(self) -> int:
        return 8

    def get_max_user_titles(self) -> int:
        return 16

    def get_max_golden_quotes(self) -> int:
        return 8

    def get_html_output_dir(self) -> str:
        return "data/html"

    def get_html_filename_format(self) -> str:
        return "report_{group_id}_{date}.html"

    def get_enable_user_card(self) -> bool:
        return True

    @property
    def playwright_available(self) -> bool:
        return True

    def get_browser_path(self) -> str:
        return ""

    def get_t2i_max_concurrent(self) -> int:
        return 4

    def get_llm_max_concurrent(self) -> int:
        return 2

    def get_profile_display_mode(self) -> str:
        return self.profile_mode

    def get_profile_image_opacity(self) -> float:
        return self.profile_image_opacity

    def get_profile_image_size_mode(self) -> str:
        return "contain"

    def get_profile_mapping_config(self) -> str:
        return self.profile_mapping_config

    def get_html_base_url(self) -> str:
        return ""

    def get_t2i_atri_font_mirror(self) -> str:
        return "https://tc.ciallo.ccwu.cc"

    def get_t2i_google_fonts_mirror(self) -> str:
        return "https://fonts.googleapis.com"

    def get_t2i_gstatic_mirror(self) -> str:
        return "https://fonts.gstatic.com"

    def get_t2i_font_source(self) -> str:
        return "Overseas"

    def get_t2i_rendering_strategies(self) -> list:
        return []

    def get_image_summary_enabled(self) -> bool:
        return True

    def get_max_image_summaries(self) -> int:
        return 5

    def get_max_image_candidates(self) -> int:
        return 10

    def get_image_llm_max_concurrent(self) -> int:
        return 2

    def get_llm_retries(self) -> int:
        return 1

    def get_llm_backoff(self) -> int:
        return 0

    def get_image_summary_prompt(self) -> str:
        return "Test prompt for ${sender}"

    def get_bot_self_ids(self) -> list:
        return []

    def get_enable_streaming_llm_call(self) -> bool:
        return False


async def mock_get_user_avatar(user_id: str) -> str:
    # Return a known avatar URL for testing
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"


async def debug_render(
    template_name: str,
    output_file: str = "debug_output.html",
    profile_mode: str = "mbti",
) -> None:
    # 1. Setup Mock Data
    config_manager = MockConfigManager(
        template_name=template_name,
        profile_mode=profile_mode,
    )

    # 2. Mock Analysis Result using Data Models
    stats = GroupStatistics(
        message_count=1250,
        total_characters=45000,
        participant_count=42,
        most_active_period="20:00 - 22:00",
        golden_quotes=[],  # Will be filled later
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={
                i: (10 + i * 5 if i < 12 else 100 - i * 2) for i in range(24)
            }
        ),
        token_usage=TokenUsage(
            prompt_tokens=1500, completion_tokens=800, total_tokens=2300
        ),
        chat_quality_review=QualityReview(
            title="互联网难民收容所",
            subtitle="只要不工作，我们就是最好的朋友",
            dimensions=[
                QualityDimension(
                    "水群闲聊",
                    44.0,
                    "这里的群友不生产代码，只生产各种表情包和废话，建议送去加个班。",
                    "#607d8b",
                ),
                QualityDimension(
                    "技术探讨",
                    25.5,
                    "偶尔冒出的技术术语像是在荒漠里发现绿洲，虽然很快就被废话淹没了。",
                    "#2196f3",
                ),
                QualityDimension(
                    "深夜发情",
                    15.0,
                    "凌晨三点的群聊内容需要打上 R18 标签，建议各位群友早点休息。",
                    "#f44336",
                ),
                QualityDimension(
                    "就业焦虑",
                    10.5,
                    "谈到工作时群里笼罩着一股淡淡的忧伤，大家都在比谁的工位更像牢房。",
                    "#ff9800",
                ),
            ],
            summary="今天也是充满活力（或者说充满废话）的一天，继续保持这份不求上进的快乐吧。",
        ),
    )

    topics = [
        SummaryTopic(
            topic="关于AstrBot插件开发的讨论",
            contributors=["张三", "李四", "王五"],
            detail="大家深入探讨了专家 [123456789] 提到的如何利用Jinja2模板渲染出精美的分析报告，[987654321] 也分享了调试技巧。",
        ),
        SummaryTopic(
            topic="午餐吃什么的终极哲学问题",
            contributors=["赵六", "孙七"],
            detail="[112233445] 提议去吃黄焖鸡，但群友对螺蛳粉的优劣进行了长达一小时的辩论，最终未能达成共识。",
        ),
        SummaryTopic(
            topic="新出的3A大作测评",
            contributors=["周八", "吴九"],
            detail="[200000000] 开始尝试新的游戏，发现 INTJ 类型的玩家在策略游戏中非常吃香。",
        ),
    ]

    mbti_types = [
        "INTJ",
        "INTP",
        "ENTJ",
        "ENTP",
        "INFJ",
        "INFP",
        "ENFJ",
        "ENFP",
        "ISTJ",
        "ISFJ",
        "ESTJ",
        "ESTP",
        "ISTP",
        "ISFP",
        "ESFJ",
        "ESFP",
    ]
    user_titles = []
    user_analysis = {
        "123456789": {"nickname": "张三"},
        "987654321": {"nickname": "李四"},
        "112233445": {"nickname": "潜水员"},
    }

    for i, mbti in enumerate(mbti_types):
        uid = str(200000000 + i)
        uname = f"用户_{mbti}"
        user_titles.append(
            UserTitle(
                name=uname,
                user_id=uid,
                title=f"{mbti} 王者",
                mbti=mbti,
                reason=f"在日常交流中表现出极强的 {mbti} 特征，获得了大家的认可。",
            )
        )
        user_analysis[uid] = {"nickname": uname}

    golden_quotes = [
        GoldenQuote(
            content="代码写得好，下班走得早。",
            sender="张三",
            reason="深刻揭示了程序员的生存法则",
            user_id="123456789",
        ),
        GoldenQuote(
            content="这个Bug我不修，它就是个Feature。",
            sender="李四",
            reason="经典的开发辩解",
            user_id="987654321",
        ),
        GoldenQuote(
            content="PHP是世界上最好的语言！",
            sender="王五",
            reason="[200000001] 表示强烈赞同，并引发了后续的长篇大论。",
            user_id="112233445",
        ),
    ]

    stats.golden_quotes = golden_quotes
    # token_usage already set in constructor

    image_summaries = [
        ImageSummaryItem(
            url="https://q4.qlogo.cn/headimg_dl?dst_uin=123456789&spec=640",
            sender="张三",
            sender_id="123456789",
            description="这张图里的代码写得很有深度，建议细品。",
        ),
        ImageSummaryItem(
            url="https://q4.qlogo.cn/headimg_dl?dst_uin=987654321&spec=640",
            sender="李四",
            sender_id="987654321",
            description="离谱的 Bug 现场，建议查查这位群友的心理状态。",
        ),
        ImageSummaryItem(
            url="https://q4.qlogo.cn/headimg_dl?dst_uin=112233445&spec=640",
            sender="王五",
            sender_id="112233445",
            description="群友发的神秘二次元图，大家都在问出处。",
        ),
    ]

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "user_analysis": user_analysis,
        "chat_quality_review": stats.chat_quality_review,
        "image_summaries": image_summaries,
        "analysis_date": "2026年02月11日",
        "group_id": "123456",
        "group_name": "插件逻辑调试群",
    }

    # 3. Initialize Generator
    data_dir = Path("data/debug_data")
    data_dir.mkdir(parents=True, exist_ok=True)
    generator = ReportGenerator(config_manager, data_dir)

    # Mock avatar cache to avoid KeyError in debug mode
    class MockCache(dict):
        def __getitem__(self, key):
            return self.get(key, "")

        def set(self, key, value, expire=None):
            self[key] = value

    generator._avatar_cache = MockCache()

    # 4. Prepare Render Data
    # Note: _prepare_render_data handles converting Entities to template-friendly dicts
    render_payload = await generator._prepare_render_data(
        analysis_result, avatar_url_getter=mock_get_user_avatar
    )

    # Use Jinja2 renderer
    final_html = generator.html_templates.render_template(
        "image_template.html", **render_payload
    )

    # 复用最终 HTML 中所有内联头像资源，并注入复用样式
    final_html = generator._reuse_avatars_in_final_html(
        final_html,
        render_payload.get("avatar_reuse_registry", {}),
        render_payload.get("avatar_reuse_aliases", {}),
    )

    # 6. Save to file
    output_path = Path(output_file)
    output_path.write_text(final_html, encoding="utf-8")

    # 7. Close generator
    await generator.close()

    print(
        f"Successfully rendered template '{template_name}' in mode '{profile_mode}' to {output_path.absolute()}"
    )
    print("You can now open this file with your browser to debug your HTML/CSS.")


async def test_image_logic():
    print("\n" + "=" * 50)
    print("RUNNING IMAGE LOGIC TESTS")
    print("=" * 50)

    # 1. Test StatisticsService Sampling
    stats_service = StatisticsService()
    messages = []
    # Create 30 mock messages with images
    for i in range(30):
        messages.append(
            UnifiedMessage(
                message_id=f"msg_{i}",
                sender_id=f"user_{i}",
                sender_name=f"User {i}",
                group_id="test_group",
                timestamp=1000 + i * 100,
                text_content="",
                contents=(
                    MessageContent(
                        type=MessageContentType.IMAGE,
                        url=f"http://example.com/img_{i}.jpg",
                        raw_data={"url": f"http://example.com/img_{i}.jpg"},
                    ),
                ),
            )
        )

    print(f"Total messages created: {len(messages)}")
    limit = 10
    sampled = stats_service.extract_image_summaries(messages, limit=limit)

    print(f"Sampled {len(sampled)} images (Limit: {limit})")
    for i, item in enumerate(sampled):
        print(f"  [{i}] {item.url}")

    # Verify distribution (simple check)
    if len(sampled) == limit:
        print("[PASS] Sampling count correct.")
        # Check if it's spread out (index should be roughly 0, 3, 6, 9, 12, 15, 18, 21, 24, 27)
        indices = [int(item.url.split("_")[1].split(".")[0]) for item in sampled]
        print(f"  Indices: {indices}")
        if indices[0] == 0 and indices[-1] > 20:
            print("[PASS] Sampling distribution seems uniform.")
    else:
        print("[FAIL] Sampling count incorrect.")

    # 2. Test Concurrent Analysis in AnalysisApplicationService
    print("\nTesting Concurrent Analysis...")

    class MockLLMAnalyzer:
        def __init__(self):
            self.context = types.ModuleType("MockContext")

            async def mock_llm_generate(**kwargs):
                await asyncio.sleep(0.5)  # Simulate network latency
                print(f"    [AI] Analyzing {kwargs.get('image_urls')}")
                return types.SimpleNamespace(
                    completion_text="这张图很抽象。",
                    usage={
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                    },
                )

            self.context.llm_generate = mock_llm_generate
            self.context.get_provider_by_id = lambda **k: types.SimpleNamespace(
                text_chat_stream=None, meta=lambda: types.SimpleNamespace(id="test")
            )

    config = MockConfigManager()

    # Manually mock the service object to avoid heavy __init__
    class MockService:
        def __init__(self, config_manager, llm_analyzer):
            self.config_manager = config_manager
            self.llm_analyzer = llm_analyzer

    app_service = MockService(config, MockLLMAnalyzer())
    # Bind the method from the class to our mock instance
    app_service._enrich_image_summaries = (
        AnalysisApplicationService._enrich_image_summaries.__get__(
            app_service, MockService
        )
    )

    start_time = asyncio.get_event_loop().time()
    # Mocking 5 candidates, concurrency limit is 2
    candidates = sampled[:5]
    print(f"Starting parallel analysis of {len(candidates)} images (Concurrency: 2)...")

    # We need to mock get_provider_id_with_fallback for AnalysisApplicationService
    # It's imported as a function, so we might need to patch it or mock the context better.
    # Since we are in a debug script, we can just hack it.
    import src.application.services.analysis_application_service as aas

    original_fallback = aas.get_provider_id_with_fallback
    aas.get_provider_id_with_fallback = lambda *a, **k: asyncio.sleep(
        0, result="mock_provider"
    )

    # Also mock call_provider_with_retry
    original_call = aas.call_provider_with_retry

    async def mock_call(*a, **k):
        await asyncio.sleep(0.5)
        print(
            f"    [AI] Analyzing image: {k.get('extra_generate_kwargs', {}).get('image_urls')}"
        )
        return types.SimpleNamespace(
            completion_text="这张图太离谱了，建议查查。",
            usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        )

    aas.call_provider_with_retry = mock_call

    try:
        enriched, tokens = await app_service._enrich_image_summaries(candidates)
        end_time = asyncio.get_event_loop().time()

        print(f"Analysis took {end_time - start_time:.2f}s")
        print(f"Enriched {len(enriched)} images")
        print(
            f"Total Tokens: {tokens.total_tokens} (P:{tokens.prompt_tokens}, C:{tokens.completion_tokens})"
        )

        # Verify time: 5 images, concurrency 2, each 0.5s -> should take ~1.5s
        if 1.4 <= (end_time - start_time) <= 1.8:
            print("[PASS] Concurrency seems to be working correctly (around 1.5s).")
        else:
            print(
                f"Note: Concurrency check timed {end_time - start_time:.2f}s (Expected ~1.5s)"
            )

        if tokens.total_tokens == 300 * len(enriched):
            print("[PASS] Token tracking correct.")
    finally:
        # Restore originals
        aas.get_provider_id_with_fallback = original_fallback
        aas.call_provider_with_retry = original_call

    print("=" * 50 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug render tool for astrbot_plugin_qq_group_daily_analysis report templates."
    )
    parser.add_argument(
        "-t",
        "--template",
        type=str,
        default="scrapbook",
        help="Template name to render (default: scrapbook)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="debug_output.html",
        help="Output HTML file path (default: debug_output.html)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        default="mbti",
        choices=["mbti", "sbti", "acgti"],
        help="Profile display mode to render (default: mbti)",
    )
    parser.add_argument(
        "--test-logic",
        action="store_true",
        help="Run image sampling and concurrency logic tests",
    )
    args = parser.parse_args()

    if args.test_logic:
        asyncio.run(test_image_logic())
    else:
        asyncio.run(debug_render(args.template, args.output, args.mode))


if __name__ == "__main__":
    main()
