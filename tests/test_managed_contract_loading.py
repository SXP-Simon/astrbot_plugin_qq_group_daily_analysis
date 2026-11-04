"""契约支持安装包加载，也支持不启动宿主的独立导出。"""

import subprocess
import sys
from pathlib import Path


def test_contract_loads_without_top_level_src_alias(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = root / "src/infrastructure/webui/openapi_spec.py"
    code = f"""
import importlib.util
import sys
import types
package = types.ModuleType('contract_host')
package.__path__ = [{str(source.parent)!r}]
sys.modules['contract_host'] = package
spec = importlib.util.spec_from_file_location('contract_host.openapi_spec', {str(source)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert '/plugin-data/records' in module.generate_openapi_spec()['paths']
assert 'src' not in sys.modules
assert 'astrbot' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_standalone_export_needs_no_host(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-I", str(root / "scripts/export_openapi.py"), "--check"],
        cwd=tmp_path,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
