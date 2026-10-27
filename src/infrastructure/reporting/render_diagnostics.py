"""渲染诊断与输出路径工具模块

提供 T2I 渲染错误排查诊断、视口策略解析及安全文件路径生成功能。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Required, TypedDict

import ulid

from ...shared.trace_context import TraceContext
from ...utils.template_utils import render_template

if TYPE_CHECKING:
    from ..config.rendering_config import (
        FontMode,
        RenderingResourceConfig,
        ScreenshotOptions,
    )
    from .html_renderer import RenderServiceInfo


class RenderAttemptRecord(TypedDict, total=False):
    """单轮渲染的只读观测记录，不包含服务凭据或报告正文。"""

    attempt: int
    strategy_name: str
    priority: int | None
    service_type: Literal["astrbot", "custom"]
    font_mode: FontMode
    resource_environment: str
    resource_urls: RenderingResourceConfig | None
    render_timeout_ms: int | None
    request_timeout_ms: int | None
    started_at: float
    duration_ms: float
    status: Literal["running", "success", "failed", "cancelled"]
    type: str
    viewport: str
    error: str
    return_type: Required[str]
    render_service: RenderServiceInfo
    returned_bytes: int
    file_exists: bool


def summarize_render_error(text: str) -> str:
    """整理渲染错误摘要，隐藏常见凭据并限制输出长度。

    Args:
        text: 响应片段或异常消息。

    Returns:
        适合日志和任务详情展示的单行摘要。
    """
    text = re.sub(r"https?://[^\s<>\"']+", "[地址已隐藏]", text, flags=re.I)
    text = re.sub(r"\b(Bearer|Basic)\s+[^\s,;\"']+", r"\1 [已隐藏]", text, flags=re.I)
    text = re.sub(
        r"""(?ix)(["']?(?:authorization|cookie|set-cookie|token|access_token|
        refresh_token|api[_-]?key|password|secret)["']?\s*[:=]\s*)
        (?:"[^"]*"|'[^']*'|[^\s,;}]+)""",
        r"\1[已隐藏]",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300] + ("…" if len(text) > 300 else "")


def diagnose_non_image_payload(data: bytes) -> str:
    """从非图片响应中提取有限的错误信息，不推断 HTTP 状态或故障原因。

    Args:
        data: 服务响应的前置片段。

    Returns:
        错误摘要，以及与已知信息分开标注的排查建议。
    """
    if not data:
        return "渲染服务返回了空内容。"

    text = ""
    for encoding in ("utf-8", "gbk"):
        try:
            text = data.decode(encoding).strip()
            break
        except UnicodeDecodeError:
            continue
    if not text or any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        return "渲染服务返回了无法识别的数据，未得到可用图片。"

    response_kind = "文字"
    try:
        payload = json.loads(text)
    except ValueError:
        payload = None
    if isinstance(payload, (dict, list)):
        response_kind = "JSON"
        if isinstance(payload, dict):
            detail = (
                payload.get("detail") or payload.get("error") or payload.get("message")
            )
            text = str(detail) if detail else json.dumps(payload, ensure_ascii=False)
    elif "<html" in text.lower() or "<!doctype html" in text.lower():
        response_kind = "网页"
        heading = re.search(
            r"<(?:title|h1)[^>]*>(.*?)</(?:title|h1)>", text, re.I | re.S
        )
        # 不输出整个错误页，避免混入页面正文或脚本。
        text = re.sub(r"<[^>]+>", "", heading.group(1)) if heading else ""

    summary = summarize_render_error(text)
    if summary:
        diagnosis = f"渲染服务返回了{response_kind}内容，未得到图片：{summary}"
        # 只把响应中的线索作为排查方向，不据此认定状态码或根因。
        hint = ""
        normalized = summary.casefold()
        if "bad gateway" in normalized or "gateway timeout" in normalized:
            hint = (
                "请查看同一时间的反向代理和 T2I 服务日志，"
                "确认渲染服务是否正常运行，以及代理能否连接到它。"
            )
        elif "internal server error" in normalized:
            hint = (
                "请先查看同一时间的 T2I 服务日志。"
                "如果日志提到浏览器退出、内存不足或文件不存在，"
                "再检查浏览器运行情况、可用内存或文件挂载。"
            )
        elif (
            "timeout" in normalized or "timed out" in normalized or "超时" in normalized
        ):
            hint = (
                "请先查看同一时间的 T2I 服务日志。"
                "如果日志显示页面资源加载超时，再检查模板图片、字体等 CDN 资源"
                "在渲染服务所在环境中能否访问；确认资源可达后，再考虑调整渲染超时时间。"
            )
        if hint:
            diagnosis += f"\n排查建议：{hint}"
        return diagnosis
    return f"渲染服务返回了{response_kind}内容，未得到图片。"


def resolve_t2i_viewport_options(
    html_content: str, image_options: ScreenshotOptions
) -> tuple[ScreenshotOptions, str]:
    """优先使用模板 meta 声明的视口，缺失维度使用插件配置的兜底值。

    Args:
        html_content: 已渲染完成的报告 HTML。
        image_options: 当前轮次的渲染参数字典。

    Returns:
        包含实际传给渲染引擎的选项字典及视口说明描述。
    """
    resolved_options = image_options.copy()
    head_snippet = html_content[:4096]
    descriptions = []
    for dimension, option_key in (
        ("width", "viewport_width"),
        ("height", "viewport_height"),
    ):
        pattern = (
            r'<meta\s+[^>]*name=["\']viewport["\'][^>]*'
            rf'content=["\'][^"\']*{dimension}\s*=\s*(\d+)[^"\']*["\'][^>]*>'
        )
        match = re.search(pattern, head_snippet, re.IGNORECASE)
        if match:
            resolved_options.pop(option_key, None)
            descriptions.append(f"模板{dimension}={match.group(1)}")
        else:
            descriptions.append(f"兜底{dimension}={resolved_options.get(option_key)}")
    return resolved_options, "，".join(descriptions)


def sanitize_path_component(name: str) -> str:
    """消毒单个路径/文件名片段，禁止路径穿越和非法字符。

    Args:
        name: 原始路径组件名称。

    Returns:
        清理后的合法安全组件名称。

    Raises:
        ValueError: 当路径组件为空、包含相对路径控制符或消毒后为空时抛出。
    """
    if not name or name in {".", ".."}:
        raise ValueError(f"无效的路径片段: {name!r}")

    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip()
    if not name:
        raise ValueError("路径片段经过消毒后为空")

    return name


def build_safe_report_path(
    output_dir: Path,
    filename_format: str,
    group_id: str,
    date: str,
    trace_id: str | None = None,
) -> Path:
    """根据模板安全构建报告文件输出路径，防止目录穿越。

    Args:
        output_dir: 基础输出目录。
        filename_format: 文件名格式模板字符串。
        group_id: 群组 ID。
        date: 当前日期字符串。
        trace_id: 显式指定的链路追踪 ID，用于渲染 ${trace_id} 变量；未提供时回退到当前 TraceContext。

    Returns:
        生成的安全输出 Path 对象。

    Raises:
        ValueError: 当文件名模板渲染异常、为绝对路径或存在路径穿越时抛出。
    """
    generated_ulid = str(ulid.new())
    safe_context = {
        "group_id": group_id,
        "date": date,
        "ulid": generated_ulid,
        "trace_id": str(trace_id or TraceContext.get() or ""),
    }

    try:
        formatted = render_template(filename_format, strict=True, **safe_context)
    except Exception as e:
        raise ValueError(f"文件名模板渲染失败: {e}") from e

    if os.path.isabs(formatted):
        raise ValueError("文件名格式不得为绝对路径")

    relative_path = Path(formatted)
    sanitized_parts = []
    for part in relative_path.parts:
        if part in {".", ".."}:
            raise ValueError("路径中不得包含 '.' 或 '..'。")
        sanitized_parts.append(sanitize_path_component(part))

    safe_relative = Path(*sanitized_parts)
    output_dir_resolved = output_dir.resolve(strict=False)
    target_path = (output_dir_resolved / safe_relative).resolve(strict=False)

    try:
        target_path.relative_to(output_dir_resolved)
    except ValueError as e:
        raise ValueError("文件路径不在输出目录之内，可能包含路径穿越") from e

    if target_path.exists():
        suffix = target_path.suffix
        stem = target_path.stem
        target_path = target_path.with_name(f"{stem}_{generated_ulid}{suffix}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path
