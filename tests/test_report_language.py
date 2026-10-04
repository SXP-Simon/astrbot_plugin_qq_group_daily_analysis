"""报告语言（report_language）单元测试。

覆盖：配置解析、模板门禁、提示词注入幂等、日期格式化、auto 判据、多群并发不串扰。
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from src.shared.report_language import (
    LANGUAGE_AWARE_TEMPLATES,
    apply_auto_language_detection,
    apply_report_language,
    current_report_template,
    detect_language_from_messages,
    format_report_date,
    get_detected_language,
    is_language_aware_template,
    remember_detected_language,
    resolve_report_language,
)


class FakeConfigManager:
    """最小配置管理器替身。"""

    def __init__(
        self, language: str = "auto", template: str | None = "HatsuneMiku"
    ) -> None:
        self.language = language
        self.template = template

    def get_report_language(self) -> str:
        return self.language

    def get_report_template(self) -> str:
        if self.template is None:
            raise RuntimeError("模板读取失败")
        return self.template


class NoTemplateGetter(FakeConfigManager):
    """未实现 get_report_template 的旧 Mock（模拟未知环境）。"""

    get_report_template = None  # type: ignore[assignment]


class NoLanguageGetter:
    """未实现 get_report_language 的旧 Mock。"""


@pytest.mark.parametrize("language", ["zh-Hans", "zh-Hant", "en", "ja"])
def test_resolve_explicit_language(language: str) -> None:
    assert resolve_report_language(FakeConfigManager(language=language)) == language


def test_resolve_auto_returns_none() -> None:
    assert resolve_report_language(FakeConfigManager(language="auto")) is None


def test_resolve_invalid_returns_none() -> None:
    assert resolve_report_language(FakeConfigManager(language="fr")) is None
    assert resolve_report_language(FakeConfigManager(language="")) is None


def test_resolve_without_language_getter_returns_none() -> None:
    assert resolve_report_language(NoLanguageGetter()) is None  # type: ignore[arg-type]


def test_gate_skips_language_for_unadapted_template() -> None:
    """未适配多语言的模板即使配了语言也不生效（避免骨架中文 + 解说英文）。"""
    cfg = FakeConfigManager(language="en", template="scrapbook")
    assert resolve_report_language(cfg) is None
    assert is_language_aware_template(cfg) is False


def test_gate_allows_language_aware_template() -> None:
    cfg = FakeConfigManager(language="en", template=LANGUAGE_AWARE_TEMPLATES[0])
    assert resolve_report_language(cfg) == "en"
    assert is_language_aware_template(cfg) is True


def test_gate_unknown_template_environment_is_permissive() -> None:
    """模板名未知（旧 Mock / 读取异常）时不做门禁，保持历史行为。"""
    assert is_language_aware_template(NoTemplateGetter()) is True
    assert resolve_report_language(NoTemplateGetter(language="en")) == "en"
    assert current_report_template(FakeConfigManager(template=None)) is None


def test_apply_injects_once_and_is_idempotent() -> None:
    cfg = FakeConfigManager(language="en")
    once = apply_report_language("原文", cfg)
    assert "【报告语言】" in once and "English" in once
    assert apply_report_language(once, cfg) == once


def test_apply_keeps_prompt_for_auto_and_unadapted_template() -> None:
    assert apply_report_language("原文", FakeConfigManager(language="auto")) == "原文"
    unadapted = FakeConfigManager(language="en", template="ATRI")
    assert apply_report_language("原文", unadapted) == "原文"


def test_apply_empty_prompt_untouched() -> None:
    assert apply_report_language("", FakeConfigManager(language="en")) == ""


def test_instruction_protects_quotes_and_nicknames() -> None:
    """语言指令必须显式保护引用原文与昵称（金句/昵称不得被翻译）。"""
    text = apply_report_language("原文", FakeConfigManager(language="ja"))
    assert "禁止翻译" in text
    assert "昵称" in text
    assert "JSON" in text


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (None, "2026年10月04日"),
        ("auto", "2026年10月04日"),
        ("zh-Hans", "2026年10月04日"),
        ("zh-Hant", "2026年10月04日"),
        ("ja", "2026年10月4日"),
        ("en", "October 4, 2026"),
    ],
)
def test_format_report_date(language: str | None, expected: str) -> None:
    assert format_report_date(language, datetime(2026, 10, 4)) == expected


# ---------------------------------------------------------------- auto 自动判断


def test_detect_simplified_chinese() -> None:
    texts = [
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_detect_traditional_chinese() -> None:
    texts = [
        "我們來說說這個新遊戲吧，你們覺得好玩嗎",
        "這裡的畫風真的很美，請大家推薦更多",
        "謝謝大家，我們明天再來討論這個",
    ]
    assert detect_language_from_messages(texts) == "zh-Hant"


def test_detect_japanese() -> None:
    texts = [
        "こんにちは、今日はいい天気ですね",
        "みんなでゲームをしましょう！",
        "このイラスト、とても可愛いと思うよ",
    ]
    assert detect_language_from_messages(texts) == "ja"


def test_detect_english() -> None:
    texts = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
    ]
    assert detect_language_from_messages(texts) == "en"


def test_detect_insufficient_evidence_returns_none() -> None:
    assert detect_language_from_messages(["你好", "在吗"]) is None
    assert detect_language_from_messages([]) is None
    # 单一长消息也不够（样本消息数下限）
    assert (
        detect_language_from_messages(
            [
                "今天群里好热闹，大家都聊新出的游戏，我也来说两句，这个画风真好看，推荐一起玩"
            ]
        )
        is None
    )


def test_sticker_line_is_ignored() -> None:
    """Telegram 历史里的「Sticker: 😋」这类占位行没有语言证据，不该投票。"""
    texts = [
        "Sticker: 😋",
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
        "Sticker: 🎉",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_kana_nickname_in_mention_does_not_flip_to_japanese() -> None:
    """群友昵称是三个平假名（@みく）时，整群不能被判成日文。"""
    texts = [
        "@みく 你今天怎么不说话",
        "大家都在等你呢，快点回来",
        "刚刚那个活动你参加了吗",
        "回来记得说一声，我们继续聊",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_url_and_cq_noise_is_ignored() -> None:
    texts = [
        "https://example.com/news/hello-world",
        "[CQ:image,file=abc.jpg]",
        "今天群里好热闹，大家都聊新出的游戏",
        "我也来说两句，这个画风真好看",
        "推荐大家一起玩，晚上联机",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_latin_nickname_does_not_flip_to_english() -> None:
    texts = [
        "@MikuFan 你今天怎么不说话",
        "大家都在等你呢，快点回来",
        "刚刚那个活动你参加了吗",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_chinese_group_with_one_japanese_quote_stays_chinese() -> None:
    """汉字为主的群夹一条日文引用（歌名/歌词）仍按中文处理——占比不够 70% 就不换语言。"""
    texts = [
        "今天听了夜に駆ける，感觉不错",
        "大家都在讨论编曲和调教，推荐去听一遍",
        "我觉得这首歌的副歌特别好听",
        "你们平时都听什么歌，说两个来",
        "晚上一起联机吗，我这边有空",
        "刚下班，等下就上来",
        "这个画风确实很好看",
        "我先把作业写完再玩",
        "群里最近好热闹啊",
        "明天见，大家早点睡",
    ]
    assert detect_language_from_messages(texts) == "zh-Hans"


def test_mixed_group_below_threshold_returns_none() -> None:
    """达不到 70% 的混合语群不猜（返回 None = 不干预，走历史行为）。"""
    texts = [
        "今天群里好热闹啊",
        "我也来说两句",
        "推荐大家一起玩",
        "こんにちは、今日はいい天気ですね",
        "みんなでゲームをしましょう",
        "このイラスト、とても可愛いと思うよ",
    ]
    assert detect_language_from_messages(texts) is None
    # 恰好 70% 也不判（要求「大于 70%」）
    exactly_seventy = [
        "中文消息一",
        "中文消息二",
        "中文消息三",
        "中文消息四",
        "中文消息五",
        "中文消息六",
        "中文消息七",
        *[
            "こんにちは、今日はいい天気ですね",
            "みんなでゲームをしましょう",
            "このイラスト、とても可愛いと思うよ",
        ],
    ]
    assert detect_language_from_messages(exactly_seventy) is None


def test_english_group_with_chinese_smattering_stays_english() -> None:
    texts = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
        "I will bring some snacks for the group",
        "我来晚了，抱歉",
    ]
    assert detect_language_from_messages(texts) == "en"


_MAINLAND_GROUP = [
    "这个应用程序很好用",
    "我查一下信息",
    "软件更新完了",
    "视频下载好了",
    "鼠标坏了",
    "我的账号登录不了",
    "屏幕有点暗",
    "数据存在数据库里",
    "我在写程序",
    "缓存清一下",
]

_TAIWAN_WORDING_SIMPLIFIED_CHARS = [
    "我在用应用程式",
    "我查一下资讯",
    "软体更新完了",
    "影片下载好了",
    "滑鼠坏了",
    "我的帐号登入不了",
    "萤幕有点暗",
    "资料存在资料库里",
    "我在写程式",
    "快取清一下",
]

_TAIWAN_WORDING_TRADITIONAL_CHARS = [
    "我在用應用程式",
    "我查一下資訊",
    "軟體更新完了",
    "影片下載好了",
    "滑鼠壞了",
    "我的帳號登入不了",
    "螢幕有點暗",
    "資料存在資料庫裡",
    "我在寫程式",
    "快取清一下",
]


def test_variant_taiwanese_wording_written_in_simplified_chars() -> None:
    """台湾用词即使写成简体字，也按繁中（台湾）语境判——用户明确要求这一点。"""
    assert detect_language_from_messages(_TAIWAN_WORDING_SIMPLIFIED_CHARS) == "zh-Hant"


def test_variant_taiwanese_wording_in_traditional_chars() -> None:
    assert detect_language_from_messages(_TAIWAN_WORDING_TRADITIONAL_CHARS) == "zh-Hant"


def test_variant_mainland_wording_stays_simplified() -> None:
    """大陆用词的群不能被带上繁体。"""
    assert detect_language_from_messages(_MAINLAND_GROUP) == "zh-Hans"


def test_variant_single_taiwanese_word_is_not_enough() -> None:
    """孤立一个「应用程式」不够定案（最小证据量），其余都是大陆用词时仍按简体。"""
    group = [
        "好的",
        "在吗",
        "我来了",
        "这个应用程序很好用",
        "应用程式",
    ]
    assert detect_language_from_messages(group) == "zh-Hans"


def test_variant_traditional_characters_without_wording() -> None:
    """纯字形证据（没有台湾用词）同样能判出繁体。"""
    group = [
        "今天天氣很好，我想去臺北逛逛",
        "這個遊戲的畫質還不錯",
        "不過我還沒玩過",
        "你們那邊現在幾點",
    ]
    assert detect_language_from_messages(group) == "zh-Hant"


def test_variant_cantonese_hong_kong() -> None:
    """香港粤语用字（嘅/咗/唔/冇…）算繁中语境。"""
    group = [
        "係咁先啦",
        "我等陣間再上線",
        "你食咗飯未",
        "呢個遊戲幾好玩",
        "唔該晒你",
        "我聽日返工",
    ]
    assert detect_language_from_messages(group) == "zh-Hant"


def test_resolve_auto_uses_detected_language() -> None:
    cfg = FakeConfigManager(language="auto")
    remember_detected_language("en")
    assert resolve_report_language(cfg) == "en"
    remember_detected_language("ja")
    assert resolve_report_language(cfg) == "ja"


def test_resolve_auto_without_detection_is_noop() -> None:
    remember_detected_language(None)
    assert resolve_report_language(FakeConfigManager(language="auto")) is None


def test_explicit_language_overrides_detection() -> None:
    remember_detected_language("en")
    assert resolve_report_language(FakeConfigManager(language="zh-Hant")) == "zh-Hant"


def test_apply_auto_detection_writes_context() -> None:
    english = [
        "Hello everyone, today we played a new game",
        "It was really fun, see you tomorrow",
        "Anyone wants to join the next session tonight?",
    ]
    assert apply_auto_language_detection(english) == "en"
    assert get_detected_language() == "en"
    assert apply_auto_language_detection(["你好"]) is None
    assert get_detected_language() is None


def test_detected_language_still_gated_by_template() -> None:
    """自动判断出来的语言同样受模板白名单约束。"""
    remember_detected_language("en")
    assert (
        resolve_report_language(
            FakeConfigManager(language="auto", template="scrapbook")
        )
        is None
    )


def test_schema_condition_matches_code() -> None:
    """设置项的官方键 condition 必须与 LANGUAGE_AWARE_TEMPLATES 一致。

    这是「加模板只改一处」的保险丝：漏同步时跑
    python scripts/sync_report_language_templates.py 修好。
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    item = schema["basic"]["items"]["report_language"]
    declared = item["condition"]["report_template"]
    declared_list = declared if isinstance(declared, list) else [declared]
    assert declared_list == list(LANGUAGE_AWARE_TEMPLATES), (
        "condition.report_template 与 LANGUAGE_AWARE_TEMPLATES 不一致，"
        "跑 python scripts/sync_report_language_templates.py 同步"
    )


