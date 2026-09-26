"""Export OpenAPI 3.1 specification for AstrBot QQ Group Daily Analysis WebUI.

Generates openapi.json defining REST API endpoints and data schemas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import src modules
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from src.infrastructure.webui.openapi_spec import generate_openapi_spec
except ImportError:
    from openapi_spec import generate_openapi_spec  # type: ignore[import-not-found]


def main() -> None:
    """Generate and write openapi.json to plugin root."""
    spec = generate_openapi_spec()
    output_path = ROOT_DIR / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"Generated OpenAPI specification at: {output_path}")


if __name__ == "__main__":
    main()
