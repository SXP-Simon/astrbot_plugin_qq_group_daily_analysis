"""验证素材缩放的内存优化保留颜色模式、透明度和原有采样像素。"""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from src.infrastructure.reporting.typst_resources import TypstAssets


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "P", "RGB-transparent", "JPEG", "CMYK"])
@pytest.mark.parametrize("opacity", [1.0, .18])
def test_resize_keeps_legacy_rgba_pixels(tmp_path, mode, opacity):
    image = Image.new(
        "RGBA" if mode == "RGBA" else "RGB", (8000, 16),
        (0, 128, 255, 0) if mode == "RGBA" else (0, 128, 255),
    )
    ImageDraw.Draw(image).rectangle(
        (2000, 0, 6000, 15), fill=(200, 20, 60, 137) if mode == "RGBA" else (200, 20, 60),
    )
    options = {}
    if mode == "P":
        image = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
        options["transparency"] = 0
    elif mode == "RGB-transparent":
        options["transparency"] = (0, 128, 255)
    elif mode == "CMYK":
        image = image.convert("CMYK")
    payload = BytesIO()
    image.save(payload, format="JPEG" if mode in ("JPEG", "CMYK") else "PNG", **options)
    data = payload.getvalue()
    # 原版先转换 RGBA 再缩放，作为既有采样行为的参考。
    with Image.open(BytesIO(data)) as original:
        expected = original.convert("RGBA")
        expected.thumbnail((1600, 1600))
        if opacity < 1:
            expected.putalpha(expected.getchannel("A").point(lambda a: int(a * opacity)))
    target, cached = tmp_path / "job.png", tmp_path / "cache.png"
    TypstAssets._save_image(data, target, cached, opacity)
    with Image.open(target) as result:
        assert result.mode == "RGBA" and result.size == expected.size
        assert result.tobytes() == expected.tobytes()
    assert target.read_bytes() == cached.read_bytes()
