#!/usr/bin/env python3
"""生成简繁判定用的字表 / 词表：src/shared/zh_variant_tables.py。

为什么需要词表：简繁差异不只在字上，还在用词上——「应用程式 / 应用程序」「软体 / 软件」
「资讯 / 信息」这类，就算有人用简体字写「应用程式」，那也是繁中（台湾）语境的证据，
光数字形特征字判不出来。

数据来源（都统一归一化成简体形式，便于「同一个词不管写成简繁都能命中」）：
- 字表：OpenCC data/dictionary/TSCharacters.txt（繁体→简体，取 1:1 映射，剔除歧义字）
- 词表：OpenCC data/dictionary/TWPhrases.txt（大陆用词→台湾用词）、HKPhrases.txt（→香港用词）
        + 本脚本底部的补充表（高频 IT / 生活用词，OpenCC 没收录的）
- 归一化表：TSCharacters.txt 同一份数据（繁体→简体，逐字）

OpenCC 许可：Apache-2.0。

用法：
    python scripts/gen_zh_variant_tables.py                 # 自动从 GitHub 拉字典
    python scripts/gen_zh_variant_tables.py --dict-dir /tmp/oc   # 用本地已下载的字典
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary"
WANTED = ("TSCharacters.txt", "TWPhrases.txt", "HKPhrases.txt")
OUT = Path(__file__).resolve().parent.parent / "src/shared/zh_variant_tables.py"

# 补充表：OpenCC 没收的高频用词差异（大陆, 台湾/香港）。繁简字形本身不同的会被自动过滤掉
# （那一类字表已经覆盖，留着会重复计分）。
SUPPLEMENT: tuple[tuple[str, str], ...] = (
    ("应用程序", "应用程式"),
    ("手机应用", "手機App"),
    ("硬盘", "硬碟"),
    ("固态硬盘", "固態硬碟"),
    ("内存条", "記憶體"),
    ("闪存", "快閃記憶體"),
    ("打印机", "印表機"),
    ("复印机", "影印機"),
    ("摄像头", "網路攝影機"),
    ("宽带", "寬頻"),
    ("音频", "音訊"),
    ("登录", "登入"),
    ("退出登录", "登出"),
    ("保存", "儲存"),
    ("文件夹", "資料夾"),
    ("文件", "檔案"),
    ("菜单", "選單"),
    ("默认", "預設"),
    ("博客", "部落格"),
    ("帖子", "貼文"),
    ("短信", "簡訊"),
    ("服务器", "伺服器"),
    ("客户端", "用戶端"),
    ("界面", "介面"),
    ("缓存", "快取"),
    ("编译器", "編譯器"),
    ("调试器", "偵錯程式"),
    ("账号", "帳號"),
    ("邮箱", "信箱"),
    ("身份证", "身分證"),
    ("激光", "雷射"),
    ("复印", "影印"),
    ("快递", "宅配"),
    ("外卖", "外送"),
    ("高速公路", "國道"),
    ("公交车", "公車"),
    ("自行车", "腳踏車"),
    ("摩托车", "機車"),
    ("乒乓球", "桌球"),
    ("羽毛球", "羽球"),
    ("台球", "撞球"),
    ("足球", "足球"),
    ("空调", "冷氣"),
    ("盒饭", "便當"),
    ("方便面", "泡麵"),
    ("酸奶", "優格"),
    ("土豆", "馬鈴薯"),
    ("西红柿", "番茄"),
    ("菠萝", "鳳梨"),
    ("猕猴桃", "奇異果"),
    ("塑料袋", "塑膠袋"),
    ("质量", "品質"),
    ("简历", "履歷"),
    ("工资", "薪水"),
    ("数据", "資料"),
    ("数据库", "資料庫"),
    ("信息来源", "資訊來源"),
    ("视频", "影片"),
    ("视频通话", "視訊通話"),
    ("外卖员", "外送員"),
)

#: 粤语（香港）常用字：不是简繁字形差异，但极强地指向香港语境，单独作为词表项计分
CANTONESE_MARKERS: tuple[str, ...] = (
    "嘅",
    "咗",
    "唔",
    "係",
    "嚟",
    "睇",
    "冇",
    "喺",
    "啲",
    "哋",
    "乜",
    "咁",
    "俾",
    "攞",
    "嘢",
    "啱",
    "點解",
    "邊度",
    "幾時",
    "屋企",
    "返工",
    "食飯",
    "唔該",
    "多謝",
    "而家",
    "聽日",
    "琴日",
    "鍾意",
    "乜嘢",
    "咩",
)


def fetch(dict_dir: Path | None) -> dict[str, list[tuple[str, list[str]]]]:
    """读取（或下载）OpenCC 字典，返回 {文件名: [(key, [values...]), ...]}。"""
    parsed: dict[str, list[tuple[str, list[str]]]] = {}
    for name in WANTED:
        if dict_dir:
            text = (dict_dir / name).read_text(encoding="utf-8")
        else:
            with urllib.request.urlopen(f"{RAW}/{name}", timeout=60) as resp:
                text = resp.read().decode("utf-8")
        entries: list[tuple[str, list[str]]] = []
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("\t")
            values = value.split()
            if key and values:
                entries.append((key, values))
        parsed[name] = entries
        print(f"  {name}: {len(entries)} 条")
    return parsed


def _is_common_han(ch: str) -> bool:
    """只保留基本区汉字（U+4E00–U+9FFF）：扩展区/兼容区的生僻字在群聊里几乎不会出现，
    留在表里只会撑大文件。"""
    return len(ch) == 1 and 0x4E00 <= ord(ch) <= 0x9FFF


def build_char_tables(
    entries: list[tuple[str, list[str]]],
) -> tuple[str, str, str, str]:
    """从 TSCharacters（繁体→简体）生成四张表：简繁特征字对 + 繁→简归一化映射。"""
    norm_from: list[str] = []
    norm_to: list[str] = []
    for trad, values in entries:
        simp = values[0]
        if not _is_common_han(trad) or not _is_common_han(simp):
            continue
        norm_from.append(trad)
        norm_to.append(simp)

    # 特征字对：只取单字 1:1、且互相不通用的字
    pairs: list[tuple[str, str]] = []
    for trad, values in entries:
        simp = values[0]
        if len(simp) != 1 or simp == trad:
            continue
        if not _is_common_han(trad) or not _is_common_han(simp):
            continue
        pairs.append((simp, trad))
    trad_set = {t for _, t in pairs}
    simp_set = {s for s, _ in pairs}
    # 剔除歧义字：某个字的另一半同时也是另一对里的字（如 干/幹 与 乾 打架）→ 两边都丢弃
    pairs = [(s, t) for s, t in pairs if s not in trad_set and t not in simp_set]
    pairs.sort()
    seen: set[str] = set()
    simplified: list[str] = []
    traditional: list[str] = []
    for simp, trad in pairs:
        if simp in seen:
            continue
        seen.add(simp)
        simplified.append(simp)
        traditional.append(trad)
    return (
        "".join(simplified),
        "".join(traditional),
        "".join(norm_from),
        "".join(norm_to),
    )


def build_word_tables(
    tw_entries: list[tuple[str, list[str]]],
    hk_entries: list[tuple[str, list[str]]],
    norm_from: str,
    norm_to: str,
) -> tuple[list[str], list[str]]:
    """生成「繁中侧用词」与「大陆侧用词」两张词表（统一归一化成简体形式）。"""
    norm_map = {ord(a): b for a, b in zip(norm_from, norm_to, strict=True)}
    reverse_map = {ord(b): a for a, b in zip(norm_from, norm_to, strict=True)}

    def norm(text: str) -> str:
        return text.translate(norm_map)

    def to_trad(text: str) -> str:
        return text.translate(reverse_map)

    pairs: list[tuple[str, str]] = []
    for entries in (tw_entries, hk_entries):
        for key, values in entries:
            pairs.append((key, values[0]))
    pairs.extend(SUPPLEMENT)

    cn_words: list[str] = []
    tw_words: list[str] = list(CANTONESE_MARKERS)
    for cn_raw, tw_raw in pairs:
        cn = norm(cn_raw).strip()
        tw = norm(tw_raw).strip()
        if not cn or not tw or cn == tw:
            continue
        if len(cn) < 2:
            continue
        # 纯字形差异（台湾写法 == 大陆写法的繁化结果）由字表负责，不重复计分
        if cn and to_trad(cn) == tw_raw:
            continue
        cn_words.append(cn)
        tw_words.append(tw)
    return sorted(set(tw_words)), sorted(set(cn_words))


def wrap(text: str, width: int = 60) -> str:
    """把长字符串按固定宽度切成若干行，便于阅读与 diff。"""
    lines = [text[i : i + width] for i in range(0, len(text), width)]
    return "\n".join(f'    "{line}"' for line in lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dict-dir", type=Path, default=None, help="本地 OpenCC 字典目录"
    )
    args = parser.parse_args()

    print("读取字典：")
    entries = fetch(args.dict_dir)
    simplified, traditional, norm_from, norm_to = build_char_tables(
        entries["TSCharacters.txt"]
    )
    tw_words, cn_words = build_word_tables(
        entries["TWPhrases.txt"], entries["HKPhrases.txt"], norm_from, norm_to
    )
    print(
        f"  特征字对 {len(simplified)} 组；繁中侧用词 {len(tw_words)} 个；大陆侧用词 {len(cn_words)} 个"
    )

    body = f'''"""简繁判定用的字表 / 词表（**自动生成，别手改**）。

