"""导出 AstrBot QQ群聊分析插件 WebUI 的 OpenAPI 3.1 契约规范。

生成根目录下的 openapi.json，定义 REST API 路由与请求响应数据模型。
支持 `--check` 模式用于 CI/CD 和 Git Pre-commit 门禁检测类型契约漂移。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保项目根目录位于 sys.path 中以正确导入 src 内部模块
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from src.infrastructure.webui.openapi_spec import generate_openapi_spec
except ImportError:
    from openapi_spec import generate_openapi_spec  # type: ignore[import-not-found]


def main() -> None:
    """生成或校验 openapi.json 规范。"""
    spec = generate_openapi_spec()
    output_path = ROOT_DIR / "openapi.json"

    if "--check" in sys.argv:
        if not output_path.exists():
            print(
                f"[Error] {output_path} does not exist. Run 'uv run python scripts/export_openapi.py' to generate it.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            with open(output_path, encoding="utf-8") as f:
                current_spec = json.load(f)
        except Exception as e:
            print(
                f"[Error] Failed to parse existing {output_path}: {e}", file=sys.stderr
            )
            sys.exit(1)

        if spec != current_spec:
            print(
                "[Error] openapi.json 与后端 FastAPI 接口定义存在漂移 (Out of Sync)！",
                file=sys.stderr,
            )
            print(
                "请在提交前执行: uv run python scripts/export_openapi.py && pnpm --dir dashboard generate:types",
                file=sys.stderr,
            )
            sys.exit(1)

        print("[Pass] openapi.json 与后端接口规范完全一致 (100% in sync)。")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"Generated OpenAPI specification at: {output_path}")


if __name__ == "__main__":
    main()
