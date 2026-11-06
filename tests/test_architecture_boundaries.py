"""约束领域契约，不直接依赖宿主和外层实现。"""

import ast
from importlib.util import resolve_name
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_domain_does_not_import_outer_layers():
    forbidden = ("astrbot", "src.infrastructure", "src.application", "src.entrypoints")
    violations = []
    for path in (ROOT / "src/domain").rglob("*.py"):
        package = ".".join(path.parent.relative_to(ROOT).parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                if node.level:
                    module = resolve_name(module, package)
                modules = [module, *(f"{module}.{alias.name}" for alias in node.names)]
            else:
                continue
            for module in modules:
                if any(module == name or module.startswith(name + ".") for name in forbidden):
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
    assert not violations, "领域层不应导入外层实现：\n" + "\n".join(violations)
