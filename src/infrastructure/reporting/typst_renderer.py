"""与 AstrBot/custom 并列的独立 Typst 渲染入口。"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import aiohttp
from PIL import Image

from .typst_data import TypstDataPreparer
from .typst_resources import TypstAssets

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager
    from ..config.rendering_config import RenderingStrategyOptions
    from .avatar_service import AvatarService


TYPST_TEMPLATES = Path(__file__).parent / "typst_templates"
# 发布包不含开发目录的图片，所有装饰只通过配置的 CDN 获取并持久缓存。
THEME_DECORATIONS: dict[str, tuple[str, ...]] = {
    "HatsuneMiku": tuple(
        f"HatsuneMiku/retouch_{name}.png"
        for name in (
            "2026032802083201",
            "2026032810150449",
            "2026032810143720",
            "2026032810151717",
            "2026032810153327",
            "2026032810145078",
        )
    ),
    "ATRI": (
        "ATRI/file/1775130609119_1774881269400_可爱-1.webp",
        "ATRI/file/1775130585446_1774881263342_观察.webp",
    ),
    "deepseek_maid": ("deepseek_maid/basin-v3.png", "deepseek_maid/closed-eye-0.png"),
    "maria": (
        "maria/rosa_chinensis_sachiko_yumi.png",
        "maria/rose_red.png",
        "maria/rose_white.png",
        "maria/rose_yellow.png",
        "maria/rosa_gigantea_sei_shimako.png",
    ),
}


async def run_typst_worker(
    job_dir: Path, font_dir: Path, timeout_seconds: float
) -> None:
    """限时执行隔离编译，取消或超时后等待子进程退出再清理目录。

    Args:
        job_dir: 本次编译专用目录。
        font_dir: 受管理字体目录。
        timeout_seconds: 编译允许的最长秒数。

    Raises:
        TimeoutError: 编译超时且进程已终止。
        RuntimeError: 编译器返回失败。
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        str(Path(__file__).with_name("typst_worker.py")),
        str(job_dir),
        str(font_dir),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    communication = asyncio.create_task(process.communicate())
    try:
        async with asyncio.timeout(timeout_seconds):
            _, stderr = await asyncio.shield(communication)
    except BaseException:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await asyncio.shield(communication)
        raise
    if process.returncode:
        raise RuntimeError((stderr or b"").decode("utf-8", errors="replace")[-1800:])


async def render_typst_probe(
    data_dir: Path, options: RenderingStrategyOptions
) -> bytes:
    """使用同一独立编译进程测试受管理字体和 PNG 输出。

    Args:
        data_dir: 插件数据根目录。
        options: 当前未保存的 Typst 方案。

    Returns:
        固定测试图片，不读取群聊、不调用模型也不发送消息。
    """
    jobs = data_dir / "typst" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="probe-", dir=jobs) as directory:
        job_dir = Path(directory)
        payload = {"width": 480, "ppi": options.get("typst_ppi", 144)}
        (job_dir / "data.json").write_text(json.dumps(payload), encoding="utf-8")
        (job_dir / "main.typ").write_text(
            """#let d = json("data.json")
#let u = 72/d.ppi*1pt
#set page(width:480*u,height:180*u,margin:28*u,fill:rgb("f0fafa"))
#set text(font:"Noto Sans SC",size:18*u,fill:rgb("2c3e50"))
#text(weight:"bold",fill:rgb("2a9d95"))[Typst 独立排版测试]
#v(12*u)
中文、English、日本語 · 0123456789
#v(8*u)
受管理字体 → 原生 PNG
#metadata((height:180*u/1pt))<report-size>
""",
            encoding="utf-8",
        )
        await run_typst_worker(
            job_dir, data_dir / "typst" / "fonts", options.get("timeout", 30000) / 1000
        )
        return await asyncio.to_thread((job_dir / "report.png").read_bytes)


