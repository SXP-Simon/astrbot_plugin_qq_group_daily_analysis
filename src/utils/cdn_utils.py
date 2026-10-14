"""模板 CDN 根地址的共享格式校验。"""

import re
from urllib.parse import urlsplit

_CDN_ROOT = re.compile(
    r"https?://((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
    r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.?|\[[a-f0-9:]+\])"
    r"(?::([0-9]{1,5}))?",
    re.IGNORECASE | re.ASCII,
)


def normalize_cdn_base_url(value: str) -> str:
    """规范化 CDN 根地址，拒绝凭据、资源路径和查询参数。

    Args:
        value: 用户输入的 HTTP(S) CDN 根地址。

    Returns:
        去掉首尾空白及末尾斜杠的根地址。

    Raises:
        ValueError: 输入不是有效的 HTTP(S) 根地址。
    """
    base_url = value.strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        if (
            len(value) <= 2048
            and _CDN_ROOT.fullmatch(base_url)
            and parsed.scheme in ("http", "https")
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and not parsed.path
            and (parsed.port is None or parsed.port > 0)
            and not any(char.isspace() or char in "?#\\" for char in base_url)
        ):
            return base_url
    except ValueError:
        pass
    raise ValueError(
        "请填完整的网站地址，例如 https://fastly.jsdelivr.net/，不要带账号密码、文件路径或 ?、# 后面的内容"
    )
