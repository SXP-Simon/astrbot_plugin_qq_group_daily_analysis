import argparse
import asyncio
import base64
import json
import os
import sys
import types
from datetime import datetime
from io import BytesIO
from pathlib import Path

# 离线加载插件模块，不启动 AstrBot 或访问真实群聊数据。
plugin_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(plugin_root))

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

# 配置模块在导入时引用 StarTools；离线调试不需要启动宿主。
astrbot_star = types.ModuleType("astrbot.api.star")


class MockStarTools:
    @staticmethod
    def get_data_dir(name: str = "") -> Path:
        """返回离线示例数据目录。

        Args:
            name: 插件名称。

        Returns:
            与真实插件数据隔离的调试目录。
        """
        return plugin_root / "data" / "debug_data" / name


astrbot_star.StarTools = MockStarTools
sys.modules["astrbot.api.star"] = astrbot_star

# Mock astrbot.core.utils.astrbot_path
astrbot_core_utils = types.ModuleType("astrbot.core.utils")
astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_path.get_astrbot_data_path = lambda: Path(".")
sys.modules["astrbot.core.utils"] = astrbot_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path

from PIL import Image, ImageDraw  # noqa: E402

from src.domain.value_objects import (  # noqa: E402
    GroupStatistics,
    SummaryTopic,
    UserTitle,
)
from src.infrastructure.reporting.generators import ReportGenerator  # noqa: E402
from src.shared.constants import DEFAULT_ASSETS_CDN_URL, DEFAULT_CDN_HOST  # noqa: E402
from src.shared.report_language import format_report_date  # noqa: E402


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
        return f"{self.get_template_assets_base_url()}/ATRI"

    def get_t2i_cdn_base_url(self) -> str:
        return DEFAULT_CDN_HOST

    def get_template_assets_base_url(self) -> str:
        return DEFAULT_ASSETS_CDN_URL

    def get_t2i_google_fonts_mirror(self) -> str:
        return "https://fonts.googleapis.com"

    def get_t2i_gstatic_mirror(self) -> str:
        return "https://fonts.gstatic.com"

    def get_t2i_rendering_strategies(self) -> list:
        return []


async def mock_get_user_avatar(user_id: str, size: int | None = None) -> str:
    """生成不关联真实账号的内嵌示例头像，不访问 QQ 头像服务。

    Args:
        user_id: 示例用户 ID，用于选择固定颜色。
        size: 兼容头像获取接口；示例头像统一使用 192 像素。

    Returns:
        PNG 头像的 Data URI。
    """
    colors = [
        "#54a6b8",
        "#e59b9f",
        "#9491c9",
        "#d3a459",
        "#71ad93",
        "#b17c9f",
        "#7f9cb5",
        "#aab46b",
    ]
    image = Image.new(
        "RGB", (192, 192), colors[(int(user_id) - 80010001) % len(colors)]
    )
    draw = ImageDraw.Draw(image)
    draw.ellipse((61, 36, 131, 106), fill="#fff7e6")
    draw.rounded_rectangle((34, 113, 158, 216), radius=58, fill="#fff7e6")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )


