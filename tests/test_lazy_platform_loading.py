"""Tests for on-demand lazy platform loading and Lark removal."""

import pytest
from src.domain.value_objects.platform_capabilities import get_capabilities
from src.infrastructure.platform.factory import PlatformAdapterFactory
from src.shared.constants import Platform


def test_feishu_and_lark_are_not_supported():
    """Verify Lark/Feishu is completely removed from platform factory and domain objects."""
    assert not PlatformAdapterFactory.is_supported("lark")
    assert not PlatformAdapterFactory.is_supported("feishu")
    assert get_capabilities("lark") is None
    assert get_capabilities("feishu") is None
    assert not hasattr(Platform, "LARK")


def test_supported_platforms_registration():
    """Verify standard platforms are supported without eager instantiation."""
    supported = PlatformAdapterFactory.get_supported_platforms()
    for name in [
        "onebot",
        "aiocqhttp",
        "telegram",
        "discord",
        "discord_bot",
        "qq_official",
        "qq_official_webhook",
    ]:
        assert name in supported
        assert PlatformAdapterFactory.is_supported(name)


def test_lazy_adapter_resolution():
    """Verify get_adapter_class dynamically loads adapter classes."""
    qq_cls = PlatformAdapterFactory.get_adapter_class("qq_official")
    assert qq_cls is not None
    assert qq_cls.__name__ == "QQOfficialAdapter"

    onebot_cls = PlatformAdapterFactory.get_adapter_class("onebot")
    assert onebot_cls is not None
    assert onebot_cls.__name__ == "OneBotAdapter"


def test_lazy_imports_from_platform_package():
    """Verify __getattr__ dynamically resolves exports from platform package."""
    from src.infrastructure import platform
    from src.infrastructure.platform import adapters

    assert hasattr(platform, "OneBotAdapter")
    assert hasattr(platform, "QQOfficialAdapter")
    assert hasattr(adapters, "OneBotAdapter")
    assert hasattr(adapters, "QQOfficialAdapter")

    with pytest.raises(AttributeError):
        _ = platform.LarkAdapter

    with pytest.raises(AttributeError):
        _ = adapters.LarkAdapter


def test_importing_factory_does_not_import_sdk_modules():
    """Verify importing factory does not eagerly import heavy SDK modules."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    plugin_root = Path(__file__).resolve().parents[1]
    astrbot_root = plugin_root.parents[2] if len(plugin_root.parents) >= 3 else None

    code = (
        "import sys, types, logging\n"
        "astrbot = types.ModuleType('astrbot')\n"
        "astrbot_api = types.ModuleType('astrbot.api')\n"
        "astrbot_api.logger = logging.getLogger('astrbot-test')\n"
        "astrbot.api = astrbot_api\n"
        "sys.modules.setdefault('astrbot', astrbot)\n"
        "sys.modules.setdefault('astrbot.api', astrbot_api)\n"
        "from src.infrastructure.platform.factory import PlatformAdapterFactory\n"
        "assert 'lark_oapi' not in sys.modules, 'lark_oapi should not be imported'\n"
        "assert 'discord' not in sys.modules, 'discord should not be imported'\n"
        "assert 'telegram' not in sys.modules, 'telegram should not be imported'\n"
        "assert 'src.infrastructure.platform.adapters.discord_adapter' not in sys.modules\n"
        "assert 'src.infrastructure.platform.adapters.telegram_adapter' not in sys.modules\n"
        "print('OK')\n"
    )
    env = os.environ.copy()
    search_paths = [str(plugin_root)]
    if astrbot_root and astrbot_root.exists():
        search_paths.append(str(astrbot_root))
    search_paths.extend(sys.path)
    env["PYTHONPATH"] = os.pathsep.join(search_paths)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "OK" in result.stdout


