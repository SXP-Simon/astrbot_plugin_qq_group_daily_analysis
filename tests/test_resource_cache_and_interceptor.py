"""静态资源持久化缓存、拦截器及 HTML 本地化流水线单元测试。"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.application.services.resource_prefetch_service import (
    ResourcePrefetchService,
)
from src.domain.repositories.resource_cache_repository import (
    IResourceCacheRepository,
)
from src.infrastructure.resources.html_resource_localizer import (
    HTMLResourceLocalizer,
)
from src.infrastructure.resources.interceptors.base import BaseResourceInterceptor
from src.infrastructure.resources.interceptors.css_stylesheet_interceptor import (
    CssStylesheetInterceptor,
)
from src.infrastructure.resources.interceptors.font_face_interceptor import (
    FontFaceInterceptor,
)
from src.infrastructure.resources.interceptors.google_fonts_interceptor import (
    GoogleFontsInterceptor,
)
from src.infrastructure.resources.interceptors.preconnect_interceptor import (
    PreconnectInterceptor,
)
from src.infrastructure.resources.interceptors.remote_image_interceptor import (
    RemoteImageInterceptor,
)
from src.infrastructure.resources.interceptors.remote_script_interceptor import (
    RemoteScriptInterceptor,
)
from src.infrastructure.resources.resource_cache_repository import (
    FileSystemResourceCacheRepository,
)


class MockResourceCacheRepository(IResourceCacheRepository):
    """内存模拟资源缓存仓储，用于快速、确定性的单元测试。"""

    def __init__(self):
        self._store: dict[str, tuple[bytes, str | None]] = {}

    async def get(self, url: str) -> bytes | None:
        return self._store.get(url, (None, None))[0]

    async def set(
        self, url: str, data: bytes, mime_type: str | None = None
    ) -> Path:
        self._store[url] = (data, mime_type)
        return Path(f"/mock/cache/{hash(url)}")

    async def get_path(self, url: str) -> Path | None:
        if url in self._store:
            return Path(f"/mock/cache/{hash(url)}")
        return None

    async def has(self, url: str) -> bool:
        return url in self._store

    async def get_or_download(
        self,
        url: str,
        custom_headers: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> tuple[bytes | None, str | None]:
        if url in self._store:
            return self._store[url]
        # 未命中时生成模拟数据
        dummy_data = f"/* content of {url} */".encode("utf-8")
        mime = "application/octet-stream"
        if url.endswith(".woff2") or "woff2" in url:
            mime = "font/woff2"
        elif url.endswith(".css") or "css" in url:
            mime = "text/css"
        elif url.endswith(".png"):
            mime = "image/png"
        elif url.endswith(".js"):
            mime = "application/javascript"
        self._store[url] = (dummy_data, mime)
        return dummy_data, mime

    def get_stats(self) -> dict[str, int]:
        return {
            "total_files": len(self._store),
            "total_bytes": sum(len(d[0]) for d in self._store.values()),
            "fonts": sum(1 for u in self._store if "woff" in u or "font" in u),
            "css": sum(1 for u in self._store if "css" in u),
            "images": sum(1 for u in self._store if "png" in u or "image" in u),
            "scripts": sum(1 for u in self._store if "js" in u),
        }


@pytest.mark.asyncio
async def test_filesystem_resource_cache_repository(tmp_path: Path):
    """测试基于本地磁盘的文件缓存仓储基本增删查功能。"""
    repo = FileSystemResourceCacheRepository(tmp_path / "cache")
    test_url = "https://fonts.gstatic.com/s/notosans/v30/mock.woff2"
    test_data = b"dummy woff2 binary data"

    # 初始状态不在缓存中
    assert not await repo.has(test_url)
    assert await repo.get(test_url) is None

    # 保存至缓存
    saved_path = await repo.set(test_url, test_data, "font/woff2")
    assert saved_path.is_file()
    assert saved_path.read_bytes() == test_data

    # 从缓存中读取
    assert await repo.has(test_url)
    cached_data = await repo.get(test_url)
    assert cached_data == test_data

    # get_or_download 命中缓存
    data, mime = await repo.get_or_download(test_url)
    assert data == test_data
    assert mime == "font/woff2"

    stats = repo.get_stats()
    assert stats["total_files"] == 1
    assert stats["fonts"] == 1
    assert stats["total_bytes"] == len(test_data)
    await repo.close()


@pytest.mark.asyncio
async def test_google_fonts_interceptor():
    """测试 Google Fonts <link> 与 @import 拦截及 WOFF2 字体切片内联。"""
    mock_repo = MockResourceCacheRepository()
    interceptor = GoogleFontsInterceptor(mock_repo)

    css_url = "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap"
    font_woff2_url = (
        "https://fonts.gstatic.com/s/notosanssc/v36/mock_chunk.woff2"
    )
    raw_css = f"@font-face {{ font-family: 'Noto Sans SC'; src: url('{font_woff2_url}') format('woff2'); }}"
    font_bytes = b"\x00\x01\x02\x03\x04"

    # 预先填充 mock 仓储
    await mock_repo.set(css_url, raw_css.encode("utf-8"), "text/css")
    await mock_repo.set(font_woff2_url, font_bytes, "font/woff2")

    html_input = f"""
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="stylesheet" href="{css_url}">
    </head>
    <body>Hello</body>
    </html>
    """

    result_html = await interceptor.intercept(html_input)
    assert css_url not in result_html
    assert "<style data-localized-fonts='google-fonts'>" in result_html
    encoded_font = base64.b64encode(font_bytes).decode("ascii")
    assert f"data:font/woff2;base64,{encoded_font}" in result_html


@pytest.mark.asyncio
async def test_css_stylesheet_interceptor():
    """测试通用外部样式表链接拦截及递归子资源内联。"""
    mock_repo = MockResourceCacheRepository()
    interceptor = CssStylesheetInterceptor(mock_repo)

    stylesheet_url = "https://cdn.jsdelivr.net/npm/@proj-airi/font-cjkfonts-allseto@0.9.0/dist/index.css"
    nested_font_url = "https://cdn.jsdelivr.net/npm/@proj-airi/font-cjkfonts-allseto@0.9.0/dist/allseto.woff2"
    raw_css = (
        f"@font-face {{ font-family: 'AllSeto'; src: url('{nested_font_url}'); }}"
    )
    font_bytes = b"font-binary-12345"

    await mock_repo.set(stylesheet_url, raw_css.encode("utf-8"), "text/css")
    await mock_repo.set(nested_font_url, font_bytes, "font/woff2")

    html_input = f"""
    <head>
        <link rel="stylesheet" href="{stylesheet_url}">
    </head>
    """

    result_html = await interceptor.intercept(html_input)
    assert stylesheet_url not in result_html
    assert "<style data-localized-stylesheet='true'>" in result_html
    encoded_font = base64.b64encode(font_bytes).decode("ascii")
    assert f"data:font/woff2;base64,{encoded_font}" in result_html


@pytest.mark.asyncio
async def test_font_face_interceptor():
    """测试 CSS @font-face 外部字体链接直接转换为 Base64 Data URI。"""
    mock_repo = MockResourceCacheRepository()
    interceptor = FontFaceInterceptor(mock_repo)

    atri_font_url = "https://tc.ciallo.ccwu.cc/file/1775130743963_LXGWWenKai-Regular.woff2"
    font_bytes = b"atri-font-bytes-999"
    await mock_repo.set(atri_font_url, font_bytes, "font/woff2")

    html_input = f"""
    <style>
        @font-face {{
            font-family: 'LXGWWenKai';
            src: url('{atri_font_url}') format('woff2');
        }}
    </style>
    """

    result_html = await interceptor.intercept(html_input)
    assert atri_font_url not in result_html
    encoded_font = base64.b64encode(font_bytes).decode("ascii")
    assert f"data:font/woff2;base64,{encoded_font}" in result_html


@pytest.mark.asyncio
async def test_remote_image_interceptor(tmp_path: Path):
    """测试远程图片拦截与本地插件 assets 零网络直读。"""
    # 创建模拟本地插件静态文件
    assets_dir = tmp_path / "assets" / "HatsuneMiku"
    assets_dir.mkdir(parents=True, exist_ok=True)
    local_img_file = assets_dir / "deco.png"
    local_img_bytes = b"local-png-data"
    local_img_file.write_bytes(local_img_bytes)

    mock_repo = MockResourceCacheRepository()
    interceptor = RemoteImageInterceptor(mock_repo, plugin_root=tmp_path)

    remote_img_url = "https://img.dkdun.cn/v1/2026/17/aron.png"
    remote_bytes = b"remote-png-bytes"
    await mock_repo.set(remote_img_url, remote_bytes, "image/png")

    local_asset_url = (
        "https://fastly.jsdelivr.net/gh/owner/repo@main/assets/HatsuneMiku/deco.png"
    )

    html_input = f"""
    <div>
        <img class="aron" src="{remote_img_url}" alt="aron">
        <div style="background-image: url('{local_asset_url}');"></div>
    </div>
    """

    result_html = await interceptor.intercept(html_input)
    assert remote_img_url not in result_html
    assert local_asset_url not in result_html

    encoded_remote = base64.b64encode(remote_bytes).decode("ascii")
    encoded_local = base64.b64encode(local_img_bytes).decode("ascii")
    assert f"data:image/png;base64,{encoded_remote}" in result_html
    assert f"data:image/png;base64,{encoded_local}" in result_html


@pytest.mark.asyncio
async def test_remote_script_and_preconnect_interceptors():
    """测试远程脚本内联与 preconnect 标签剔除。"""
    mock_repo = MockResourceCacheRepository()
    script_interceptor = RemoteScriptInterceptor(mock_repo)
    preconnect_interceptor = PreconnectInterceptor(mock_repo)

    script_url = "https://unpkg.com/lucide@latest"
    script_code = b"console.log('lucide loaded');"
    await mock_repo.set(script_url, script_code, "application/javascript")

    html_input = f"""
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="dns-prefetch" href="https://fonts.gstatic.com">
        <script src="{script_url}"></script>
    </head>
    """

    res = await script_interceptor.intercept(html_input)
    assert f'src="{script_url}"' not in res
    assert "<script data-localized-script='true'>" in res
    assert "console.log('lucide loaded');" in res

    res2 = await preconnect_interceptor.intercept(res)
    assert 'rel="preconnect"' not in res2
    assert 'rel="dns-prefetch"' not in res2


@pytest.mark.asyncio
async def test_html_resource_localizer_full_pipeline(tmp_path: Path):
    """测试 HTMLResourceLocalizer 完整流水线端到端 0 外链效果。"""
    mock_repo = MockResourceCacheRepository()
    localizer = HTMLResourceLocalizer(mock_repo, plugin_root=tmp_path)

    # 预设多种静态资源
    google_css = (
        "https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&display=swap"
    )
    font_chunk = "https://fonts.gstatic.com/s/zcoolkuaile/v1/zcool.woff2"
    await mock_repo.set(
        google_css,
        f"@font-face {{ font-family: 'ZCOOL'; src: url('{font_chunk}'); }}".encode(),
        "text/css",
    )
    await mock_repo.set(font_chunk, b"font-binary", "font/woff2")

    direct_font = "https://tc.ciallo.ccwu.cc/file/LXGWWenKai-Regular.woff2"
    await mock_repo.set(direct_font, b"direct-font-binary", "font/woff2")

    img_url = "https://img.dkdun.cn/aron.png"
    await mock_repo.set(img_url, b"png-binary", "image/png")

    html_source = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="stylesheet" href="{google_css}">
        <style>
            @font-face {{
                font-family: 'LXGW';
                src: url('{direct_font}') format('woff2');
            }}
        </style>
    </head>
    <body>
        <img src="{img_url}">
    </body>
    </html>
    """

    localized_html = await localizer.localize_html(html_source)

    # 验证最终 HTML 中无任何外部网络外链
    assert "https://fonts.googleapis.com" not in localized_html
    assert "https://fonts.gstatic.com" not in localized_html
    assert direct_font not in localized_html
    assert img_url not in localized_html
    assert "preconnect" not in localized_html
    assert "data:font/woff2;base64," in localized_html
    assert "data:image/png;base64," in localized_html


