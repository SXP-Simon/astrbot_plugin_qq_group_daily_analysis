"""验证请求兼容层优先使用宿主上下文，避免模块扫描与跨请求污染。"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from types import SimpleNamespace

import pytest

from src.infrastructure.webui import web_compat


class NoScanModules(dict):
    """在正式请求路径意外扫描模块注册表时立即失败。"""

    def items(self):
        raise AssertionError("正式请求不应扫描 sys.modules")

    def __iter__(self):
        raise AssertionError("正式请求不应扫描 sys.modules")

    def keys(self):
        raise AssertionError("正式请求不应扫描 sys.modules")

    def values(self):
        raise AssertionError("正式请求不应扫描 sys.modules")


@pytest.mark.parametrize("access", ["__iter__", "items", "keys", "values"])
def test_module_scan_guard_rejects_iteration(access):
    """守卫自身应拦截逐键遍历以及各类字典视图扫描。"""
    registry = NoScanModules({"example": object()})
    with pytest.raises(AssertionError, match="不应扫描"):
        getattr(registry, access)()


@pytest.mark.parametrize("attribute", ["query", "query_params", "headers", "files"])
def test_host_request_does_not_scan_modules(monkeypatch, attribute):
    """读取请求属性应直接使用宿主代理，不受模块数量影响。"""
    target = SimpleNamespace(
        query={"limit": "10"},
        headers={"x-request-id": "current"},
        files={"report": object()},
    )
    monkeypatch.setattr(web_compat, "_real_request", target)
    monkeypatch.setattr(web_compat, "sys", SimpleNamespace(modules=NoScanModules()))

    value = getattr(web_compat._RequestProxy(), attribute)
    expected = (
        target.query if attribute == "query_params" else getattr(target, attribute)
    )
    assert value == expected


def test_host_request_takes_priority_over_foreign_plugin(monkeypatch):
    """其他插件的同名变量不能覆盖宿主绑定的当前请求。"""
    target = SimpleNamespace(query={"search": "current"})
    foreign = SimpleNamespace(request=SimpleNamespace(query={"search": "foreign"}))
    monkeypatch.setattr(web_compat, "_real_request", target)
    monkeypatch.setattr(
        web_compat,
        "sys",
        SimpleNamespace(modules={"other_plugin.infrastructure.webui.routes": foreign}),
    )

    assert web_compat._RequestProxy().query == {"search": "current"}


def test_falsey_host_request_is_not_discarded(monkeypatch):
    """宿主请求的真假值不应参与请求对象的选择。"""

    class FalseyRequest:
        def __init__(self):
            self.query = {"limit": "0"}

        def __bool__(self):
            return False

    target = FalseyRequest()
    monkeypatch.setattr(web_compat, "_real_request", target)
    monkeypatch.setattr(web_compat, "sys", SimpleNamespace(modules=NoScanModules()))

    assert web_compat._RequestProxy()._get_target() is target


def test_host_proxy_with_same_class_name_is_not_discarded(monkeypatch):
    """宿主代理即使与本地兼容代理同名，也应保留当前请求数据。"""
    host_proxy_type = type("_RequestProxy", (), {"query": {"limit": "10"}})
    target = host_proxy_type()
    monkeypatch.setattr(web_compat, "_real_request", target)
    monkeypatch.setattr(web_compat, "sys", SimpleNamespace(modules=NoScanModules()))

    assert web_compat._RequestProxy()._get_target() is target
    assert web_compat._RequestProxy().query == {"limit": "10"}


@pytest.mark.asyncio
async def test_concurrent_requests_keep_host_context(monkeypatch):
    """异步请求切换后仍读取各自的查询、标头及 JSON，不能缓存具体请求。"""
    current = ContextVar("test_web_request")

    class HostProxy:
        @property
        def query(self):
            return {"request_id": current.get()}

        @property
        def headers(self):
            return {"x-request-id": current.get()}

        async def json(self):
            await asyncio.sleep(0)
            return {"request_id": current.get()}

    monkeypatch.setattr(web_compat, "_real_request", HostProxy())
    monkeypatch.setattr(web_compat, "sys", SimpleNamespace(modules=NoScanModules()))
    proxy = web_compat._RequestProxy()

    async def read_request(request_id):
        token = current.set(request_id)
        try:
            await asyncio.sleep(0)
            assert proxy.query == {"request_id": request_id}
            assert proxy.headers == {"x-request-id": request_id}
            assert await proxy.json() == {"request_id": request_id}
        finally:
            current.reset(token)

    await asyncio.gather(read_request("first"), read_request("second"))


@pytest.mark.parametrize(
    "module_name",
    [
        "other_plugin.infrastructure.webui.routes",
        "src.infrastructure.webui.unrelated",
        "src.infrastructure.webui.plugin_page_bridge_extra",
        "astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.unrelated",
    ],
)
def test_fallback_ignores_foreign_webui_module(monkeypatch, module_name):
    """无宿主接口时，也不能误选其他插件的测试请求。"""
    monkeypatch.setattr(web_compat, "_real_request", None)
    monkeypatch.setattr(
        web_compat,
        "sys",
        SimpleNamespace(
            modules={
                module_name: SimpleNamespace(
                    request=SimpleNamespace(query={"search": "foreign"})
                )
            }
        ),
    )

    assert web_compat._RequestProxy().query == {}


@pytest.mark.parametrize(
    "package_name",
    [
        "src.infrastructure.webui",
        "astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui",
        "data.plugins.astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui",
    ],
)
@pytest.mark.parametrize(
    "bridge_name",
    [
        "src.infrastructure.webui.plugin_page_bridge",
        "astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.plugin_page_bridge",
    ],
)
def test_fallback_preserves_local_bridge_mock(monkeypatch, package_name, bridge_name):
    """无宿主接口的离线单测仍可在本插件桥接模块替换请求。"""
    monkeypatch.setattr(web_compat, "_real_request", None)
    monkeypatch.setattr(web_compat, "__package__", package_name)
    monkeypatch.setattr(
        web_compat,
        "sys",
        SimpleNamespace(
            modules=NoScanModules(
                {
                    bridge_name: SimpleNamespace(
                        request=SimpleNamespace(query={"limit": "10"})
                    )
                }
            )
        ),
    )

    assert web_compat._RequestProxy().query == {"limit": "10"}


def test_fallback_preserves_current_package_bridge_mock(monkeypatch):
    """宿主通过额外包前缀加载插件时，应按当前包名直接查找桥接。"""
    package_name = (
        "data.plugins.astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui"
    )
    monkeypatch.setattr(web_compat, "__package__", package_name)
    monkeypatch.setattr(web_compat, "_real_request", None)
    monkeypatch.setattr(
        web_compat,
        "sys",
        SimpleNamespace(
            modules={
                f"{package_name}.plugin_page_bridge": SimpleNamespace(
                    request=SimpleNamespace(query={"limit": "10"})
                )
            }
        ),
    )

    assert web_compat._RequestProxy().query == {"limit": "10"}
