"""导出 AstrBot QQ群聊分析插件 WebUI 的 OpenAPI 3.1 契约规范。

生成根目录下的 openapi.json，定义 REST API 路由与请求响应数据模型。
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
    """生成并将 openapi.json 写入插件根目录。"""
    spec = generate_openapi_spec()
    output_path = ROOT_DIR / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"Generated OpenAPI specification at: {output_path}")


if __name__ == "__main__":
    main()
