"""QQ SDK 异常的跨版本防腐与安全日志摘要。"""

from __future__ import annotations

import json
import re
from collections import deque
from html import unescape
from urllib.parse import unquote

import aiohttp

_SECRET_FIELDS = (
    r"authorization|proxy[-_]?authorization|cookie|set[-_]?cookie|"
    r"(?:access|refresh|id|bot)[-_]?token|token|(?:client|app)[-_]?secret|secret|"
    r"password|passwd|api[-_]?key|file[-_]?info"
)
_ERROR_HINTS = {
    "AuthenticationFailedError": "QQ 接口鉴权失败，请检查机器人连接状态",
    "ForbiddenError": "QQ 接口拒绝访问，请检查消息及按钮权限",
    "SequenceNumberError": "QQ 接口限流或消息序号冲突",
    "ServerError": "QQ 接口返回错误",
    "NotFoundError": "QQ 接口或目标会话不存在",
    "MethodNotAllowedError": "QQ 接口不支持此发送方式",
    "ImportError": "当前 SDK 缺少原生消息能力",
    "ModuleNotFoundError": "当前 SDK 缺少原生消息能力",
    "AttributeError": "当前客户端缺少所需 SDK 接口",
    "FileNotFoundError": "本地预览图或缓存文件不存在",
    "PermissionError": "没有本地文件读写权限",
    "UnidentifiedImageError": "预览内容不是可识别的图片",
    "ValueError": "图片格式、大小或像素未通过校验",
}


def describe_preview_error(exc: Exception) -> str:
    """安全提取异常已有的错误原因，不依赖特定版本的 botpy 异常类。

    Args:
        exc: QQ 原生消息、图片准备或宿主发送阶段的异常。

    Returns:
        最多 512 字符的单行脱敏摘要。只保留已有状态码及白名单消息字段，
        不访问请求／响应对象，也不修改全局 SDK 日志；无法提取时保留错误类别。
    """
    name = type(exc).__name__
    hint = _ERROR_HINTS.get(name, "调用异常，请结合当前阶段排查")
    fields: dict[str, object] = {}
    if isinstance(exc, aiohttp.ClientResponseError):
        hint = f"HTTP {exc.status}"
        fields = {"message": exc.message}
    elif isinstance(exc, aiohttp.ClientConnectionError):
        hint = "无法连接，请检查网络或代理"
    elif isinstance(exc, TimeoutError):
        hint = "请求超时"
    else:
        # 仅在外部 SDK 边界读取可选属性；不同版本的属性或 getter 可能不存在。
        for key in ("msgs", "message", "status", "status_code", "code", "errcode"):
            try:
                value: object = getattr(exc, key, None)
            except Exception:
                continue
            fields[key] = value

    pending: deque[object] = deque([fields])
    # 文件异常可能包含本地私有路径；继续使用类别提示，不展开文件系统正文。
    if not isinstance(exc, OSError):
        try:
            pending.extend(exc.args[:3])
        except Exception:
            pass
        try:
            pending.append(str(exc))
        except Exception:
            pass
    numbers: dict[str, int] = {}
    detail = ""
    # 同时限制循环及嵌套，兼容字典、消息列表和损坏的 SDK 错误对象。
    for _ in range(16):
        if not pending:
            break
        candidate = pending.popleft()
        if isinstance(candidate, dict):
            for key, label in (
                ("status", "http_status"),
                ("status_code", "http_status"),
                ("code", "code"),
                ("errcode", "code"),
            ):
                value = dict.get(candidate, key)
                if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,10}", value):
                    value = int(value)
                if (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and -9_999_999_999 <= value <= 9_999_999_999
                    and (label == "code" or 100 <= value <= 599)
                ):
                    numbers.setdefault(label, value)
            # 不展开 headers、request、response、data 等任意 SDK 附加信息。
            for key in ("error", "error_description", "msg", "message", "msgs"):
                value = dict.get(candidate, key)
                if value is not None:
                    pending.appendleft(value)
            continue
        if isinstance(candidate, (tuple, list)):
            pending.extend(candidate[:3])
            continue
        if isinstance(candidate, bytes):
            candidate = candidate[:8192].decode("utf-8", errors="replace")
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        raw = candidate[:8192]
        if raw.lstrip().startswith(("{", "[")):
            try:
                pending.append(json.loads(raw))
            except (ValueError, RecursionError):
                if raw.lstrip().startswith("{"):
                    continue
            else:
                continue
        if detail:
            continue
        # 先解码常见转义，脱敏后再截断，避免截断留下半个鉴权值。
        raw = raw.replace(r"\/", "/").replace(r"\"", '"').replace(r"\'", "'")
        for _ in range(2):
            raw = unquote(unescape(raw))
        raw = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028-\u202e\u2066-\u2069]", "", raw
        )
        raw = re.sub(
            r"(?im)\b(?:authorization|proxy[-_]?authorization|cookie|set[-_]?cookie)"
            r"[\"']?\s*:\s*[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*",
            "[鉴权信息已隐藏]",
            raw,
        )
        raw = re.sub(
            r"(?i)\b(?:bearer|qqbot|bot)\s+[^\s,;\"'<>]+", "[鉴权信息已隐藏]", raw
        )
        raw = re.sub(
            rf"(?i)(\b(?:{_SECRET_FIELDS})\b[\"']?\s*[:=]\s*)"
            r"(?:\"[^\"]*\"|'[^']*'|[^,;\r\n}]+)",
            r"\1[已隐藏]",
            raw,
        )
        raw = re.sub(
            r"(?i)\b(?:https?|wss?|file)://[^\s<>\"']+", "[资源地址已隐藏]", raw
        )
        raw = re.sub(r"[\x00-\x1f\x7f-\x9f\u2028-\u202e\u2066-\u2069]", " ", raw)
        detail = " ".join(raw.split())
    summary = f"{name}: {hint}"
    for key, value in numbers.items():
        summary += f" {key}={value}"
    if detail:
        summary += f"; 详情={detail}"
    return summary if len(summary) <= 512 else summary[:509] + "..."
