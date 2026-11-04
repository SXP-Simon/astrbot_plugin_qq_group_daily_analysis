"""图片报告的本地持久化边界，先识别编码来源再访问文件系统。"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path


def save_report_image(source: str, destination: Path) -> Path:
    """保存图片副本并按真实 PNG/JPEG 签名确定扩展名。

    Args:
        source: 本地文件、base64:// 编码或带 Base64 的图片 data URI。
        destination: 调用方生成的目标路径，父目录须已存在。

    Returns:
        实际已写入的文件路径。

    Raises:
        ValueError: 图片编码无效、内容为空或来源类型不受支持。
        OSError: 本地源文件不存在、不可读或目标文件写入失败。
    """
    data: bytes | None = None
    local: Path | None = None
    if source.startswith(("base64://", "data:image/")):
        if source.startswith("base64://"):
            encoded = source[len("base64://") :]
        else:
            header, separator, encoded = source.partition(",")
            if not separator or not header.endswith(";base64"):
                raise ValueError("报告图片须使用 Base64 编码的图片 data URI")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError) as error:
            raise ValueError("报告图片 Base64 编码无效") from error
        if not data:
            raise ValueError("报告图片内容为空")
        signature = data[:12]
    else:
        if "://" in source:
            raise ValueError("报告图片来源须为本地文件或 Base64 图片")
        local = Path(source)
        with local.open("rb") as stream:
            signature = stream.read(12)
        if not signature:
            raise ValueError("报告图片内容为空")

    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        destination = destination.with_suffix(".png")
    elif signature.startswith(b"\xff\xd8\xff"):
        destination = destination.with_suffix(".jpg")
    if data is not None:
        destination.write_bytes(data)
    elif local is not None and local.resolve() != destination.resolve():
        shutil.copy2(local, destination)
    return destination
