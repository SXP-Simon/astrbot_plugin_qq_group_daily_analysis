"""数据管理文件浏览、预览与逐项操作接口。"""

from __future__ import annotations

import asyncio
import base64
import binascii
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, TypedDict

from astrbot.api.star import StarTools

from ....shared.comic_presets import COMIC_PRESETS
from ....shared.constants import PLUGIN_NAME
from ....shared.type_guards import is_object_list, is_string_mapping
from ...persistence.managed_files import MAX_FILE_BYTES, ManagedFiles
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from pathlib import Path


class ManagedFileGroup(TypedDict):
    """模板包目录及其完整文件统计。"""

    directory: str
    count: int
    size_bytes: int


class ManagedFileRoutes:
    """管理显式文件分区；数据库与运行中目录只读。"""

    def __init__(self, report_dir: Path | None = None) -> None:
        self.report_dir = report_dir
        self.mutation_lock = asyncio.Lock()

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
            extensions = {
                value.strip().lower().lstrip(".")
                for value in query.get("extensions", "").split(",")
                if value.strip()
            }
            partition = query.get("partition", "")
            items = await asyncio.to_thread(self.store().files, partition)
            directory = query.get("directory", "")
            if directory and query.get("partition") != "custom_templates":
                raise ValueError("只有自定义模板分区支持按模板目录筛选")
            groups: dict[str, ManagedFileGroup] = {}
            if query.get("partition") == "custom_templates":
                for item in items:
                    folder = (
                        item["name"].split("/", 1)[0] if "/" in item["name"] else "."
                    )
                    group = groups.setdefault(
                        folder, {"directory": folder, "count": 0, "size_bytes": 0}
                    )
                    group["count"] += 1
                    group["size_bytes"] += item["size_bytes"]
            filtered = [
                item
                for item in items
                if (
                    search in item["name"].casefold()
                    or (
                        partition == "comic_preview_cache"
                        and (preset := COMIC_PRESETS.get(item["name"].split("/", 1)[0]))
                        is not None
                        and search in preset.name.casefold()
                    )
                )
                and (
                    not directory
                    or (
                        "/" not in item["name"]
                        if directory == "."
                        else item["name"].startswith(directory + "/")
                    )
                )
                and (
                    not extensions
                    or PurePosixPath(item["name"]).suffix.lower().lstrip(".")
                    in extensions
                )
            ]
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "items": filtered[(page - 1) * size : page * size],
                        "total": len(filtered),
                        "groups": [groups[key] for key in sorted(groups)],
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
            return json_response({"status": "ok", "data": content}, compress=True)
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
            if type(body) is not dict:
                raise ValueError("无效请求")
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
            async with self.mutation_lock:
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

    async def api_delete_many(self) -> WebApiResponse:
        """只删除显式选择的文件，分别返回成功和失败项，不扩展到筛选外文件。"""
        try:
            body = await request.json()
            if type(body) is not dict:
                raise ValueError("无效请求")
            partition, files = body.get("partition"), body.get("files")
            if (
                not isinstance(partition, str)
                or not is_object_list(files)
                or not 1 <= len(files) <= 200
            ):
                raise ValueError("请选择 1 到 200 个文件")
            selected: list[tuple[str, str]] = []
            for item in files:
                if (
                    not is_string_mapping(item)
                    or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("revision"), str)
                    or not item["revision"]
                ):
                    raise ValueError("每个文件都需要名称和选中时的修订号")
                selected.append((str(item["name"]), str(item["revision"])))
            if len({name for name, _ in selected}) != len(selected):
                raise ValueError("所选文件存在重复项")
            store = self.store()
            if not store.partition(partition).deletable:
                raise ValueError("此分区不允许删除文件")
            deleted: list[str] = []
            failed: list[dict[str, str]] = []
            async with self.mutation_lock:
                for name, revision in selected:
                    try:
                        await asyncio.to_thread(
                            store.mutate, partition, name, "delete", revision
                        )
                        deleted.append(name)
                    except (ValueError, OSError) as error:
                        failed.append({"name": name, "message": str(error)})
            return json_response(
                {"status": "ok", "data": {"deleted": deleted, "failed": failed}}
            )
        except ValueError as error:
            return error_response(str(error), status_code=400)
