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

# Mock astrbot.api before importing our modules
astrbot_api = types.ModuleType("astrbot.api")


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


astrbot_api.logger = MockLogger()
astrbot_api.AstrBotConfig = dict
sys.modules["astrbot.api"] = astrbot_api

# Mock astrbot.core.utils.astrbot_path
astrbot_core_utils = types.ModuleType("astrbot.core.utils")
astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_path.get_astrbot_data_path = lambda: Path(".")
sys.modules["astrbot.core.utils"] = astrbot_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path

from src.domain.value_objects import (  # noqa: E402
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from src.infrastructure.reporting.generators import ReportGenerator  # noqa: E402


class MockConfigManager:
    def __init__(
        self,
        template_name: str = "scrapbook",
        profile_mode: str = "mbti",
        profile_image_opacity: float = 0.20,
        profile_mapping_config: str = "",
        report_language: str = "auto",
    ) -> None:
        self.template_name = template_name
        self.profile_mode = profile_mode
        self.profile_image_opacity = profile_image_opacity
        self.profile_mapping_config = profile_mapping_config
        self.report_language = report_language

    def get_report_template(self) -> str:
        return self.template_name

    def get_custom_report_template_dir(self, template_name: str = "") -> None:
        # 离线调试不加载自定义模板目录，只渲染内置模板
        return None

    def get_max_topics(self) -> int:
        return 8

    def get_max_user_titles(self) -> int:
        return 16

    def get_t2i_font_source(self) -> str:
        # 离线渲染默认 Overseas；要复现大陆部署的产物（页面声明 zh-CN）可加环境变量：
        #   DEBUG_T2I_FONT_SOURCE=Mainland .venv-render/bin/python scripts/debug_render.py ...
        return os.environ.get("DEBUG_T2I_FONT_SOURCE", "Overseas")

    def get_report_language(self) -> str:
        # 语言优先取 --language 参数；未给时回退环境变量 DEBUG_REPORT_LANGUAGE，再回退 auto。
        return (
            (self.report_language or "").strip()
            or os.environ.get("DEBUG_REPORT_LANGUAGE", "auto").strip()
            or "auto"
        )

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

    def get_t2i_rendering_strategies(self) -> list:
        return []


async def mock_get_user_avatar(user_id: str) -> str:
    # Return a known avatar URL for testing
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"


async def debug_render(
    template_name: str,
    output_file: str = "debug_output.html",
    profile_mode: str = "mbti",
    template_file: str = "image_template.html",
    report_language: str = "auto",
) -> None:
    # 1. Setup Mock Data
    config_manager = MockConfigManager(
        template_name=template_name,
        profile_mode=profile_mode,
        report_language=report_language,
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

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "user_analysis": user_analysis,
        "chat_quality_review": stats.chat_quality_review,
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
        analysis_result,
        template_theme=template_name,
        avatar_url_getter=mock_get_user_avatar,
    )

    # 报告语言：由 DEBUG_REPORT_LANGUAGE 驱动 Mock 配置（见 MockConfigManager.get_report_language），
    # 因此 report_language 与 current_date 都由核心逻辑产出，离线产物与线上走同一条路。

    # Use Jinja2 renderer
    final_html = generator.html_templates.render_template(
        template_file, template_theme=template_name, **render_payload
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


def _print_detection_report(texts: list[str], source: str) -> None:
    """打印一次 auto 语言判定的完整过程（票数 / 占比 / 简繁分数 / 命中的词）。

    这就是「判据检视器」：判错了、想调阈值、想解释给用户听，都跑它，不用另写脚本。

    Args:
        texts: 群聊正文（每条消息一条）。
        source: 数据来源说明（打印用）。
    """
    from src.shared.report_language import (
        _MIN_LANGUAGE_CHARS,
        _MIN_VARIANT_EVIDENCE,
        _MIN_VOTING_MESSAGES,
        _SIMP_SIDE_PATTERN,
        _SIMPLIFIED_ONLY,
        _TRAD_SIDE_PATTERN,
        _TRAD_TO_SIMP,
        _TRADITIONAL_ONLY,
        _WORD_HIT_WEIGHT,
        _count_scripts,
        _vote_language,
        clean_message_body,
        detect_language_from_messages,
    )

    print("=" * 72)
    print(f"报告语言 auto 判据检视（来源：{source}，消息 {len(texts)} 条）")
    print("=" * 72)

    votes = {"zh": 0, "en": 0, "ja": 0}
    bodies: list[str] = []
    lang_chars = 0
    for index, raw in enumerate(texts, 1):
        body = clean_message_body(raw or "")
        if not body:
            if (raw or "").strip():
                print(f"  #{index:<3} 噪音整条丢弃  {raw.strip()[:48]!r}")
            continue
        counts = _count_scripts(body)
        chunk = sum(counts.values())
        if chunk == 0:
            continue
        lang_chars += chunk
        bodies.append(body)
        vote = _vote_language(counts)
        if vote:
            votes[vote] += 1
        mark = {"zh": "中文票", "en": "英文票", "ja": "日文票"}.get(
            vote or "", "不投票"
        )
        print(
            f"  #{index:<3} {mark:6s} 假名{counts['kana']:<3d} 汉字{counts['cjk']:<4d} "
            f"拉丁{counts['latin']:<4d} 正文={body[:40]!r}"
        )

    voting = sum(votes.values())
    print("-" * 72)
    print(
        f"  投票合计: zh={votes['zh']} en={votes['en']} ja={votes['ja']}（有效票 {voting}）"
    )
    if voting:
        share = max(votes.values()) / voting * 100
        print(f"  最高占比: {share:.1f}%（要求 > 70%）")
    print(
        f"  样本门槛: 正文条数 {len(bodies)}（要求 ≥{_MIN_VOTING_MESSAGES}）"
        f"、语言字符 {lang_chars}（要求 ≥{_MIN_LANGUAGE_CHARS}）"
    )

    joined = "".join(bodies)
    simplified = sum(1 for ch in joined if ch in _SIMPLIFIED_ONLY)
    traditional = sum(1 for ch in joined if ch in _TRADITIONAL_ONLY)
    normalized = joined.translate(_TRAD_TO_SIMP)
    trad_hits = _TRAD_SIDE_PATTERN.findall(normalized) if _TRAD_SIDE_PATTERN else []
    simp_hits = _SIMP_SIDE_PATTERN.findall(normalized) if _SIMP_SIDE_PATTERN else []
    trad_score = traditional + _WORD_HIT_WEIGHT * len(trad_hits)
    simp_score = simplified + _WORD_HIT_WEIGHT * len(simp_hits)
    print(
        f"  简繁合议（词命中 ×{_WORD_HIT_WEIGHT} 分）: 繁体侧 {trad_score} 分"
        f"（字形 {traditional} + 用词 {len(trad_hits)}）= 简体侧 {simp_score} 分"
        f"（字形 {simplified} + 用词 {len(simp_hits)}）；要求繁体 ≥{_MIN_VARIANT_EVIDENCE} 分且更高"
    )
    if trad_hits:
        print(f"    繁中侧命中: {'、'.join(dict.fromkeys(trad_hits))[:80]}")
    if simp_hits:
        print(f"    大陆侧命中: {'、'.join(dict.fromkeys(simp_hits))[:80]}")

    verdict = detect_language_from_messages(texts)
    print("-" * 72)
    print(f"  最终判定: {verdict or '不干预（走历史行为：骨架简体、解说跟随群消息）'}")
    print("=" * 72)


def _load_detect_texts(path: str) -> list[str]:
    """读取待检测文本：一行一条消息；文件不存在时报错退出。"""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"找不到检测样本文件: {path}")
    return [line.rstrip("\n") for line in p.read_text(encoding="utf-8").splitlines()]


def _run_language_cases(path: str) -> int:
    """跑 golden 用例（tests/data/language_cases.json），返回失败数。

    与 tests/test_report_language.py 共用同一份用例数据：测试器先跑一遍，contributor 不用装
    pytest 也能确认自己没把判据改坏。
    """
    import json

    from src.shared.report_language import detect_language_from_messages

    cases_path = Path(path)
    if not cases_path.exists():
        raise SystemExit(f"找不到用例文件: {path}")
    cases = json.loads(cases_path.read_text(encoding="utf-8")).get("cases", [])
    failed = 0
    for case in cases:
        got = detect_language_from_messages(case.get("messages") or [])
        want = case.get("expect")
        ok = got == want
        print(
            f"[{'PASS' if ok else 'FAIL'}] {case.get('name')}: 期望 {want} 实得 {got}"
        )
        if not ok:
            failed += 1
            _print_detection_report(case.get("messages") or [], case.get("name") or "")
    print(f"\n共 {len(cases)} 例，失败 {failed}")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Debug render tool for astrbot_plugin_qq_group_daily_analysis report templates. "
            "也可用 --detect 检视「报告语言 auto」的判据过程。"
        )
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
        "-f",
        "--template-file",
        type=str,
        default="image_template.html",
        help="Main template file to render (default: image_template.html)",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default=None,
        choices=["auto", "zh-Hans", "zh-Hant", "en", "ja"],
        help="报告语言（默认 auto；未给时回退环境变量 DEBUG_REPORT_LANGUAGE）",
    )
    parser.add_argument(
        "--all-languages",
        action="store_true",
        help="一次渲染全部语言（产出 <输出名>.<语言>.html），方便检查各语言排版",
    )
    parser.add_argument(
        "--detect",
        nargs="*",
        default=None,
        metavar="消息",
        help="只做语言判据检视：把这些消息当群聊正文，打印判定过程后退出（不渲染）",
    )
    parser.add_argument(
        "--detect-file",
        type=str,
        default=None,
        help="从文件读检测样本（一行一条消息），与 --detect 效果相同",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        metavar="用例文件",
        help="跑 golden 用例（默认 tests/data/language_cases.json），逐例打印 PASS/FAIL 后退出",
    )
    args = parser.parse_args()

    if args.cases:
        raise SystemExit(_run_language_cases(args.cases))

    if args.detect is not None or args.detect_file:
        texts = list(args.detect or [])
        if args.detect_file:
            texts.extend(_load_detect_texts(args.detect_file))
        if not texts:
            parser.error("--detect / --detect-file 需要至少一条消息")
        _print_detection_report(texts, args.detect_file or "命令行参数")
        return

    languages = (
        ["auto", "zh-Hans", "zh-Hant", "en", "ja"]
        if args.all_languages
        else [args.language]
    )
    for language in languages:
        output = args.output
        if args.all_languages:
            base = Path(args.output)
            output = str(
                base.with_name(f"{base.stem}.{language}{base.suffix or '.html'}")
            )
        asyncio.run(
            debug_render(
                args.template,
                output,
                args.mode,
                args.template_file,
                report_language=language or "auto",
            )
        )


if __name__ == "__main__":
    main()
