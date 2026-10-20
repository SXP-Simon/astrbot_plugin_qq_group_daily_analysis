"""验证词云模板隔离、远端资源与框架渲染契约。"""

import os
import time
from dataclasses import replace
from pathlib import Path

import pytest

from src.domain.value_objects.wordcloud import (
    WordCloudData,
    WordCloudOptions,
    WordFrequency,
)
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.wordcloud_renderer import WordCloudRenderer


class ConfigStub:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_t2i_max_concurrent(self) -> int:
        return 2

    def get_custom_report_template_dir(self, name: str) -> Path:
        return self.root / "themes" / name

    def get_wordcloud_options(self, umo: str = "") -> WordCloudOptions:
        return WordCloudOptions()

    def get_t2i_atri_font_mirror(self) -> str:
        return "https://example.com/assets/ATRI"

    def get_template_assets_base_url(self) -> str:
        return "https://example.com/assets"


def sample() -> WordCloudData:
    return WordCloudData(
        frequencies=(WordFrequency("高性能", 20, 12), WordFrequency("亚托莉", 8, 6)),
        message_count=30,
        group_id="1234",
        date_str="2026-10-17",
    )


def test_builtin_assets_use_existing_cdn_and_data_cannot_close_script(
    tmp_path: Path,
) -> None:
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    data = replace(
        sample(),
        frequencies=(WordFrequency("</script><script>alert(1)</script>{{7*7}}", 4, 3),),
    )
    source = renderer.build_html(data)
    assert 'data-t2i-state="pending"' in source
    assert (
        "https://example.com/assets/ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2"
        in source
    )
    assert (
        'src="https://example.com/assets/ATRI/file/1775130626446_1774881312214_atri1.webp"'
        in source
    )
    assert (
        'src="https://example.com/assets/ATRI/file/1775130623112_1774881319340_atri4.webp"'
        in source
    )
    assert "data:font/woff2;base64," not in source
    assert "data:image/webp;base64," not in source
    assert '"\\u003c/script>' in source
    assert "{{7*7}}" in source
    assert len(source) < 50000


@pytest.mark.parametrize("mirror", ["", "https://old.example/ATRI"])
def test_builtin_font_and_portraits_follow_report_cdn_settings(
    tmp_path: Path, mirror: str
) -> None:
    config = object.__new__(ConfigManager)
    config.config = {
        "t2i_rendering": {
            "t2i_cdn_base_url": "https://new.example",
            "t2i_atri_font_mirror": mirror,
        }
    }
    renderer = WordCloudRenderer(config, tmp_path)
    expected = (
        mirror
        or "https://new.example/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/ATRI"
    )
    source = renderer.build_html(sample())
    assert expected + "/file/1775130626446_1774881312214_atri1.webp" in source
    assert renderer.font_uri("wenkai").startswith(expected + "/file/")
    assert expected in renderer.build_font_sample("wenkai")


@pytest.mark.parametrize(
    "path",
    ["../secret.woff2", "/ATRI/file/a.webp", "ATRI/../a.webp", "ATRI\\file/a.webp"],
)
def test_cdn_assets_reject_traversal(tmp_path: Path, path: str) -> None:
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    with pytest.raises(ValueError, match="CDN 素材路径无效"):
        renderer._cdn_asset_uri(path)


def test_remote_font_sample_waits_for_font_load_and_reports_failure(
    tmp_path: Path,
) -> None:
    source = WordCloudRenderer(ConfigStub(tmp_path), tmp_path).build_font_sample(
        "wenkai"
    )
    assert "await font.load();document.fonts.add(font)" in source
    assert "await document.fonts.ready" in source
    assert "catch{clearTimeout(timer);fail();}" in source
    assert "root.dataset.t2iState='error'" in source
    assert "字体加载失败，请检查模板 CDN 或上传字体" in source
    assert "if(finished)return" in source


