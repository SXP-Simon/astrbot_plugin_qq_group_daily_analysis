"""WebUI 静态资源缓存与 Plugin Data 存储可观测性后端 API 接口测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.repositories.resource_cache_repository import (
    IResourceCacheRepository,
)
from src.infrastructure.webui.plugin_page_bridge import (
    PluginPageWebUIBridge,
)


class MockResourceCacheRepository(IResourceCacheRepository):
    """内存模拟静态资源缓存仓储。"""

    def __init__(self):
        self._store: dict[str, tuple[bytes, str | None, str | None]] = {}

    async def get(self, url: str, template: str | None = None) -> bytes | None:
        return self._store.get(url, (None, None, None))[0]

    async def set(
        self,
        url: str,
        data: bytes,
        mime_type: str | None = None,
        template: str | None = None,
    ) -> Path:
        self._store[url] = (data, mime_type, template)
        return Path(f"/mock/cache/{hash(url)}")

    async def get_path(
        self, url: str, template: str | None = None
    ) -> Path | None:
        return Path(f"/mock/cache/{hash(url)}")

    async def has(self, url: str, template: str | None = None) -> bool:
        return url in self._store

    async def get_or_download(
        self,
        url: str,
        custom_headers: dict[str, str] | None = None,
        timeout: float = 5.0,
        template: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        if url in self._store:
            item = self._store[url]
            return item[0], item[1]
        return None, None

    def get_stats(self):
        return {
            "total_files": len(self._store),
            "total_bytes": sum(len(d[0]) for d in self._store.values()),
            "total_access_count": len(self._store),
            "by_category": {
                "fonts": {"files": len(self._store), "bytes": 0},
            },
            "by_template": {
                "scrapbook": {
                    "files": len(self._store),
                    "bytes": 0,
                    "access_count": len(self._store),
                    "categories": {"fonts": len(self._store)},
                }
            },
        }

    async def list_resources(
        self, template: str | None = None, category: str | None = None
    ):
        return [
            {
                "url": u,
                "hash": "abc",
                "template": tmpl or "global",
                "category": "fonts",
                "mime_type": mime,
                "size": len(data),
                "file_path": f"/mock/cache/{hash(u)}",
                "access_count": 1,
            }
            for u, (data, mime, tmpl) in self._store.items()
        ]

    async def clear_cache(
        self, template: str | None = None, category: str | None = None
    ):
        count = len(self._store)
        self._store.clear()
        return {"deleted_files": count, "freed_bytes": 1024, "freed_mb": 0.0}


@pytest.mark.asyncio
async def test_api_get_resource_cache(tmp_path: Path):
    """测试获取静态资源缓存列表与统计指标 API。"""
    repo = MockResourceCacheRepository()
    await repo.set(
        "https://fonts.com/a.woff2",
        b"123",
        "font/woff2",
        template="scrapbook",
    )

    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=MagicMock(),
        active_task_manager=MagicMock(),
        analysis_service=MagicMock(),
        resource_cache_repo=repo,
        plugin_data_dir=tmp_path,
    )

    resp = await bridge.api_get_resource_cache()
    # 验证响应格式（dict 或 Response）
    data = resp.get("data") if isinstance(resp, dict) else resp
    assert data is not None
    assert data["status"] == "ok"
    assert data["data"]["stats"]["total_files"] == 1
    assert len(data["data"]["resources"]) == 1
    assert data["data"]["resources"][0]["template"] == "scrapbook"


@pytest.mark.asyncio
async def test_api_clear_resource_cache(tmp_path: Path):
    """测试清理指定模板静态资源缓存 API。"""
    repo = MockResourceCacheRepository()
    await repo.set(
        "https://fonts.com/a.woff2",
        b"123",
        "font/woff2",
        template="scrapbook",
    )

    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=MagicMock(),
        active_task_manager=MagicMock(),
        analysis_service=MagicMock(),
        resource_cache_repo=repo,
        plugin_data_dir=tmp_path,
    )

    resp = await bridge.api_clear_resource_cache()
    data = resp.get("data") if isinstance(resp, dict) else resp
    assert data is not None
    assert data["status"] == "ok"
    assert data["data"]["deleted_files"] == 1


@pytest.mark.asyncio
async def test_api_trigger_resource_prefetch(tmp_path: Path):
    """测试手动触发全量模板静态资源预取 API。"""
    prefetch_svc = MagicMock()
    prefetch_svc.prefetch_all_templates = AsyncMock(
        return_value={"templates": ["scrapbook"]}
    )

    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=MagicMock(),
        active_task_manager=MagicMock(),
        analysis_service=MagicMock(),
        resource_prefetch_service=prefetch_svc,
        plugin_data_dir=tmp_path,
    )

    resp = await bridge.api_trigger_resource_prefetch()
    data = resp.get("data") if isinstance(resp, dict) else resp
    assert data is not None
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_api_get_storage_overview(tmp_path: Path):
    """测试获取 plugin_data 内部各模块磁盘空间占用 API。"""
    (tmp_path / "traces.sqlite").write_bytes(b"dummy-sqlite-data")
    cache_fonts = (
        tmp_path
        / "cache"
        / "resources"
        / "templates"
        / "scrapbook"
        / "fonts"
    )
    cache_fonts.mkdir(parents=True, exist_ok=True)
    (cache_fonts / "font.woff2").write_bytes(b"font-data-12345")

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "rep.png").write_bytes(b"img-bytes")

    repo = MockResourceCacheRepository()
    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=MagicMock(),
        active_task_manager=MagicMock(),
        analysis_service=MagicMock(),
        resource_cache_repo=repo,
        plugin_data_dir=tmp_path,
    )

    resp = await bridge.api_get_storage_overview()
    data = resp.get("data") if isinstance(resp, dict) else resp
    assert data is not None
    assert data["status"] == "ok"
    payload = data["data"]
    assert "total" in payload
    assert "database" in payload
    assert "resources_cache" in payload
    assert "reports" in payload
    assert payload["total"]["bytes"] > 0
