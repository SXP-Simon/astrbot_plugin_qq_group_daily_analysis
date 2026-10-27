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


@dataclass(frozen=True)
class CdnProbeResource:
    """固定检测文件及其在模板中的用途。"""

    id: str
    label: str
    description: str
    kind: Literal["gh", "npm"]
    path: str


# 路径取自当前模板及预览图；测试会核对文件存在且仍被引用。
PROBE_RESOURCES = (
    CdnProbeResource(
        "maria-png",
        "装饰图片",
        "Maria 模板的蔷薇图片",
        "gh",
        "maria/rose_red.png",
    ),
    CdnProbeResource(
        "miku-png",
        "较大的图片",
        "初音未来模板的装饰图片",
        "gh",
        "HatsuneMiku/retouch_2026032810150449.png",
    ),
    CdnProbeResource(
        "maid-layer",
        "多层目录中的图片",
        "鲸鱼女仆模板的眼睛图层",
        "gh",
        "deepseek_maid/layers/eye-0.png",
    ),
    CdnProbeResource(
        "atri-background",
        "背景图片",
        "ATRI 模板的背景图片",
        "gh",
        "ATRI/file/1775130588385_1774881257527_bg1.webp",
    ),
    CdnProbeResource(
        "atri-webp",
        "中文文件名图片",
        "ATRI 模板里的「疑惑」表情图片",
        "gh",
        "ATRI/file/1775130581843_1774881262835_疑惑.webp",
    ),
    CdnProbeResource(
        "atri-gif",
        "中文文件名动图",
        "ATRI 模板话题卡片中的「疑惑」动图",
        "gh",
        "ATRI/file/1775132805081_1774881262835_疑惑.gif",
    ),
    CdnProbeResource(
        "atri-font",
        "报告字体",
        "ATRI 模板的霞鹜文楷字体",
        "gh",
        "ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2",
    ),
    CdnProbeResource(
        "template-preview",
        "模板预览图",
        "模板选择页面中的 Maria 预览图",
        "gh",
        "maria-demo.webp",
    ),
    CdnProbeResource(
        "npm-css",
        "npm 兼容性",
        "额外检查 normalize.css；当前内置模板没有使用它",
        "npm",
        "normalize.css@8.0.1/normalize.css",
    ),
)


async def _probe_resource(
    session: aiohttp.ClientSession, resource: CdnProbeResource, url: str
) -> TemplateCdnCheckDTO:
    """使用 HEAD 检查资源地址，只接收响应头，不读取文件内容。

    Args:
        session: 带有超时限制的 HTTP 会话。
        resource: 检测文件的固定定义。
        url: 使用待测 CDN 拼接的文件地址。

    Returns:
        文件用途、响应耗时、HTTP 状态及检测未通过的原因。
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
        "error": None,
    }
    try:
        async with session.head(url, allow_redirects=True, max_redirects=3) as response:
            result["status_code"] = response.status
            result["success"] = 200 <= response.status < 300
            if response.status in (405, 501):
                result["error"] = (
                    "这个站点不支持 HEAD 检测，暂时无法确认；可以打开下面的链接查看。"
                )
            elif not result["success"]:
                result["error"] = f"本次请求返回 HTTP {response.status}，可以稍后重试。"
    except (TimeoutError, asyncio.TimeoutError):
        result["error"] = f"等了 {PROBE_TIMEOUT_SECONDS} 秒仍未收到响应，可以稍后重试。"
    except aiohttp.ClientConnectorCertificateError:
        result["error"] = "这个地址的安全证书验证失败，请检查地址或换一个 CDN。"
    except aiohttp.TooManyRedirects:
        result["error"] = "这个地址反复跳转，本次检测未能完成。"
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
        # 分批限制并发；超时从实际发起 HEAD 请求时计，不包含排队时间。
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