def test_schema_uses_official_keys_only() -> None:
    """设置项只能用 AstrBot 官方 schema 键（visible_when / option_labels 等自造键禁止再出现）。

    背景：本模板曾自造 visible_when / option_labels，官方等价键是 condition / labels
    （`condition` 见维护者自己在 daily_comic 里的用法；`labels` 见官方插件配置文档的
    「配置项国际化」一节）。这条断言把该教训固化为回归测试。
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    schema_text = (root / "_conf_schema.json").read_text(encoding="utf-8")
    for invented in ("visible_when", "option_labels"):
        assert invented not in schema_text, f"_conf_schema.json 不应再出现自造键 {invented}"

    item = json.loads(schema_text)["basic"]["items"]["report_language"]
    assert isinstance(item.get("labels"), list), "labels 必须是数组（与 options 顺序对应）"
    assert len(item["labels"]) == len(item["options"]), "labels 必须与 options 等长，否则会串位"
    assert all(label.strip() for label in item["labels"]), "labels 不允许空串"


def _load_language_cases() -> list[dict]:
    """读取 golden 用例（与离线测试器 scripts/debug_render.py --cases 共用同一份数据）。"""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent
    data = json.loads(
        (root / "data" / "language_cases.json").read_text(encoding="utf-8")
    )
    cases = data.get("cases") or []
    assert cases, "tests/data/language_cases.json 里没有一个用例"
    return cases


@pytest.mark.parametrize(
    "case",
    _load_language_cases(),
    ids=[c.get("name", f"case{i}") for i, c in enumerate(_load_language_cases())],
)
def test_language_golden_cases(case: dict) -> None:
    """golden 用例：真实场景（含真机样本归纳出来的样本）逐条钉住判定结果。

    改判据（阈值 / 权重 / 字词表）后一跑就知道有没有翻；用例文件同时给离线测试器用：
    python scripts/debug_render.py --cases tests/data/language_cases.json
    """
    assert detect_language_from_messages(case["messages"]) == case.get("expect"), (
        f"用例「{case.get('name')}」判定结果与预期不符；"
        "想看判定过程跑 python scripts/debug_render.py --detect-file <每行一条消息的文件>"
    )


# ---------------------------------------------------------------------------
# 多群并发：auto 检测结果靠 ContextVar 承载，必须「每组一份」，不能跨群串扰
# （调度器对每个群各起一个 asyncio.create_task；这里用 gather 模拟同一事件循环里并发）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_groups_do_not_cross_languages() -> None:
    """两个群并发分析时，各自的检测结果互不污染。"""
    zh_messages = ["大家一起打排位吧", "昨天那个活动真好玩", "我明天要上班"]
    en_messages = [
        "let us play ranked together",
        "the event yesterday was fun",
        "i have to work tomorrow",
    ]

    async def run_group(messages: list[str]) -> str | None:
        apply_auto_language_detection(messages)
        # 让另一组在这中间写入自己的结果；若 ContextVar 不是任务级隔离，这里就会被串改
        await asyncio.sleep(0.02)
        return get_detected_language()

    zh_language, en_language = await asyncio.gather(
        run_group(zh_messages), run_group(en_messages)
    )
    assert zh_language == "zh-Hans"
    assert en_language == "en"


@pytest.mark.asyncio
async def test_group_without_evidence_keeps_its_own_empty_result() -> None:
    """证据不足的群拿到 None（不干预），不会继承并发兄弟群的语言。"""
    zh_messages = ["大家一起打排位吧", "昨天那个活动真好玩", "我明天要上班"]
    no_evidence = ["好的", "在吗", "嗯嗯"]

    async def detected_group() -> str | None:
        apply_auto_language_detection(zh_messages)
        await asyncio.sleep(0.02)
        return get_detected_language()

    async def empty_group() -> str | None:
        await asyncio.sleep(0.01)
        apply_auto_language_detection(no_evidence)
        return get_detected_language()

    zh_language, empty_language = await asyncio.gather(detected_group(), empty_group())
    assert zh_language == "zh-Hans"
    assert empty_language is None


@pytest.mark.asyncio
async def test_language_is_reset_per_group_analysis() -> None:
    """同一个事件循环里先后跑两个群（顺序执行）时，后一个群不会被前一个群的结果带跑。"""
    apply_auto_language_detection(["大家一起打排位吧", "昨天那个活动真好玩", "我明天要上班"])
    assert get_detected_language() == "zh-Hans"

    apply_auto_language_detection(["好的", "在吗", "嗯嗯"])
    assert get_detected_language() is None