def test_uploaded_font_remains_embedded_without_remote_font_dependency(
    tmp_path: Path,
) -> None:
    name = "a" * 64 + ".woff2"
    directory = tmp_path / "wordcloud_fonts"
    directory.mkdir()
    (directory / name).write_bytes(b"wOF2" + bytes(60))
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    source = renderer.build_html(sample(), WordCloudOptions(font="uploaded:" + name))
    assert "data:font/woff2;base64," in source
    assert "LXGWWenKai-Regular.woff2" not in source


def test_wordcloud_discovery_has_no_daily_report_fallback(tmp_path: Path) -> None:
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    themes = renderer.discover_templates()
    assert [entry.id for entry in themes] == ["ATRI"]
    with pytest.raises(ValueError, match="不支持词云"):
        renderer.build_html(sample(), WordCloudOptions(template="HatsuneMiku"))


def test_uploaded_font_is_local_and_path_is_validated(tmp_path: Path) -> None:
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    with pytest.raises(ValueError, match="标识无效"):
        renderer.build_html(
            sample(), WordCloudOptions(font="uploaded:../../secret.woff2")
        )
    with pytest.raises(ValueError, match="资源不存在"):
        renderer.build_html(
            sample(), WordCloudOptions(font="uploaded:" + "a" * 64 + ".woff2")
        )


@pytest.mark.asyncio
async def test_renderer_passes_session_and_reuses_only_same_appearance(
    tmp_path: Path,
) -> None:
    calls: list[tuple[dict[str, object], dict[str, object], str | None]] = []
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"

    async def render(tmpl, data, return_url, options, umo=None):
        assert tmpl == "{{ wordcloud_html | safe }}"
        assert return_url is False
        calls.append((data, options, umo))
        return png

    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path, render)
    first = await renderer.render(sample(), "bot:GroupMessage:1234")
    again = await renderer.render(sample(), "bot:GroupMessage:1234")
    changed = await renderer.render(
        sample(), "bot:GroupMessage:1234", WordCloudOptions(word_spacing=4)
    )
    assert first == again
    assert first != changed
    assert len(calls) == 2
    assert calls[0][2] == "bot:GroupMessage:1234"
    assert calls[0][1]["viewport_width"] == 1200
    assert calls[0][1]["viewport_height"] == 900
    assert Path(first).read_bytes() == png


@pytest.mark.asyncio
async def test_invalid_renderer_payload_is_not_cached(tmp_path: Path) -> None:
    async def render(_tmpl, _data, _return_url, _options, **_kwargs):
        return b"<html>upstream failed</html>"

    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path, render)
    with pytest.raises(RuntimeError, match="不是 PNG"):
        await renderer.render(sample())
    assert not (tmp_path / "wordcloud_images").exists()


def test_image_retention_preserves_active_and_pending_files(tmp_path: Path) -> None:
    renderer = WordCloudRenderer(ConfigStub(tmp_path), tmp_path)
    image_dir = tmp_path / "wordcloud_images"
    image_dir.mkdir()
    old = time.time() - 7200
    for i in range(260):
        path = image_dir / f"{i:03}.png"
        path.write_bytes(b"cached")
        os.utime(path, (old + i, old + i))
    active = image_dir / "000.png"
    renderer._active_images.add(active)
    expired = image_dir / "expired.png"
    expired.write_bytes(b"expired")
    os.utime(expired, (old - 31 * 86400, old - 31 * 86400))
    pending = image_dir / "writing.tmp"
    pending.write_bytes(b"pending")
    renderer._store_image(image_dir / "new.png", b"current")
    assert active.exists()
    assert pending.exists()
    assert not expired.exists()
    assert len(list(image_dir.glob("*.png"))) <= 257
    assert (image_dir / "new.png").read_bytes() == b"current"
    renderer._active_images.clear()
    renderer._store_image(image_dir / "newer.png", b"next")
    assert len(list(image_dir.glob("*.png"))) <= 256