async def render_typst_report(
    result: AnalysisResultPayload,
    config: ConfigManager,
    data_dir: Path,
    avatars: AvatarService,
    profile_manifest: dict[str, dict],
    theme: str,
    options: RenderingStrategyOptions,
    avatar_getter: Callable | None = None,
    nickname_getter: Callable | None = None,
    namespace: str | None = None,
    hide_names: bool = False,
    extended_ids: bool = False,
) -> bytes:
    """准备原生数据和 CDN 素材，独立编译为现有发送接口可接受的图片。

    Args:
        result: 完整领域分析结果。
        config: 当前插件配置。
        data_dir: 插件数据根目录。
        avatars: 现有平台隔离头像服务。
        profile_manifest: 人格资源映射。
        theme: 内置主题目录名。
        options: 本轮 Typst 方案参数。
        avatar_getter: 平台头像回调。
        nickname_getter: 平台昵称回调。
        namespace: 平台缓存命名空间。
        hide_names: 是否匿名。
        extended_ids: 是否识别字母数字用户 ID。

    Returns:
        PNG 或 JPEG 字节；不生成或调用 HTML。

    Raises:
        ValueError: 主题不支持或没有安装受管理字体。
        RuntimeError: 编译失败。
        TimeoutError: 准备或编译超过本轮超时。
    """
    template = TYPST_TEMPLATES / theme / "report.typ"
    if (
        theme not in {path.name for path in TYPST_TEMPLATES.iterdir() if path.is_dir()}
        or not template.is_file()
    ):
        raise ValueError(f"Typst 暂不支持模板 {theme}，请使用内置主题")
    font_dir = data_dir / "typst" / "fonts"
    if not font_dir.is_dir() or not any(
        p.suffix.lower() in (".ttf", ".otf", ".ttc") for p in font_dir.iterdir()
    ):
        raise ValueError(
            "请先在 WebUI 下载 Typst 字体，字体保存在插件数据目录 typst/fonts"
        )
    jobs = data_dir / "typst" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    resources = options.get("resource_urls")
    cdn = resources["cdn_base_url"] if resources else config.get_t2i_cdn_base_url()
    environment = options.get("resource_environment")
    base = config.get_template_assets_base_url(environment, cdn_base_url=cdn)
    async with asyncio.timeout(options.get("timeout", 30000) / 1000):
        with TemporaryDirectory(prefix="report-", dir=jobs) as directory:
            job_dir = Path(directory)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15), trust_env=True
            ) as session:
                assets = TypstAssets(data_dir, job_dir, session)
                preparer = TypstDataPreparer(
                    config,
                    avatars,
                    assets,
                    result,
                    hide_names,
                    avatar_getter,
                    nickname_getter,
                    namespace,
                    extended_ids,
                )
                data = await preparer.prepare(profile_manifest, cdn)
                data["decorations"] = await asyncio.gather(
                    *(
                        assets.localize(f"{base}/{name}")
                        for name in THEME_DECORATIONS.get(theme, ())
                    )
                )
            payload = {
                **data,
                "width": options.get("typst_width", 940),
                "ppi": options.get("typst_ppi", 144),
            }
            (job_dir / "data.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            shutil.copyfile(template, job_dir / "main.typ")
            shutil.copyfile(TYPST_TEMPLATES / "common.typ", job_dir / "common.typ")
            for resource in template.parent.iterdir():
                if resource.suffix in (".svg", ".typ") and resource != template:
                    shutil.copyfile(resource, job_dir / resource.name)
            await run_typst_worker(
                job_dir, font_dir, options.get("timeout", 30000) / 1000
            )
            image = await asyncio.to_thread((job_dir / "report.png").read_bytes)
            if options.get("type", "png") == "jpeg":
                image = await asyncio.to_thread(
                    _encode_jpeg, image, options.get("quality", 90)
                )
            return image


def _encode_jpeg(payload: bytes, quality: int) -> bytes:
    """在工作线程中将编译结果转为 JPEG，避免压缩阻塞事件循环。

    Args:
        payload: 已校验的 PNG。
        quality: JPEG 质量。

    Returns:
        JPEG 文件字节。
    """
    with Image.open(BytesIO(payload)) as image:
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=quality)
        return output.getvalue()