生成脚本：scripts/gen_zh_variant_tables.py
数据来源：OpenCC（Apache License 2.0）—— https://github.com/BYVoid/OpenCC
          TSCharacters.txt（繁体→简体，取 1:1 且互不通用的字对）
          TWPhrases.txt（大陆用词 → 台湾用词）、HKPhrases.txt（→ 香港用词）
          + 生成脚本里的高频用词补充表与粤语常用字（OpenCC 未收录部分）
许可：本生成数据适用 Apache-2.0，署名与许可全文见
      src/shared/zh_variant_tables.SOURCE-NOTICE.md（末尾附录）；
      本仓库其余部分沿用项目 MIT 许可。

用途：`report_language._detect_chinese_variant()` 用字形特征 + 用词特征投票，
判断一个中文群该出简体还是繁体报告。词表统一归一化成简体形式，所以
「应用程式」这类**用简体字写的台湾用词**同样能命中。
"""

from __future__ import annotations

#: 简繁 1:1 特征字（两个字符串逐位对应，互不通用）
VARIANT_SIMPLIFIED = (
{wrap(simplified)}
)

VARIANT_TRADITIONAL = (
{wrap(traditional)}
)

#: 繁体→简体 归一化逐字映射（用于把观测文本与词表都折成简体再比对）
TRAD_TO_SIMP_FROM = (
{wrap(norm_from)}
)

TRAD_TO_SIMP_TO = (
{wrap(norm_to)}
)

#: 繁中（台湾/香港）侧用词，已折算成简体形式
TRAD_SIDE_WORDS: tuple[str, ...] = (
{chr(10).join(f'    "{w}",' for w in tw_words)}
)

#: 大陆侧用词，已折算成简体形式
SIMP_SIDE_WORDS: tuple[str, ...] = (
{chr(10).join(f'    "{w}",' for w in cn_words)}
)

assert len(VARIANT_SIMPLIFIED) == len(VARIANT_TRADITIONAL), "特征字表长度不一致"
assert len(TRAD_TO_SIMP_FROM) == len(TRAD_TO_SIMP_TO), "归一化表长度不一致"
'''
    OUT.write_text(body, encoding="utf-8")
    print(f"已写入 {OUT}（{OUT.stat().st_size / 1024:.1f} KB）")


if __name__ == "__main__":
    main()
