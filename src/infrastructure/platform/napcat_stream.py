"""通过 NapCat Stream API 上传大文件。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import math
import uuid
from pathlib import Path
from typing import Any

from ...utils.logger import logger


def _calculate_sha256(file_path: Path) -> str:
    """计算文件校验和，避免将完整文件保留在内存中。"""
    hasher = hashlib.sha256()
    with file_path.open("rb") as file:
        while chunk := file.read(64 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


async def upload_file_stream(bot: Any, file_path: str | Path) -> str | None:
    """通过当前 OneBot 连接上传本地文件。

    Args:
        bot: 提供 ``call_action`` 的 OneBot 客户端。
        file_path: 待上传且已存在的本地文件。

    Returns:
        NapCat 返回的临时文件路径；Stream API 不可用或上传失败时返回 ``None``。
    """
    if not hasattr(bot, "call_action"):
        return None

    path = Path(file_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return None

    chunk_size = 64 * 1024
    file_size = path.stat().st_size
    total_chunks = math.ceil(file_size / chunk_size)
    stream_id = str(uuid.uuid4())

    try:
        expected_sha256 = await asyncio.to_thread(_calculate_sha256, path)
        if path.stat().st_size != file_size:
            raise RuntimeError("上传前文件大小发生变化")

        with path.open("rb") as file:
            for chunk_index in range(total_chunks):
                chunk = file.read(chunk_size)
                if not chunk:
                    raise RuntimeError("文件在所有分块上传完成前提前结束")
                response = await bot.call_action(
                    "upload_file_stream",
                    stream_id=stream_id,
                    chunk_data=base64.b64encode(chunk).decode("ascii"),
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    file_size=file_size,
                    expected_sha256=expected_sha256,
                    filename=path.name,
                    file_retention=30_000,
                )
                if isinstance(response, dict) and (
                    response.get("status") == "failed"
                    or response.get("retcode") not in (None, 0)
                ):
                    raise RuntimeError(f"NapCat 拒绝接收分块: {response}")

        response = await bot.call_action(
            "upload_file_stream", stream_id=stream_id, is_complete=True
        )
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        payload = data if isinstance(data, dict) else response
        for key in ("file_path", "file", "path"):
            uploaded_path = payload.get(key)
            if isinstance(uploaded_path, str) and uploaded_path.strip():
                return uploaded_path.strip()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(f"[NapCat 流式上传] {path.name} 上传失败: {exc}")
    return None
