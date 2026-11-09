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
                if any(
                    module == name or module.startswith(name + ".")
                    for name in forbidden
                ):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: {module}"
                    )
    assert not violations, "领域层不应导入外层实现：\n" + "\n".join(violations)


def test_domain_does_not_parse_dynamic_sdk_objects():
    """宿主与供应商的动态字段读取应在接入边界完成。"""
    violations = []
    for path in (ROOT / "src/domain").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "hasattr", "setattr"}
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not violations, "领域层不应通过反射解释外部对象：" + ", ".join(violations)


def test_runtime_imports_respect_the_installed_plugin_package():
    """插件源码随 AstrBot 识别的安装目录加载，避免依赖开发时的顶层包名。"""
    forbidden = ("src", "data.plugins.astrbot_plugin_qq_group_daily_analysis")
    violations = []
    for path in (ROOT / "main.py", *(ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                modules = [
                    node.module,
                    *(f"{node.module}.{alias.name}" for alias in node.names),
                ]
            else:
                continue
            if any(
                module == prefix or module.startswith(prefix + ".")
                for module in modules
                for prefix in forbidden
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not violations, "插件运行时代码应使用包内引用：\n" + "\n".join(violations)
