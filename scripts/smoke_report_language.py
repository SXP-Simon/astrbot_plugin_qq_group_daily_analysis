#!/usr/bin/env python3
"""报告语言 / 多语言模板改动的冒烟测试（一次跑完全部面）。

覆盖：
  1. 配置 schema 不变量（位置、条件显示、选项标签、与代码白名单一致）
  2. 语言解析与模板门禁
  3. 渲染矩阵：HatsuneMiku × {网页模板, 长图模板} × {auto, zh-Hans, zh-Hant, en, ja}
     —— 每份检查：渲染成功、无 Jinja 残留、页面语言声明正确、骨架文案与语言一致
  4. 长图专项：交互件类名出现 0 次（铁律：默认态完整可读、动效不入长图）
  5. 前端产物已接官方键 condition / labels（且不含自造键）

用法：
  ../../.venv-render/bin/python scripts/smoke_report_language.py            # 渲染 + 静态检查
  /home/AI-agent/dsweb/venv/bin/python scripts/smoke_report_language.py --with-shot  # 追加长图截图量尺寸
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _find_render_python() -> Path:
    """找渲染用的解释器：环境变量优先，其次仓库常见的两个相对位置，最后退回当前解释器。"""
    override = os.environ.get("SMOKE_RENDER_PYTHON")
    candidates = [
        Path(override) if override else None,
        ROOT.parent.parent / ".venv-render" / "bin" / "python",
        ROOT.parent / ".venv-render" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise SystemExit("找不到渲染解释器，可用 SMOKE_RENDER_PYTHON=<python 路径> 指定")


PYTHON = _find_render_python()
TEMPLATE = "HatsuneMiku"
LANGUAGES = ("auto", "zh-Hans", "zh-Hant", "en", "ja")
#: 各语言的页面语言声明期望值（auto 未命中时跟随字体源：离线默认 Overseas）
EXPECTED_LANG_ATTR = {
    "auto": "zh-Hant",
    "zh-Hans": "zh-Hans",
    "zh-Hant": "zh-Hant",
    "en": "en",
    "ja": "ja",
}
#: 简体骨架文案（应当只出现在 zh-Hans / auto 产物里）
SIMPLIFIED_SKELETON = ("群友画像", "今日圣经", "群聊锐评")
#: 只该出现在网页交互层的类名，长图里必须为 0（否则截屏会捕获到半成品状态）
WEB_ONLY_MARKERS = (
    "miku-nav",
    "miku-fold-wrap",
    "miku-fold-inner",
    "miku-more-btn",
    "is-scroll",
    "is-tip",
)
#: 语言判定 golden 用例
CASES = ROOT / "tests" / "data" / "language_cases.json"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """记录一条检查结果并即时打印。"""
    results.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}{('  — ' + detail) if detail else ''}")


def check_schema() -> None:
    schema_text = (ROOT / "_conf_schema.json").read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    basic = schema["basic"]["items"]
    keys = list(basic)
    item = basic.get("report_language")

    check(
        "schema: report_language 在 basic 组且紧跟 report_template",
        bool(item)
        and (keys.index("report_language") == keys.index("report_template") + 1),
        f"顺序 {keys.index('report_template')} → {keys.index('report_language') if item else '缺失'}",
    )

    condition = (item or {}).get("condition") or {}
    declared = condition.get("report_template")
    check(
        "schema: 官方键 condition 指向初音模板（单值相等）",
        declared == TEMPLATE,
        json.dumps(condition, ensure_ascii=False),
    )

    options = list((item or {}).get("options") or [])
    labels = list((item or {}).get("labels") or [])
    check(
        "schema: 官方键 labels 与 options 等长且无空串（防串位）",
        len(labels) == len(options) and all(label.strip() for label in labels),
        f"options={options} labels={labels}",
    )
    check(
        "schema: 默认值在选项内",
        (item or {}).get("default") in options,
        str((item or {}).get("default")),
    )
    check(
        "schema: 选项都是合法语言代码（含 auto）",
        set(options) == set(LANGUAGES),
        str(options),
    )

    # 反向保险丝：不许再出现自造键（这次整改的教训固化成检查）
    invented = [
        key
        for key in ("visible_when", "option_labels", '"hidden"')
        if key in schema_text
    ]
    check(
        "schema: 不含自造键（visible_when / option_labels / hidden）",
        not invented,
        ("发现：" + "、".join(invented)) if invented else "干净",
    )

    from src.shared.report_language import LANGUAGE_AWARE_TEMPLATES

    declared_list = declared if isinstance(declared, list) else [declared]
    check(
        "schema: condition 名单与 LANGUAGE_AWARE_TEMPLATES 一致",
        declared_list == list(LANGUAGE_AWARE_TEMPLATES),
        f"{declared_list} vs {list(LANGUAGE_AWARE_TEMPLATES)}",
    )


def check_language_resolution() -> None:
    from src.shared.report_language import (
        apply_report_language,
        resolve_report_language,
    )

    class Cfg:
        def __init__(self, language: str, template: str) -> None:
            self.language = language
            self.template = template

        def get_report_language(self) -> str:
            return self.language

        def get_report_template(self) -> str:
            return self.template

    check(
        "解析: 初音模板 + 显式 en 生效",
        resolve_report_language(Cfg("en", TEMPLATE)) == "en",
    )
    check(
        "门禁: 非白名单模板即使配了语言也不生效",
        resolve_report_language(Cfg("en", "scrapbook")) is None,
    )
    check(
        "解析: auto 且未检测到语言时不干预",
        resolve_report_language(Cfg("auto", TEMPLATE)) is None,
    )
    prompt = apply_report_language("测试提示词", Cfg("en", TEMPLATE))
    check(
        "注入: 语言指令包含引用/昵称保护且只注入一次",
        "原样保留" in prompt
        and apply_report_language(prompt, Cfg("en", TEMPLATE)) == prompt,
    )


def check_cases() -> None:
    from src.shared.report_language import detect_language_from_messages

    cases = json.loads(CASES.read_text(encoding="utf-8")).get("cases") or []
    bad = [
        f"{c['name']}: 期望 {c.get('expect')} 实得 {detect_language_from_messages(c['messages'])}"
        for c in cases
        if detect_language_from_messages(c["messages"]) != c.get("expect")
    ]
    check(f"判据: golden 用例 {len(cases)} 例全部命中", not bad, "; ".join(bad[:3]))


def render(template_file: str, language: str, out_dir: Path) -> tuple[Path, str]:
    """渲染一份模板，返回（产物路径, 标准输出）。"""
    out = out_dir / f"{template_file}.{language}.html"
    proc = subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "scripts" / "debug_render.py"),
            "-t",
            TEMPLATE,
            "-f",
            template_file,
            "-o",
            str(out),
            "-l",
            language,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return out, proc.stdout + proc.stderr


def check_render_matrix(out_dir: Path) -> None:
    for template_file in ("html_template.html", "image_template.html"):
        for language in LANGUAGES:
            tag = f"渲染: {template_file} × {language}"
            out, log = render(template_file, language, out_dir)
            if not out.exists():
                check(tag, False, f"未产出文件；日志尾部 {log.strip()[-160:]}")
                continue
            html = out.read_text(encoding="utf-8")
            problems = []
            for marker in ("{{", "{%", "{#"):
                if marker in html:
                    problems.append(f"残留 {marker}")
            lang_attr = ""
            for token in html.split("<html", 1)[-1].split(">")[0].split():
                if token.startswith("lang="):
                    lang_attr = token.split("=", 1)[1].strip('"')
            if lang_attr != EXPECTED_LANG_ATTR[language]:
                problems.append(f"lang={lang_attr} 期望 {EXPECTED_LANG_ATTR[language]}")
            if template_file == "html_template.html":
                has_simplified = any(word in html for word in SIMPLIFIED_SKELETON)
                expect_simplified = language in ("auto", "zh-Hans")
                if has_simplified != expect_simplified:
                    problems.append(
                        f"简体骨架文案出现={has_simplified} 期望={expect_simplified}"
                    )
            check(tag, not problems, "；".join(problems))


def check_long_image(out_dir: Path) -> None:
    """长图里不能出现交互件的**元素**（类名出现在 CSS 规则里无所谓，元素在才是问题）。"""
    import re

    html = (out_dir / "image_template.html.auto.html").read_text(encoding="utf-8")
    element_hits = {}
    css_hits = {}
    for marker in WEB_ONLY_MARKERS:
        elements = len(re.findall(rf'(?:id|class)="[^"]*{re.escape(marker)}', html))
        raw = html.count(marker)
        if elements:
            element_hits[marker] = elements
        if raw and not elements:
            css_hits[marker] = raw
    detail = "全部为 0"
    if element_hits:
        detail = f"元素命中 {json.dumps(element_hits, ensure_ascii=False)}"
    elif css_hits:
        detail = (
            f"仅出现在 CSS 规则里（无元素）：{json.dumps(css_hits, ensure_ascii=False)}"
        )
    check("长图: 交互层元素 0 个（动效不入长图）", not element_hits, detail)


def check_frontend_bundle() -> None:
    bundle = ROOT / "pages" / "daily-analysis" / "assets" / "index.js"
    text = (
        bundle.read_text(encoding="utf-8", errors="replace") if bundle.exists() else ""
    )
    check(
        "前端产物: 已接官方键 condition / labels",
        "condition" in text and "labels" in text,
        f"{bundle.name} {bundle.stat().st_size // 1024 if bundle.exists() else 0} KB",
    )
    stale = [key for key in ("visible_when", "option_labels") if key in text]
    check(
        "前端产物: 不再含自造键（需重建产物）",
        not stale,
        ("发现：" + "、".join(stale) + "，请重建 dashboard 产物") if stale else "干净",
    )


def check_long_image_shot(out_dir: Path) -> None:
    """用 Playwright 量长图实际尺寸（需要装了 playwright 的解释器）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check(
            "长图尺寸: 跳过（当前解释器没有 playwright）",
            True,
            "用 dsweb venv 跑 --with-shot",
        )
        return

    path = out_dir / "image_template.html.auto.html"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 940, "height": 1200})
            page.goto(f"file://{path}")
            page.wait_for_timeout(2500)
            box = page.evaluate(
                "() => ({w: document.documentElement.scrollWidth, "
                "h: document.documentElement.scrollHeight})"
            )
            page.screenshot(path=str(out_dir / "long.auto.png"), full_page=True)
            browser.close()
        ok = 900 <= box["w"] <= 1000 and 3000 <= box["h"] <= 9000
        check("长图尺寸: 宽约 940、高在 3000–9000 之间", ok, f"{box['w']}×{box['h']}")
    except Exception as exc:  # pragma: no cover - 环境相关
        check("长图尺寸: 截图失败", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-shot", action="store_true", help="追加 Playwright 长图截图量尺寸"
    )
    parser.add_argument(
        "--out", type=str, default=None, help="产物目录（默认临时目录）"
    )
    args = parser.parse_args()

    out_dir = (
        Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="smoke-lang-"))
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))

    print(f"改动冒烟测试（产物目录：{out_dir}）\n")
    check_schema()
    check_language_resolution()
    check_cases()
    check_render_matrix(out_dir)
    check_long_image(out_dir)
    if args.with_shot:
        check_long_image_shot(out_dir)
    check_frontend_bundle()

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n合计 {len(results)} 项，失败 {len(failed)} 项")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
