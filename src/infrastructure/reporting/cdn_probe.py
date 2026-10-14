"""用模板实际引用的文件检测 CDN，并单独检查 npm 路径兼容性。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import aiohttp

from ...shared.constants import (
    DEFAULT_CDN_HOST,
    GITHUB_REPO_BRANCH,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)
from ...utils.cdn_utils import normalize_cdn_base_url

if TYPE_CHECKING:
    from ...application.dto.webui_dto import TemplateCdnCheckDTO, TemplateCdnProbeDTO

PROBE_TIMEOUT_SECONDS = 15
MAX_PROBE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class CdnProbeResource:
    """固定检测文件及其在模板中的用途。"""

    id: str
    label: str
    description: str
    kind: Literal["gh", "npm"]
    path: str
    format: Literal["png", "jpeg", "webp", "gif", "woff2", "css"]


# 路径取自当前模板及预览图；测试会核对文件存在且仍被引用。
PROBE_RESOURCES = (
    CdnProbeResource(
        "maria-png",
        "装饰图片",
        "Maria 模板的蔷薇图片",
        "gh",
        "maria/rose_red.png",
        "png",
    ),
    CdnProbeResource(
        "miku-png",
        "较大的图片",
        "初音未来模板的装饰图片，约 1 MB",
        "gh",
        "HatsuneMiku/retouch_2026032810150449.png",
        "png",
    ),
    CdnProbeResource(
        "maid-layer",
        "多层目录中的图片",
        "鲸鱼女仆模板的眼睛图层",
        "gh",
        "deepseek_maid/layers/eye-0.png",
        "png",
    ),
    CdnProbeResource(
        "atri-background",
        "背景图片",
        "ATRI 模板的背景图片",
        "gh",
        "ATRI/file/1775130588385_1774881257527_bg1.webp",
        "webp",
    ),
    CdnProbeResource(
        "atri-webp",
        "中文文件名图片",
        "ATRI 模板里的「疑惑」表情图片",
        "gh",
        "ATRI/file/1775130581843_1774881262835_疑惑.webp",
        "webp",
    ),
    CdnProbeResource(
        "atri-gif",
        "中文文件名动图",
        "ATRI 模板话题卡片中的「疑惑」动图",
        "gh",
        "ATRI/file/1775132805081_1774881262835_疑惑.gif",
        "gif",
    ),
    CdnProbeResource(
        "atri-font",
        "报告字体",
        "ATRI 模板的霞鹜文楷字体，约 8 MB，加载可能稍慢",
        "gh",
        "ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2",
        "woff2",
    ),
    CdnProbeResource(
        "template-preview",
        "模板预览图",
        "模板选择页面中的 Maria 预览图",
        "gh",
        "maria-demo.jpg",
        "jpeg",
    ),
    CdnProbeResource(
        "npm-css",
        "npm 兼容性",
        "额外检查 normalize.css；当前内置模板没有使用它",
        "npm",
        "normalize.css@8.0.1/normalize.css",
        "css",
    ),
)


async def _probe_resource(
    session: aiohttp.ClientSession, resource: CdnProbeResource, url: str
) -> TemplateCdnCheckDTO:
    """完整下载检测文件，检查类型及文件完整性标记。

    Args:
        session: 带有超时限制的 HTTP 会话。
        resource: 检测文件的固定定义。
        url: 使用待测 CDN 拼接的文件地址。

    Returns:
        文件用途、下载耗时、已接收字节数及失败原因。
    """
    started = time.perf_counter()
    result: TemplateCdnCheckDTO = {
        "id": resource.id,
        "label": resource.label,
        "description": resource.description,
        "kind": resource.kind,
        "url": url,
        "success": False,
        "status_code": None,
        "elapsed_ms": 0,
        "bytes_received": 0,
        "error": None,
    }
    try:
        async with session.get(url, max_redirects=3) as response:
            result["status_code"] = response.status
            if response.status != 200:
                result["error"] = (
                    "没有找到这个文件（404），这个 CDN 可能还没有同步。"
                    if response.status == 404
                    else f"下载失败，服务器返回了 HTTP {response.status}。"
                )
            else:
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    result["bytes_received"] += len(chunk)
                    if result["bytes_received"] > MAX_PROBE_BYTES:
                        raise ValueError("收到的文件超过 12 MB，已停止下载。")
                    body.extend(chunk)
                mime = response.content_type
                if resource.format == "png":
                    valid = (
                        mime == "image/png"
                        and body.startswith(b"\x89PNG\r\n\x1a\n")
                        and body.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")
                    )
                elif resource.format == "jpeg":
                    valid = (
                        mime == "image/jpeg"
                        and body.startswith(b"\xff\xd8\xff")
                        and body.endswith(b"\xff\xd9")
                    )
                elif resource.format == "webp":
                    valid = (
                        mime == "image/webp"
                        and body.startswith(b"RIFF")
                        and body[8:12] == bytearray(b"WEBP")
                        and int.from_bytes(body[4:8], "little") + 8 == len(body)
                    )
                elif resource.format == "gif":
                    valid = (
                        mime == "image/gif"
                        and body.startswith((b"GIF87a", b"GIF89a"))
                        and body.endswith(b";")
                    )
                elif resource.format == "woff2":
                    valid = (
                        mime
                        in (
                            "font/woff2",
                            "application/font-woff2",
                            "application/octet-stream",
                        )
                        and len(body) >= 48
                        and body.startswith(b"wOF2")
                        and int.from_bytes(body[8:12], "big") == len(body)
                    )
                else:
                    valid = (
                        mime == "text/css"
                        and body.lstrip().startswith(b"/*! normalize.css v8.0.1")
                        and b"html {" in body
                    )
                result["success"] = valid
                if not valid:
                    result["error"] = (
                        "收到的内容不是预期的文件，可能是验证页面、错误页面，或文件没有下载完整。"
                    )
    except (TimeoutError, asyncio.TimeoutError):
        result["error"] = (
            f"等了 {PROBE_TIMEOUT_SECONDS} 秒仍未下载完成，可以稍后重试或换一个 CDN。"
        )
    except aiohttp.ClientConnectorCertificateError:
        result["error"] = "这个地址的安全证书验证失败，请检查地址或换一个 CDN。"
    except aiohttp.TooManyRedirects:
        result["error"] = "这个地址反复跳转，无法下载文件。"
    except aiohttp.ClientError:
        result["error"] = (
            "连接中断或无法连接，请检查服务器网络，也可以换一个 CDN 再试。"
        )
    except ValueError as exc:
        result["error"] = str(exc)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


async def probe_template_cdn(base_url: str) -> TemplateCdnProbeDTO:
    """检测当前内置模板的路径类型及 npm 兼容性，不保存配置。

    Args:
        base_url: 待检测的 CDN 根地址，留空使用默认地址。

    Returns:
        规范化地址与各文件检测结果；usable 表示全部检测通过。

    Raises:
        ValueError: 非空地址格式无效。
    """
    base_url = normalize_cdn_base_url(
        base_url if base_url.strip() else DEFAULT_CDN_HOST
    )
    github_base = f"{base_url}/gh/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}@{GITHUB_REPO_BRANCH}/assets"
    checks: list[TemplateCdnCheckDTO] = []
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(
            total=PROBE_TIMEOUT_SECONDS, ceil_threshold=PROBE_TIMEOUT_SECONDS + 1
        ),
        trust_env=True,
    ) as session:
        # 分批限制并发；每个文件的超时从实际开始下载时计，不包含排队时间。
        for offset in range(0, len(PROBE_RESOURCES), 4):
            checks.extend(
                await asyncio.gather(
                    *(
                        _probe_resource(
                            session,
                            resource,
                            f"{github_base if resource.kind == 'gh' else base_url + '/npm'}/{resource.path}",
                        )
                        for resource in PROBE_RESOURCES[offset : offset + 4]
                    )
                )
            )
    return {
        "base_url": base_url,
        "usable": all(c["success"] for c in checks),
        "checks": checks,
    }
