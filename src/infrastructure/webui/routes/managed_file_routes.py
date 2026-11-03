"""数据管理文件浏览、预览与逐项操作接口。"""

from __future__ import annotations

import asyncio
import base64
import binascii
from typing import TYPE_CHECKING

from astrbot.api.star import StarTools

from ....shared.constants import PLUGIN_NAME
from ...persistence.managed_files import MAX_FILE_BYTES, ManagedFiles
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from pathlib import Path


class ManagedFileRoutes:
    """管理显式文件分区；数据库与运行中目录只读。"""

    def __init__(self, report_dir: Path | None = None) -> None:
        self.report_dir = report_dir
        self._lock = asyncio.Lock()

    def store(self) -> ManagedFiles:
        """在请求时获取插件 data 目录，便于插件迁移和测试。"""
        return ManagedFiles(StarTools.get_data_dir(PLUGIN_NAME), self.report_dir)

    async def api_partitions(self) -> WebApiResponse:
        """返回全分区统计与操作能力。"""
        try:
            items = await asyncio.to_thread(self.store().overview)
            return json_response({"status": "ok", "data": {"items": items}})
        except OSError:
            return error_response("无法读取数据目录，请检查目录权限", status_code=500)

    async def api_files(self) -> WebApiResponse:
        """按分区分页搜索文件，不读取文件内容。"""
        try:
            query = request.query
            page = max(1, int(query.get("page", "1")))
            size = max(1, min(100, int(query.get("page_size", "20"))))
            search = query.get("search", "").casefold()
            items = await asyncio.to_thread(
                self.store().files, query.get("partition", "")
            )
            filtered = [item for item in items if search in item["name"].casefold()]
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "items": filtered[(page - 1) * size : page * size],
                        "total": len(filtered),
                    },
                }
            )
        except ValueError as error:
            return error_response(str(error), status_code=400)
        except OSError:
            return error_response("文件列表读取失败，请刷新后重试", status_code=500)

    async def api_content(self) -> WebApiResponse:
        """读取预览、下载或编辑所需的内容及修订号。"""
        try:
            content = await asyncio.to_thread(
                self.store().read,
                request.query.get("partition", ""),
                request.query.get("name", ""),
            )
            return json_response({"status": "ok", "data": content})
        except FileNotFoundError:
            return error_response("文件已不存在，请刷新列表", status_code=404)
        except (ValueError, UnicodeError) as error:
            return error_response(str(error), status_code=400)
        except OSError:
            return error_response("无法读取文件，请检查目录权限", status_code=500)

    async def api_mutate(self) -> WebApiResponse:
        """应用单文件变更，禁止未检查原内容即覆盖或删除。"""
        try:
            body = await request.json()
            fields = [
                body.get(key, "")
                for key in (
                    "partition",
                    "name",
                    "operation",
                    "revision",
                    "content_base64",
                    "new_name",
                )
            ]
            if not all(isinstance(field, str) for field in fields):
                raise ValueError("文件操作参数必须为字符串")
            partition, name, operation, revision, encoded, new_name = (
                str(field) for field in fields
            )
            if len(encoded) > (MAX_FILE_BYTES + 2) // 3 * 4:
                raise ValueError("文件不得超过 32 MiB")
            payload = base64.b64decode(encoded, validate=True)
            async with self._lock:
                await asyncio.to_thread(
                    self.store().mutate,
                    partition,
                    name,
                    operation,
                    revision,
                    payload,
                    new_name,
                )
            return json_response({"status": "ok", "data": {"success": True}})
        except FileExistsError as error:
            return error_response(str(error), status_code=409)
        except FileNotFoundError:
            return error_response("文件已不存在，请刷新列表", status_code=404)
        except (ValueError, UnicodeError, binascii.Error) as error:
            return error_response(str(error), status_code=400)
        except OSError:
            return error_response("文件操作失败，请检查目录权限后重试", status_code=500)
