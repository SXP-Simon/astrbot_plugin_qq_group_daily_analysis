"""Typst 字体预设的状态查询与受管理目录下载。"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, TypedDict

import aiohttp

if TYPE_CHECKING:
    from pathlib import Path

# 字体始终写入插件 data 目录；来源是固定上游，不接受任意下载 URL 或目标路径。
FONT_SOURCES = {
    "NotoSansSC.ttf": "gh/google/fonts@main/ofl/notosanssc/NotoSansSC[wght].ttf",
    "NotoSansTC.ttf": "gh/google/fonts@main/ofl/notosanstc/NotoSansTC[wght].ttf",
    "NotoSansJP.ttf": "gh/google/fonts@main/ofl/notosansjp/NotoSansJP[wght].ttf",
    "NotoSansSymbols2.ttf": "gh/google/fonts@main/ofl/notosanssymbols2/NotoSansSymbols2-Regular.ttf",
    "NotoColorEmoji.ttf": "gh/googlefonts/noto-emoji@main/2D/fonts/Noto-COLRv1.ttf",
    "Outfit.ttf": "gh/google/fonts@main/ofl/outfit/Outfit[wght].ttf",
    "ShareTechMono.ttf": "gh/google/fonts@main/ofl/sharetechmono/ShareTechMono-Regular.ttf",
    "Inter.ttf": "gh/google/fonts@main/ofl/inter/Inter[opsz,wght].ttf",
    "JetBrainsMono.ttf": "gh/google/fonts@main/ofl/jetbrainsmono/JetBrainsMono[wght].ttf",
    "Oswald.ttf": "gh/google/fonts@main/ofl/oswald/Oswald[wght].ttf",
    "PatrickHand.ttf": "gh/google/fonts@main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "ZCOOLKuaiLe.ttf": "gh/google/fonts@main/ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf",
    "ZCOOLXiaoWei.ttf": "gh/google/fonts@main/ofl/zcoolxiaowei/ZCOOLXiaoWei-Regular.ttf",
    "MaShanZheng.ttf": "gh/google/fonts@main/ofl/mashanzheng/MaShanZheng-Regular.ttf",
    # 完整可变宋体提供与 HTML 一致的字体名和全部字重，文件超过 CDN 体积限制。
    "NotoSerifSC.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC[wght].ttf",
    "NotoSerifTC.ttf": "gh/google/fonts@main/ofl/notoseriftc/NotoSerifTC[wght].ttf",
    "Cinzel.ttf": "gh/google/fonts@main/ofl/cinzel/Cinzel[wght].ttf",
    "CormorantGaramond.ttf": "gh/google/fonts@main/ofl/cormorantgaramond/CormorantGaramond[wght].ttf",
    "CormorantGaramond-Italic.ttf": "gh/google/fonts@main/ofl/cormorantgaramond/CormorantGaramond-Italic[wght].ttf",
    # 与原 ATRI 字体相同的 1.522 版；单文件超过 CDN 体积限制，直接读取固定官方源。
    "LXGWWenKai.ttf": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKai-Regular.ttf",
    "LXGWWenKai-Medium.ttf": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKai-Medium.ttf",
    "LXGWWenKaiMono.ttf": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKaiMono-Regular.ttf",
    # BlueArchive 使用完整桌面字库，避免编译期间加载网页字体分片。
    "BlueakaBeta2GBK-DemiBold.ttf": "gh/ApricotLemonTea/BA-style-homepage@d7e9acd5d716d46cee066c59ea323b15f279d217/src/assets/font/BlueakaBeta2GBK-DemiBold.ttf",
    "BlueakaBeta2GBK-Bold.ttf": "gh/ApricotLemonTea/BA-style-homepage@d7e9acd5d716d46cee066c59ea323b15f279d217/src/assets/font/BlueakaBeta2GBK-Bold.ttf",
}

BASE_FONTS = (
    "NotoSansSC.ttf",
    "NotoSansTC.ttf",
    "NotoSansJP.ttf",
    "NotoSansSymbols2.ttf",
    "NotoColorEmoji.ttf",
)
# 共享字库覆盖正文、特殊字符与基础恢复；其余文件保持各主题原有字体和字重。
THEME_FONTS = {
    theme: BASE_FONTS + fonts
    for theme, fonts in {
        "HatsuneMiku": ("Outfit.ttf", "ShareTechMono.ttf", "Inter.ttf"),
        "simple": (),
        # JetBrains Mono 的中文等宽回退需要保留，避免按需安装后改变字形。
        "hack": ("Inter.ttf", "JetBrainsMono.ttf", "LXGWWenKaiMono.ttf"),
        "maria": (
            "NotoSerifSC.ttf",
            "NotoSerifTC.ttf",
            "Cinzel.ttf",
            "CormorantGaramond.ttf",
            "CormorantGaramond-Italic.ttf",
            "JetBrainsMono.ttf",
        ),
        "ATRI": ("LXGWWenKai.ttf", "LXGWWenKai-Medium.ttf", "LXGWWenKaiMono.ttf"),
        "deepseek_maid": ("JetBrainsMono.ttf",),
        "art_nouveau": (
            "NotoSerifSC.ttf",
            "NotoSerifTC.ttf",
            "Cinzel.ttf",
            "CormorantGaramond.ttf",
            "CormorantGaramond-Italic.ttf",
            "JetBrainsMono.ttf",
        ),
        "scrapbook": (
            "PatrickHand.ttf",
            "ZCOOLKuaiLe.ttf",
            "LXGWWenKai.ttf",
            "LXGWWenKai-Medium.ttf",
        ),
        "format": ("Inter.ttf", "NotoSerifSC.ttf", "NotoSerifTC.ttf"),
        "spring_festival": (
            "ZCOOLXiaoWei.ttf",
            "MaShanZheng.ttf",
            "NotoSerifSC.ttf",
            "NotoSerifTC.ttf",
        ),
        "retro_futurism": (
            "Oswald.ttf",
            "JetBrainsMono.ttf",
            "NotoSerifSC.ttf",
            "NotoSerifTC.ttf",
        ),
        "BlueArchive": ("BlueakaBeta2GBK-DemiBold.ttf", "BlueakaBeta2GBK-Bold.ttf"),
    }.items()
}


class TypstFontGroup(TypedDict):
    """单个内置主题所需的共享字体集合。"""

    theme: str
    required: list[str]
    missing: list[str]
    ready: bool


class TypstFontStatus(TypedDict):
    """WebUI 使用的受管理字体状态。"""

    directory: str
    files: list[str]
    missing: list[str]
    ready: bool
    groups: list[TypstFontGroup]


def typst_font_status(data_dir: Path) -> TypstFontStatus:
    """检查插件自己的字体目录，不扫描系统路径。

    Args:
        data_dir: 插件数据根目录。

    Returns:
        已安装的字体和仍需下载的预设文件。
    """
    directory = data_dir / "typst" / "fonts"
    files = sorted(
        p.name
        for p in directory.glob("*")
        if p.suffix.lower() in {".ttf", ".otf", ".ttc"} and p.is_file()
    )
    missing = [name for name in FONT_SOURCES if name not in files]
    return {
        "directory": str(directory),
        "files": files,
        "missing": missing,
        "ready": not missing,
        "groups": [
            {
                "theme": theme,
                "required": list(required),
                "missing": [name for name in required if name not in files],
                "ready": all(name in files for name in required),
            }
            for theme, required in THEME_FONTS.items()
        ],
    }


async def download_typst_fonts(
    data_dir: Path, cdn_base_url: str, theme: str | None = None
) -> TypstFontStatus:
    """将固定预设字体下载到插件目录，校验头部并原子替换。

    Args:
        data_dir: 插件数据根目录。
        cdn_base_url: 当前配置的 CDN 根地址。
        theme: 仅补齐该内置主题的字体；空值下载完整预设。

    Returns:
        下载后的字体状态；已存在的预设不会重复下载。

    Raises:
        ValueError: CDN 返回的内容过大或不是字体。
        aiohttp.ClientError: 下载失败，已经成功的文件仍可复用。
    """
    if theme is not None and theme not in THEME_FONTS:
        raise ValueError("未知 Typst 模板，请刷新字体列表后重试")
    required = THEME_FONTS[theme] if theme is not None else tuple(FONT_SOURCES)
    missing = [
        name for name in typst_font_status(data_dir)["missing"] if name in required
    ]
    directory = data_dir / "typst" / "fonts"
    directory.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=180), trust_env=True
    ) as session:
        for name in missing:
            target = directory / name
            temporary = directory / f".{name}.{uuid.uuid4().hex}.part"
            try:
                source = FONT_SOURCES[name]
                url = (
                    source
                    if source.startswith("https://")
                    else f"{cdn_base_url.rstrip('/')}/{source}"
                )
                async with session.get(url) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        payload.extend(chunk)
                        if len(payload) > 32 * 1024 * 1024:
                            raise ValueError("字体下载超过 32 MiB，请检查 CDN 响应")
                if len(payload) < 1024 or bytes(payload[:4]) not in (
                    b"ttcf",
                    b"OTTO",
                    b"\x00\x01\x00\x00",
                ):
                    raise ValueError("CDN 返回的内容不是有效字体")
                await asyncio.to_thread(temporary.write_bytes, payload)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    return typst_font_status(data_dir)
