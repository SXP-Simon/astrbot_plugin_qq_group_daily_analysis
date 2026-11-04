"""通过宿主二进制上传接口接收小分块，完成后复用文件分区的原子保存。"""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...persistence.managed_files import MAX_FILE_BYTES
from ..download_control import DownloadCancelled, DownloadControl
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from pathlib import Path

    from .managed_file_routes import ManagedFileRoutes

CHUNK_BYTES = 1024 * 1024


@runtime_checkable
class UploadedChunk(Protocol):
    """宿主上传文件的最小读取契约。"""

    async def read(self, size: int = -1) -> bytes: ...


@dataclass
class UploadSession:
    """一个页面拥有的临时上传，目标元数据在首块后固定。"""

    path: Path
    partition: str
    name: str
    operation: str
    revision: str
    total: int
    received: int = 0
    updated: float = 0


class ManagedUploadRoutes:
    """接收分块、取消实际请求，并清理失败或过期的临时文件。"""

    def __init__(self, files: ManagedFileRoutes, downloads: DownloadControl) -> None:
        self.files = files
        self.downloads = downloads
        self._sessions: dict[str, UploadSession] = {}

    def _discard(self, upload_id: str) -> None:
        """移除上传会话及其专属临时文件。

        Args:
            upload_id: 已校验的 UUID。
        """
        session = self._sessions.pop(upload_id, None)
        if session:
            session.path.unlink(missing_ok=True)

    def _save_chunk(self, session: UploadSession, payload: bytes) -> None:
        """在线程内追加分块；末块复用分区校验与乐观并发保存。

        Args:
            session: 当前持有文件变更锁的上传会话。
            payload: 已限制大小的二进制分块。
        """
        session.path.parent.mkdir(parents=True, exist_ok=True)
        with session.path.open("xb" if session.received == 0 else "ab") as output:
            output.write(payload)
        session.received += len(payload)
        session.updated = time.monotonic()
        if session.received == session.total:
            self.files.store().mutate(
                session.partition,
                session.name,
                session.operation,
                session.revision,
                session.path.read_bytes(),
            )

    async def api_start(self) -> WebApiResponse:
        """先用小 JSON 固定元数据，二进制接口仅使用宿主允许的路径参数。

        Returns:
            初始化回执；不会修改正式文件。
        """
        try:
            body = await request.json()
            if type(body) is not dict:
                raise ValueError("上传参数无效")
            upload_id = body.get("download_id")
            partition, name = body.get("partition"), body.get("name")
            operation, revision = body.get("operation"), body.get("revision", "")
            total = body.get("total")
            if (
                not isinstance(upload_id, str)
                or not isinstance(partition, str)
                or not isinstance(name, str)
                or not isinstance(operation, str)
                or not isinstance(revision, str)
            ):
                raise ValueError("上传参数无效")
            if str(uuid.UUID(upload_id)) != upload_id:
                raise ValueError("上传标识无效")
            store = self.files.store()
            if not store.partition(partition).writable or operation not in {
                "create",
                "replace",
            }:
                raise ValueError("此分区不支持上传")
            store.path(partition, name)
            if type(total) is not int or not 0 < total <= MAX_FILE_BYTES:
                raise ValueError("文件不能为空且不得超过 32 MiB")
            async with self.downloads.track(upload_id):
                for key, old in list(self._sessions.items()):
                    if time.monotonic() - old.updated > 600:
                        self._discard(key)
                if upload_id in self._sessions:
                    raise ValueError("上传任务已存在，请勿重复初始化")
                if len(self._sessions) >= 8:
                    raise ValueError("上传任务过多，请先完成或取消已有上传")
                directory = store.partition("typst_fonts").directory.parent / "uploads"
                directory.mkdir(parents=True, exist_ok=True)
                for leftover in directory.glob("*.part"):
                    if time.time() - leftover.stat().st_mtime > 600:
                        leftover.unlink(missing_ok=True)
                self._sessions[upload_id] = UploadSession(
                    directory / f"{upload_id}.part",
                    partition,
                    name,
                    operation,
                    revision,
                    total,
                    updated=time.monotonic(),
                )
            return json_response({"status": "ok", "data": {"upload_id": upload_id}})
        except DownloadCancelled:
            return error_response("上传已取消", status_code=409)
        except (ValueError, TypeError) as error:
            return error_response(str(error), status_code=400)
        except OSError:
            return error_response(
                "无法创建上传暂存目录，请检查权限或磁盘空间", status_code=500
            )

    async def api_upload(self, upload_id: str, offset: str) -> WebApiResponse:
        """接收一个分块；只有末块完整到达后才创建或替换正式文件。

        Args:
            upload_id: 初始化时固定的上传 UUID。
            offset: 已收到的字节数，用于拒绝重复或乱序分块。

        Returns:
            服务器已保存的字节数；失败或取消不会留下半份正式字体。
        """
        owned = False
        try:
            if str(uuid.UUID(upload_id)) != upload_id:
                raise ValueError("上传标识无效")
            position = int(offset)
            async with self.downloads.track(upload_id):
                owned = True
                session = self._sessions.get(upload_id)
                if session is None or time.monotonic() - session.updated > 600:
                    raise ValueError("上传已结束或过期，请重新选择文件")
                if position != session.received:
                    raise ValueError("上传分块与原任务不一致，请重新上传")
                # files 在新宿主为异步方法，旧宿主可能提供可等待的映射。
                incoming: object = request.files
                if callable(incoming):
                    incoming = incoming()
                if inspect.isawaitable(incoming):
                    incoming = await incoming
                get_file = getattr(incoming, "get", None)
                part: object = get_file("file") if callable(get_file) else None
                if not isinstance(part, UploadedChunk):
                    raise ValueError("未收到上传分块，请升级宿主后重试")
                payload = await part.read(CHUNK_BYTES + 1)
                if (
                    not payload
                    or len(payload) > CHUNK_BYTES
                    or position + len(payload) > session.total
                ):
                    raise ValueError("上传分块大小无效")
                async with self.files.mutation_lock:
                    writer = asyncio.create_task(
                        asyncio.to_thread(self._save_chunk, session, payload)
                    )
                    try:
                        await asyncio.shield(writer)
                    except asyncio.CancelledError:
                        # 取消不能与仍在运行的写入线程争抢临时文件。
                        await writer
                        raise
                complete = session.received == session.total
                if complete:
                    self._discard(upload_id)
                return json_response(
                    {
                        "status": "ok",
                        "data": {
                            "received": session.received,
                            "total": session.total,
                            "complete": complete,
                        },
                    }
                )
        except DownloadCancelled:
            self._discard(upload_id)
            return error_response("上传已取消，已保存的文件会保留", status_code=409)
        except asyncio.CancelledError:
            self._discard(upload_id)
            raise
        except FileExistsError as error:
            self._discard(upload_id)
            return error_response(str(error), status_code=409)
        except (ValueError, TypeError) as error:
            # 重复请求尚未取得所有权，不能清掉另一请求仍在写入的会话。
            if owned:
                self._discard(upload_id)
            return error_response(str(error), status_code=400)
        except OSError:
            self._discard(upload_id)
            return error_response(
                "上传保存失败，请检查数据目录权限或磁盘空间", status_code=500
            )

    async def api_cancel(self) -> WebApiResponse:
        """取消正在接收的分块，清理暂存并拒绝迟到的后续分块。

        Returns:
            复用受控传输的幂等取消回执。
        """
        body = await request.json()
        upload_id = body.get("download_id", "") if type(body) is dict else None
        result = await self.downloads.api_cancel()
        status = (
            result.get("status_code", 200)
            if isinstance(result, dict)
            else result.status_code
        )
        if isinstance(status, int) and status < 400 and isinstance(upload_id, str):
            self._discard(upload_id)
        return result