async def debug_render(
    template_name: str,
    output_file: str = "debug_output.html",
    profile_mode: str = "mbti",
    template_file: str = "image_template.html",
    report_language: str = "auto",
) -> None:
    """使用固定的日常交流示例生成 HTML，不调用模型或真实账号接口。

    Args:
        template_name: 内置主题目录名。
        output_file: 输出 HTML 文件路径。
        profile_mode: 人格展示方式。
        template_file: 图片或网页报告主模板。
        report_language: 报告界面语言；示例正文保持中文。
    """
    config_manager = MockConfigManager(
        template_name=template_name,
        profile_mode=profile_mode,
        report_language=report_language,
    )

    # 所有数字、人物和交流内容均为模拟数据，用于检查真实模板的排版。
    mock_data = {
        "statistics": {
            "message_count": 964,
            "total_characters": 24782,
            "participant_count": 28,
            "most_active_period": "21:00-22:00",
            "emoji_count": 96,
            "golden_quotes": [
                {
                    "content": "可以先吃再拍吗？这次我想吃热的。",
                    "sender": "小满",
                    "reason": "[80010005] 和 [80010004] "
                    "正讨论野餐那天怎么拍照，[80010006] "
                    "一句“想吃热的”把重点拉回了吃饭。不是反对拍照，只是提醒大家别顾着出片忘了开饭，随后还真把带菜分工定了下来。",
                    "user_id": "80010006",
                },
                {
                    "content": "我的薄荷不是水培，但我一直按水培在养。",
                    "sender": "青柠",
                    "reason": "[80010004] 从照片里发现托盘一直积水，[80010008] "
                    "才意识到自己把土培薄荷浇成了水培。用一句自嘲把问题讲明白，比继续问“是不是水还不够”更有用，也让 "
                    "[80010006] 顺势补充了检查盆土的方法。",
                    "user_id": "80010008",
                },
                {
                    "content": "今晚先救队友，明早再救闹钟。",
                    "sender": "林间",
                    "reason": "[80010007] 刚装好游戏，担心跟不上进度，[80010003] "
                    "先留出练习时间，再用闹钟的梗约定十点收工。既给新手留了位置，也替第二天要上班的人守住了下线时间。",
                    "user_id": "80010003",
                },
            ],
            "emoji_statistics": {"face_count": 61, "mface_count": 35},
            "activity_visualization": {
                "hourly_activity": {
                    "0": 6,
                    "1": 2,
                    "2": 0,
                    "3": 0,
                    "4": 0,
                    "5": 0,
                    "6": 3,
                    "7": 18,
                    "8": 36,
                    "9": 27,
                    "10": 41,
                    "11": 56,
                    "12": 71,
                    "13": 38,
                    "14": 26,
                    "15": 39,
                    "16": 63,
                    "17": 44,
                    "18": 58,
                    "19": 82,
                    "20": 102,
                    "21": 136,
                    "22": 77,
                    "23": 39,
                },
                "user_activity_ranking": [
                    {"user_id": "80010001", "nickname": "小岚", "message_count": 141},
                    {"user_id": "80010002", "nickname": "阿澄", "message_count": 128},
                    {"user_id": "80010003", "nickname": "林间", "message_count": 104},
                    {"user_id": "80010004", "nickname": "浅夏", "message_count": 97},
                    {"user_id": "80010005", "nickname": "星河", "message_count": 84},
                    {"user_id": "80010006", "nickname": "小满", "message_count": 76},
                    {"user_id": "80010007", "nickname": "墨白", "message_count": 65},
                    {"user_id": "80010008", "nickname": "青柠", "message_count": 52},
                ],
            },
            "token_usage": {
                "prompt_tokens": 18642,
                "completion_tokens": 4708,
                "total_tokens": 23350,
            },
            "chat_quality_review": {
                "title": "计划排上了，晚饭也没耽误",
                "subtitle": "从周末出游聊到今晚吃什么，热闹之外也有几件事落了地",
                "dimensions": [
                    {
                        "name": "周末计划",
                        "percentage": 30.0,
                        "comment": "集合时间、带什么、下雨怎么办都说清楚了。只差周五再确认一遍，别让计划留在聊天记录里。",
                        "color": "#5c8d89",
                    },
                    {
                        "name": "厨房交流",
                        "percentage": 26.0,
                        "comment": "大家没有只说“看起来好吃”，而是聊到了水量、焖饭和不辣版本，第一次下厨的人也能照着试。",
                        "color": "#d6a76c",
                    },
                    {
                        "name": "随手摄影",
                        "percentage": 20.0,
                        "comment": "有成片，也有拍失败的照片。建议围绕测光和时间展开，实用程度比报一串设备型号高。",
                        "color": "#7596b8",
                    },
                    {
                        "name": "游戏组队",
                        "percentage": 16.0,
                        "comment": "给新手留了练习时间，提前确认更新和语音，还约好按时收工。队伍没开，准备工作先到位了。",
                        "color": "#9482b2",
                    },
                    {
                        "name": "生活小问答",
                        "percentage": 8.0,
                        "comment": "一盆薄荷让几个人交流了养花经验。先看环境再给建议，比一句“多喝水”靠谱。",
                        "color": "#83a876",
                    },
                ],
                "summary": "今天的群聊没什么大事，但从一张失败的照片到一份能照着做的配方，都有人接话，也有人回来反馈。这种小事有回应的感觉，就是日常群聊最好看的地方。",
            },
        },
        "topics": [
            {
                "topic": "周六去公园，先把集合地点说清楚",
                "contributors": ["小岚", "阿澄", "浅夏", "青柠"],
                "contributor_ids": ["80010001", "80010002", "80010004", "80010008"],
                "detail": "[80010001] "
                "提议周六去湖边公园野餐，最初大家说“地铁口见”，后来发现附近有两个站。[80010002]查了路线，确定上午十点在东门集合，坐二号线的从 "
                "B "
                "口出来步行八分钟。[80010004]带野餐垫，[80010008]准备水果，其他人各带一份食物，不用重复买饮料。天气预报下午可能下雨，大家约好周五晚上再确认一次；如果下雨就改去附近的桌游店。",
            },
            {
                "topic": "电饭锅鸡腿饭，成功了但水放多了",
                "contributors": ["小满", "阿澄", "墨白"],
                "contributor_ids": ["80010006", "80010002", "80010007"],
                "detail": "[80010006] "
                "分享了第一次做鸡腿饭的照片：鸡腿提前腌半小时，和胡萝卜、香菇一起放进电饭锅。味道不错，就是米饭有点软。[80010002]提醒蔬菜和腌料也会出水，下次可以比平常少加一点水，煮好后再焖十分钟。[80010007]照着做了不辣的版本，家里人也能一起吃。两人把各自用量整理到群公告，约好周末再试一次，不再靠“适量”猜配方。",
            },
            {
                "topic": "手机拍落日，先别急着把亮度拉满",
                "contributors": ["星河", "浅夏", "小岚"],
                "contributor_ids": ["80010005", "80010004", "80010001"],
                "detail": "[80010005] "
                "发了下班路上拍的落日，天空很好看，前景却黑成一片。[80010004]建议先点击天空测光，再略微降低曝光，保住云层颜色；如果想留住人物细节，可以换个有路灯的位置，不一定要靠后期把暗部全部提亮。[80010001]用同一路段补拍了一组，发现提前二十分钟到，颜色和光线都更柔和。大家决定野餐那天顺便练习，但先吃饭，免得又拍到食物凉了。",
            },
            {
                "topic": "周日组队，新手也留一个位置",
                "contributors": ["林间", "墨白", "青柠", "小满"],
                "contributor_ids": ["80010003", "80010007", "80010008", "80010006"],
                "detail": "[80010003] "
                "想约周日晚上玩合作游戏，[80010007]说自己刚装好，还没过教程。大家没有直接开高难度，而是约定七点半先用半小时熟悉操作，八点再开正式关卡。[80010008]负责建房，[80010006]提醒先更新游戏和语音设置，避免全员到齐才开始下载。群里最终确认四人参加，其他人有空再替补；十点收工，第二天还要上班，不临时加一局到半夜。",
            },
            {
                "topic": "阳台薄荷没精神，原来不只是缺水",
                "contributors": ["青柠", "浅夏", "小满"],
                "contributor_ids": ["80010008", "80010004", "80010006"],
                "detail": "[80010008] "
                "问薄荷为什么每天浇水还是蔫，照片里花盆下面一直积着水。[80010004]建议先倒掉托盘积水，检查排水孔，不要看叶子没精神就继续浇。[80010006]补充，最近天气转凉，表层土干了也不代表整盆都干透。[80010008]换了通风位置，打算观察两三天再决定要不要换土。大家还约好，下次分享照片时把花盆和摆放环境一起拍进去，省得隔着屏幕全靠猜。",
            },
        ],
        "user_titles": [
            {
                "name": "小岚",
                "user_id": "80010001",
                "title": "行程整理员",
                "mbti": "ENFJ",
                "reason": "把零散的出游想法整理成时间、地点和分工，还记得给雨天留一个备选。",
            },
            {
                "name": "阿澄",
                "user_id": "80010002",
                "title": "配方校对员",
                "mbti": "ISTJ",
                "reason": "给做饭建议时会补充用量和步骤，也愿意帮大家查路线，回答很具体。",
            },
            {
                "name": "林间",
                "user_id": "80010003",
                "title": "组队发起人",
                "mbti": "ENTP",
                "reason": "先把游戏局约起来，再根据新手的进度调整玩法，愿意换个办法让大家都能参加。",
            },
            {
                "name": "浅夏",
                "user_id": "80010004",
                "title": "细节观察员",
                "mbti": "ISFJ",
                "reason": "摄影和养花的话题里都会先问实际情况，提醒也很温和，不急着下结论。",
            },
            {
                "name": "星河",
                "user_id": "80010005",
                "title": "下班追光人",
                "mbti": "ISFP",
                "reason": "会把通勤路上的光线和风景带进群里，愿意晒失败的照片，也认真听建议。",
            },
            {
                "name": "小满",
                "user_id": "80010006",
                "title": "厨房实验员",
                "mbti": "ESFP",
                "reason": "新配方做完就分享成果，水放多了也照样发图，给群里提供了不少真实经验。",
            },
            {
                "name": "墨白",
                "user_id": "80010007",
                "title": "认真补课的新手",
                "mbti": "INTP",
                "reason": "不懂的操作直接问，自己试过之后会回来反馈，游戏和做饭都学得很认真。",
            },
            {
                "name": "青柠",
                "user_id": "80010008",
                "title": "随手记录员",
                "mbti": "INFP",
                "reason": "记得大家说过的小约定，从准备水果到更新薄荷近况，都有后续。",
            },
        ],
        "user_analysis": {
            "80010001": {"nickname": "小岚", "message_count": 141},
            "80010002": {"nickname": "阿澄", "message_count": 128},
            "80010003": {"nickname": "林间", "message_count": 104},
            "80010004": {"nickname": "浅夏", "message_count": 97},
            "80010005": {"nickname": "星河", "message_count": 84},
            "80010006": {"nickname": "小满", "message_count": 76},
            "80010007": {"nickname": "墨白", "message_count": 65},
            "80010008": {"nickname": "青柠", "message_count": 52},
        },
        "group_name": "日常闲聊小站（模拟示例）",
        "group_id": "80010000",
        "analysis_date": "2026-10-23",
    }
    stats = GroupStatistics.from_dict(mock_data["statistics"])
    # JSON 风格数据的小时键是字符串，绘图器使用整数小时。
    stats.activity_visualization.hourly_activity = {
        int(hour): count
        for hour, count in stats.activity_visualization.hourly_activity.items()
    }
    analysis_result = {
        "statistics": stats,
        "topics": [SummaryTopic.from_dict(topic) for topic in mock_data["topics"]],
        "user_titles": [
            UserTitle.from_dict(title) for title in mock_data["user_titles"]
        ],
        "user_analysis": mock_data["user_analysis"],
        "chat_quality_review": stats.chat_quality_review,
        "analysis_date": mock_data["analysis_date"],
        "group_id": mock_data["group_id"],
        "group_name": mock_data["group_name"],
    }

    data_dir = plugin_root / "data" / "debug_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    generator = ReportGenerator(config_manager, data_dir)

    # 4. Prepare Render Data
    # Note: _prepare_render_data handles converting Entities to template-friendly dicts
    render_payload = await generator._prepare_render_data(
        analysis_result,
        template_theme=template_name,
        avatar_url_getter=mock_get_user_avatar,
    )

    # 报告语言：由 DEBUG_REPORT_LANGUAGE 驱动 Mock 配置（见 MockConfigManager.get_report_language），
    # 因此 report_language 与 current_date 都由核心逻辑产出，离线产物与线上走同一条路。

    # 固定示例日期，保证重复渲染时不混入当天时间；语言仍复用正式日期格式。
    moment = datetime.fromisoformat(mock_data["analysis_date"])
    render_payload["current_date"] = (
        format_report_date(render_payload["report_language"], moment) + " · Demo"
    )
    render_payload["current_datetime"] = moment.strftime("%Y-%m-%d 23:59:00")

    # 使用正式模板渲染器。
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_html, encoding="utf-8")

    # 7. Close generator
    await generator.close()

    print(f"已生成 {template_name} / {profile_mode} 示例：{output_path.absolute()}")
    print("可用浏览器打开 HTML 检查排版；日期后的 Demo 表示内容为模拟数据。")


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
