"""Typst 字体预设的状态查询与受管理目录下载。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

import aiohttp

# 字体始终写入插件 data 目录；来源是固定上游，不接受任意下载 URL 或目标路径。
FONT_SOURCES = {
    "NotoSansSC.ttf": "gh/google/fonts@main/ofl/notosanssc/NotoSansSC[wght].ttf",
    "NotoSansTC.ttf": "gh/google/fonts@main/ofl/notosanstc/NotoSansTC[wght].ttf",
    "NotoSansJP.ttf": "gh/google/fonts@main/ofl/notosansjp/NotoSansJP[wght].ttf",
    "NotoSansSymbols2.ttf": "gh/google/fonts@main/ofl/notosanssymbols2/NotoSansSymbols2-Regular.ttf",
    "NotoColorEmoji.ttf": "gh/googlefonts/noto-emoji@main/2D/fonts/Noto-COLRv1.ttf",
    # 与 cjkFonts 官方 1.11 包逐字节一致；完整 TTF 约 30 MiB，超过常见 CDN 文件上限。
    "cjkFonts_allseto_v1.11.ttf": "https://raw.githubusercontent.com/moeru-ai/airi/1eb62e912fe7936387804aa920ff98c9f1137d80/packages/font-cjkfonts-allseto/src/files/cjkFonts_allseto_v1.11.ttf",
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
        "HatsuneMiku": (
            "Outfit.ttf",
            "ShareTechMono.ttf",
            "Inter.ttf",
            "cjkFonts_allseto_v1.11.ttf",
        ),
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
        # 旧 Blueaka 文件含方正版权声明且缺少明确许可，不再预设下载或主动使用。
        "BlueArchive": (),
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


class FontDownloadProgress(TypedDict):
    """一个字体的实际网络来源、字节数和执行阶段。"""

    name: str
    url: str
    received: int
    total: int | None
    phase: Literal["connecting", "downloading", "validating"]


def typst_font_status(data_dir: Path) -> TypstFontStatus:
    """检查插件自己的字体目录，不扫描系统路径。

    Args:
        data_dir: 插件数据根目录。

    Returns:
        已安装字体、全局缺失文件和各内置主题的字体依赖状态。
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
    data_dir: Path,
    cdn_base_url: str,
    theme: str | None = None,
    *,
    name: str | None = None,
    source: Literal["cdn", "github"] = "cdn",
    on_progress: Callable[[FontDownloadProgress], None] | None = None,
) -> TypstFontStatus:
    """将固定预设字体下载到插件目录，校验头部并原子替换。

    Args:
        data_dir: 插件数据根目录。
        cdn_base_url: 当前配置的 CDN 根地址。
        theme: 仅补齐该内置主题的字体；空值下载完整预设。
        name: 可选的单个预设文件，用于逐文件展示真实下载进度。
        source: CDN 优先或所有字体均使用 GitHub Raw，字体版本保持不变。
        on_progress: 接收当前文件的来源、阶段和字节进度。

    Returns:
        下载后的字体状态；已存在的预设不会重复下载。

    Raises:
        ValueError: 模板或来源未知、网络失败、响应过大或不是字体。
        OSError: 字体目录无法写入，已经成功的文件仍可复用。
    """
    if theme is not None and theme not in THEME_FONTS:
        raise ValueError("未知 Typst 模板，请刷新字体列表后重试")
    if source not in ("cdn", "github"):
        raise ValueError("未知字体下载来源")
    required = THEME_FONTS[theme] if theme is not None else tuple(FONT_SOURCES)
    if name is not None:
        if name not in required:
            raise ValueError("未知字体或该字体不属于所选模板")
        required = (name,)
    missing = [
        file for file in typst_font_status(data_dir)["missing"] if file in required
    ]
    directory = data_dir / "typst" / "fonts"
    directory.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=180, connect=10, sock_read=20),
        trust_env=True,
    ) as session:
        for name in missing:
            location = FONT_SOURCES[name]
            if source == "github" and location.startswith("gh/"):
                repository, path = location[3:].split("@", 1)
                location = f"https://raw.githubusercontent.com/{repository}/{path}"
            url = (
                location
                if location.startswith("https://")
                else f"{cdn_base_url.rstrip('/')}/{location}"
            )
            try:
                await _download_font(session, url, directory / name, on_progress)
            except aiohttp.ClientResponseError as exc:
                raise ValueError(
                    f"{name}：来源返回 HTTP {exc.status}（{url}）；"
                    "403/429 可能是访问限制，404 表示上游文件不存在，请切换来源或上传同名字体"
                ) from exc
            except TimeoutError as exc:
                raise ValueError(
                    f"{name}：下载超时（连接上限 10 秒、连续无数据上限 20 秒、单文件总上限 180 秒）；"
                    f"请检查插件服务器到 {url} 的网络或代理"
                ) from exc
            except aiohttp.ClientError as exc:
                raise ValueError(
                    f"{name}：连接或传输失败（{type(exc).__name__}: {exc}）；"
                    f"来源 {url}，请检查插件服务器网络或代理，也可上传同名字体"
                ) from exc
    return typst_font_status(data_dir)


async def _download_font(
    session: aiohttp.ClientSession,
    url: str,
    target: Path,
    on_progress: Callable[[FontDownloadProgress], None] | None = None,
) -> None:
    """校验并原子保存一个预设字体，失败时清理临时文件。

    Args:
        session: 批次共用的下载会话。
        url: 由固定字体清单与已选 CDN 解析的来源。
        target: 插件受管理目录中的固定目标文件。
        on_progress: 接收连接、读取和校验阶段的真实进度。

    Raises:
        ValueError: 响应过大或不是字体。
        aiohttp.ClientError: 来源下载失败。
        OSError: 临时文件无法写入或替换。
    """
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    progress: FontDownloadProgress = {
        "name": target.name,
        "url": url,
        "received": 0,
        "total": None,
        "phase": "connecting",
    }
    if on_progress:
        on_progress(progress.copy())
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            progress.update(total=response.content_length, phase="downloading")
            if response.content_length and response.content_length > 32 * 1024 * 1024:
                raise ValueError("字体响应超过 32 MiB，请检查下载来源")
            if on_progress:
                on_progress(progress.copy())
            size = 0
            header = bytearray()
            with temporary.open("wb") as output:
                async for chunk in response.content.iter_chunked(65536):
                    size += len(chunk)
                    if size > 32 * 1024 * 1024:
                        raise ValueError("字体下载超过 32 MiB，请检查 CDN 响应")
                    if len(header) < 4:
                        header.extend(chunk[: 4 - len(header)])
                    output.write(chunk)
                    progress["received"] = size
                    if on_progress:
                        on_progress(progress.copy())
        progress["phase"] = "validating"
        if on_progress:
            on_progress(progress.copy())
        if size < 1024 or bytes(header) not in (b"ttcf", b"OTTO", b"\x00\x01\x00\x00"):
            raise ValueError(f"{target.name}：下载来源返回的内容不是有效字体（{url}）")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
