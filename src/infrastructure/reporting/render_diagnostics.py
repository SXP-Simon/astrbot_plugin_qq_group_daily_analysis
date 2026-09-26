"""渲染诊断与输出路径工具模块

提供 T2I 渲染错误排查诊断、视口策略解析及安全文件路径生成功能。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import ulid

from ...shared.trace_context import TraceContext
from ...utils.template_utils import render_template


def diagnose_non_image_payload(data: bytes) -> str:
    """从非图片响应（文本/HTML/JSON/错误流/未知二进制）中提取可读的诊断排查指引。

    Args:
        data: 渲染服务返回的原始响应前置或全量字节流。

    Returns:
        人类可读的错误描述与排查指引文本。
    """
    if not data:
        return "返回数据为空 (0 字节)"

    # 尝试将前置数据解码为可读文本
    text = ""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            text = data.decode(encoding).strip()
            break
        except Exception:
            continue

    # 1. 成功解码为可读文本
    if text:
        # 1.1 JSON 格式错误处理
        if (text.startswith("{") and text.endswith("}")) or (
            text.startswith("[") and text.endswith("]")
        ):
            try:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    detail = (
                        payload.get("detail")
                        or payload.get("error")
                        or payload.get("message")
                        or str(payload)
                    )
                    if isinstance(detail, str):
                        if "Timeout" in detail or "timeout" in detail:
                            return (
                                f"T2I 渲染超时 (JSON 错误: {detail}) - "
                                f"通常因外链 CDN 资源/大字体包下载过慢引起，建议在配置中切换访问环境为 Overseas 或调大渲染超时 (ms)"
                            )
                        return f"T2I 接口返回 JSON 错误: {detail}"
            except Exception:
                pass

        # 1.2 HTML 页面错误处理
        text_lower = text.lower()
        if "<html" in text_lower or "<!doctype html" in text_lower:
            title_match = re.search(
                r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL
            )
            h1_match = re.search(r"<h1>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
            title = (
                title_match.group(1).strip()
                if title_match
                else (h1_match.group(1).strip() if h1_match else "")
            )
            if title:
                return f"HTML 错误页:「{title}」(T2I 渲染端点返回了网页响应而非图片)"
            clean_snippet = re.sub(r"\s+", " ", text[:120]).strip()
            return f"HTML 响应内容: {clean_snippet}..."

        # 1.3 常见纯文本错误模式识别
        if "Internal Server Error" in text:
            return (
                f"HTTP 500 (Internal Server Error) - T2I 服务内部发生异常。"
                f"常见根因: Playwright 页面超时（外部大字体包/图片 CDN 握手丢包）、"
                f"数据卷未挂载共享（找不到 /app/data/*.html）或容器 Chromium 沙箱/内存不足崩溃。"
                f"原始返回:「{text[:100].strip()}」"
            )
        if "Bad Gateway" in text:
            return "HTTP 502 (Bad Gateway) - T2I 反向代理网关未收到上游服务响应"
        if "Gateway Timeout" in text:
            return "HTTP 504 (Gateway Timeout) - T2I 服务网关请求超时"
        if "Timeout" in text or "TimeoutError" in text:
            return (
                f"T2I 页面加载超时 (Playwright Timeout): {text[:150].strip()} - "
                f"建议检查外链 CDN 连通性、配置 IPv4 优先或放宽超时时间"
            )

        clean_text = re.sub(r"\s+", " ", text[:150]).strip()
        return f"纯文本响应 (非图片):「{clean_text}」"

    # 2. 无法解码为文本的未知二进制数据
    head_hex = data[:16].hex()
    return (
        f"未知二进制数据 (大小: {len(data)} 字节, 头部 Hex: {head_hex}) - "
        f"如持续出现，建议检查 T2I 容器日志 (podman/docker logs) 或向社区提交反馈并附带该 Hex 头部"
    )


def resolve_t2i_viewport_options(
    html_content: str, image_options: dict
) -> tuple[dict, str]:
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
) -> Path:
    """根据模板安全构建报告文件输出路径，防止目录穿越。

    Args:
        output_dir: 基础输出目录。
        filename_format: 文件名格式模板字符串。
        group_id: 群组 ID。
        date: 当前日期字符串。

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
        "trace_id": str(TraceContext.get() or ""),
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