@pytest.mark.asyncio
async def test_open_closed_principle_extensibility():
    """验证拦截器流水线开闭原则扩展性（无需修改已有代码即可添加新类型拦截器）。"""
    mock_repo = MockResourceCacheRepository()
    localizer = HTMLResourceLocalizer(mock_repo)

    class CustomSvgInterceptor(BaseResourceInterceptor):
        async def intercept(self, content: str, context=None) -> str:
            return content.replace(
                "EXTERNAL_SVG_PLACEHOLDER", "<svg>inlined</svg>"
            )

    localizer.add_interceptor(CustomSvgInterceptor(mock_repo))

    input_html = "<div>EXTERNAL_SVG_PLACEHOLDER</div>"
    output_html = await localizer.localize_html(input_html)
    assert "<svg>inlined</svg>" in output_html


@pytest.mark.asyncio
async def test_resource_prefetch_service():
    """测试 ResourcePrefetchService 模板扫描与资源预热。"""
    mock_repo = MockResourceCacheRepository()
    localizer = HTMLResourceLocalizer(mock_repo)

    mock_templates = MagicMock()
    mock_templates.get_available_templates.return_value = [
        {"id": "scrapbook", "label": "Scrapbook"},
        {"id": "ATRI", "label": "ATRI"},
    ]
    mock_templates.base_dir = "/mock/templates"
    mock_templates.config_manager = MagicMock()
    mock_templates.render_template.return_value = """
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=ScrapbookFont">
    """

    service = ResourcePrefetchService(localizer, mock_templates)
    result = await service.prefetch_all_templates()

    assert "scrapbook" in result["templates"]
    assert "ATRI" in result["templates"]
    assert result["stats"]["total_files"] >= 1
