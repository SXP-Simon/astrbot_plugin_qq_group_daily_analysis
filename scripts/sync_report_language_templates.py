#!/usr/bin/env python3
"""把「支持报告语言的模板名单」从唯一真源同步到 _conf_schema.json。

**唯一真源**：`src/shared/report_language.py` 的 `LANGUAGE_AWARE_TEMPLATES`。
设置项 `report_language` 的官方键 `condition` 由本脚本写入，避免两边各改一次
（漏改的后果：设置项不显示但生效，或显示了却不生效）。

`condition` 是 AstrBot 官方 schema 键（WebUI 与插件自带面板都认），语义是**单值相等**；
本仓库维护者已在 `daily_comic.drawing_provider_overrides.*.size` 上用同一写法。
白名单超过一个模板时写成数组（插件自带面板支持命中任一即显示；官方面板请届时回归确认）。

新增一个支持报告语言的模板时：
1. 模板自己内建语言字典（骨架文案 / 页面语言声明 / 字体优先级随 REPORT_LANG 切换）；
2. 把模板名加进 `LANGUAGE_AWARE_TEMPLATES`；
3. 跑本脚本（`python scripts/sync_report_language_templates.py`），或直接跑测试——
   `tests/test_report_language.py::test_schema_condition_matches_code` 会提示你跑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.shared.report_language import LANGUAGE_AWARE_TEMPLATES  # noqa: E402

SCHEMA = ROOT / "_conf_schema.json"


def main() -> int:
    """同步 condition 名单；返回 0 表示（同步后）一致，1 表示读取失败。"""
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:  # pragma: no cover - 只在文件损坏时触发
        print(f"读取 {SCHEMA} 失败：{exc}")
        return 1

    item = schema.get("basic", {}).get("items", {}).get("report_language")
    if item is None:
        print("_conf_schema.json 里找不到 basic.items.report_language")
        return 1

    wanted: list[str] = list(LANGUAGE_AWARE_TEMPLATES)
    expected: str | list[str] = wanted[0] if len(wanted) == 1 else wanted
    condition = item.get("condition")
    current = condition.get("report_template") if isinstance(condition, dict) else None
    if current == expected:
        print(f"已是最新：condition.report_template = {current}")
        return 0

    item["condition"] = {"report_template": expected}
    SCHEMA.write_text(
        json.dumps(schema, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
    )
    print(f"已同步：condition.report_template {current} -> {expected}（写入 {SCHEMA}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
