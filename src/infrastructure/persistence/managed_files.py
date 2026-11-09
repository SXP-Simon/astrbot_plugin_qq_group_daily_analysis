"""插件文件分区管理：显式能力、目录边界与乐观并发检查。"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    from pathlib import Path

from ..reporting.template_asset_catalog import RESOURCE_FILES
from ..reporting.template_resources import TemplateResourceStore

MAX_FILE_BYTES = 32 * 1024 * 1024
TEXT_SUFFIXES = {
    ".html",
    ".css",
    ".js",
    ".json",
    ".typ",
    ".svg",
    ".txt",
    ".md",
    ".yaml",
    ".yml",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


@dataclass(frozen=True)
class FilePartition:
    """一个文件分区及其允许的操作。"""

    key: str
    name: str
    directory: Path
    description: str
    impact: str
    writable: bool = False
    deletable: bool = True
    recursive: bool = True


class ManagedFileInfo(TypedDict):
    """列表条目，不在列表请求中读取完整文件。"""

    name: str
    size_bytes: int
    modified_at: float
    media_type: str
    editable: bool
    downloadable: bool
    revision: str


class ManagedFiles:
    """只管理插件自身持有的目录，禁止访问宿主全局临时目录。"""

    def __init__(self, data_dir: Path, report_dir: Path | None = None) -> None:
        self.data_dir = data_dir
        self.partitions = {
            item.key: item
            for item in (
                FilePartition(
                    "reports",
                    "历史报告文件",
                    report_dir or data_dir / "reports",
                    "已生成的图片及 HTML 报告",
                    "删除后历史报告无法预览；分析摘要仍保留。",
                ),
                FilePartition(
                    "custom_templates",
                    "自定义报告模板",
                    data_dir / "custom_t2i_templates" / "reporting_templates",
                    "已安装模板的源码及素材；安装入口支持完整模板包",
                    "源码修改立即用于后续渲染，请先下载留存原版。",
                    writable=True,
                ),
                FilePartition(
                    "config_files",
                    "配置参考素材",
                    data_dir / "files",
                    "配置中心上传的漫画、角色参考图片",
                    "替换同名文件保留原路径；删除会使相关配置引用失效。",
                    writable=True,
                ),
                FilePartition(
                    "config_backups",
                    "配置自动备份",
                    data_dir / "config_backups",
                    "升级与迁移保留的 JSON 配置；只读原件，可导出",
                    "删除将失去对应版本的恢复依据。",
                ),
                FilePartition(
                    "typst_fonts",
                    "Typst 字体",
                    data_dir / "typst" / "fonts",
                    "内置主题和自定义模板共用字体，可按主题下载或上传",
                    "移除字体会触发字体回退，可能改变报告排版。",
                    writable=True,
                ),
                FilePartition(
                    "template_resources",
                    "模板原始素材",
                    data_dir / "typst" / "resources",
                    "CDN 下载或手动替换的主题素材；开发仓库内素材不计入此分区",
                    "删除本地素材后会回退至仓库素材或从 CDN 重新获取。",
                    writable=True,
                ),
                FilePartition(
                    "typst_assets",
                    "Typst 派生图片缓存",
                    data_dir / "typst" / "assets",
                    "裁切、缩放及透明度处理后的图片",
                    "删除后下次渲染自动重建。",
                ),
                FilePartition(
                    "typst_jobs",
                    "Typst 渲染任务目录",
                    data_dir / "typst" / "jobs",
                    "独立编译工作目录，可查看和导出排障",
                    "任务目录由渲染器管理，避免删除正在使用的文件。",
                    deletable=False,
                ),
                FilePartition(
                    "preview_cache",
                    "模板预览缓存",
                    data_dir / "template_preview_cache",
                    "模板画廊预览图片",
                    "删除后按需重新生成预览。",
                ),
                FilePartition(
                    "comic_preview_cache",
                    "漫画样图缓存",
                    data_dir / "comic_preview_cache",
                    "群聊漫画风格预览使用的缩略图和完整样图",
                    "清理后，下一次查看样图时会按需重新获取。",
                ),
                FilePartition(
                    "hosted_reports",
                    "托管 HTML 报告",
                    data_dir / "self_hosted_html_reports",
                    "用于分享链接的 HTML 报告",
                    "删除后对应分享链接失效。",
                ),
                FilePartition(
                    "legacy_history",
                    "旧版历史记录",
                    data_dir / "history",
                    "兼容旧版本的历史 JSON 文件；当前分析记录存储在 KV 中",
                    "删除将移除旧版历史数据。",
                ),
                FilePartition(
                    "avatar_storage",
                    "头像缓存存储",
                    data_dir / "avatar",
                    "DiskCache 管理的头像数据库与二进制；请通过头像条目管理",
                    "数据库文件仅展示统计，不允许直接修改。",
                    deletable=False,
                ),
                FilePartition(
                    "state",
                    "状态与数据库",
                    data_dir,
                    "链路/快照数据库、去重数据库及插件状态文件；仅展示文件元数据",
                    "数据库应通过分析记录、快照等模块操作，不直接修改底层文件。",
                    deletable=False,
                    recursive=False,
                ),
            )
        }

    def partition(self, key: str) -> FilePartition:
        """取得白名单分区。"""
        if key not in self.partitions:
            raise ValueError("未知数据分区")
        return self.partitions[key]

    def path(self, key: str, name: str) -> Path:
        """校验相对路径及中间目录，拒绝符号链接、隐藏路径和平台路径语法。

        Args:
            key: 分区标识。
            name: 分区内 POSIX 相对路径。

        Returns:
            校验后的文件路径。

        Raises:
            ValueError: 路径越界、分区根目录被链接替换或名称非法。
        """
        part = self.partition(key)
        pieces = name.split("/")
        if (
            not name
            or len(name) > 512
            or any(
                not piece
                or piece.startswith(".")
                or any(ord(char) < 32 for char in piece)
                or any(char in piece for char in '\\:<>"|?*\x00')
                or piece.endswith((" ", "."))
                or piece.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10)),
                }
                for piece in pieces
            )
        ):
            raise ValueError("文件名或相对路径无效")
        if not part.recursive and len(pieces) != 1:
            raise ValueError("此分区只展示顶层文件")
        path = part.directory / name
        if not path.resolve().is_relative_to(part.directory.resolve()):
            raise ValueError("文件超出数据分区")
        for ancestor in (path, *path.parents):
            if ancestor.is_symlink():
                raise ValueError("不允许操作链接目录或文件")
            if ancestor == self.data_dir.parent:
                break
        return path

    def files(self, key: str) -> list[ManagedFileInfo]:
        """列出受管理文件，忽略临时文件和链接。

        Args:
            key: 分区标识。

        Returns:
            按修改时间降序排列的文件元数据。
        """
        part = self.partition(key)
        items: list[ManagedFileInfo] = []
        if not part.directory.exists():
            return items
        for path in (
            part.directory.rglob("*") if part.recursive else part.directory.iterdir()
        ):
            try:
                name = path.relative_to(part.directory).as_posix()
                self.path(key, name)
                if not path.is_file():
                    continue
                stat = path.stat()
            except (ValueError, OSError):
                continue
            items.append(
                {
                    "name": name,
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "media_type": mimetypes.guess_type(name)[0]
                    or "application/octet-stream",
                    "editable": part.writable
                    and path.suffix.lower() in TEXT_SUFFIXES
                    and key != "template_resources",
                    "downloadable": key not in {"state", "avatar_storage"},
                    "revision": "stat:"
                    + hashlib.sha256(
                        f"{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}".encode()
                    ).hexdigest(),
                }
            )
        return sorted(items, key=lambda item: (-item["modified_at"], item["name"]))

    def overview(self) -> list[dict[str, object]]:
        """统计所有显式分区，不读取文件内容。"""
        result: list[dict[str, object]] = []
        for part in self.partitions.values():
            files = self.files(part.key)
            result.append(
                {
                    "key": part.key,
                    "name": part.name,
                    "directory": str(part.directory),
                    "description": part.description,
                    "impact": part.impact,
                    "writable": part.writable,
                    "deletable": part.deletable,
                    "count": len(files),
                    "size_bytes": sum(item["size_bytes"] for item in files),
                }
            )
        return result

    def read(self, key: str, name: str) -> dict[str, object]:
        """读取单个文件及内容修订号，数据库与内部状态不开放下载。"""
        if key in {"state", "avatar_storage"}:
            raise ValueError("内部数据库与状态文件不支持直接读取")
        path = self.path(key, name)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("单文件预览或下载上限为 32 MiB")
        payload = path.read_bytes()
        text = None
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = payload.decode("utf-8")
        return {
            "name": name,
            "content_base64": base64.b64encode(payload).decode(),
            "text": text,
            "revision": hashlib.sha256(payload).hexdigest(),
            "media_type": mimetypes.guess_type(name)[0] or "application/octet-stream",
        }

    def mutate(
        self,
        key: str,
        name: str,
        operation: str,
        revision: str = "",
        payload: bytes = b"",
        new_name: str = "",
    ) -> None:
        """执行单文件变更，覆盖和删除必须携带当前内容修订号。

        Args:
            key: 白名单分区。
            name: 文件相对路径。
            operation: create、replace、delete 或 rename。
            revision: 读取时的 SHA256，避免静默覆盖其他修改。
            payload: 新文件字节。
            new_name: 重命名目标。

        Raises:
            ValueError: 操作、格式或文件内容不合法。
            FileExistsError: 创建目标已存在，或修订号已过期。
        """
        part, path = self.partition(key), self.path(key, name)
        if operation not in {"create", "replace", "delete", "rename"}:
            raise ValueError("未知文件操作")
        if (operation == "delete" and not part.deletable) or (
            operation != "delete" and not part.writable
        ):
            raise ValueError("此分区不支持该操作")
        if operation == "create":
            if path.exists():
                raise FileExistsError("同名文件已存在，请选择替换并检查原文件")
        else:
            if not revision:
                raise FileExistsError("缺少文件修订号，请刷新后重试")
            stat = path.stat()
            current_revision = (
                "stat:"
                + hashlib.sha256(
                    f"{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}".encode()
                ).hexdigest()
            )
            if revision != current_revision:
                digest = hashlib.sha256()
                with path.open("rb") as original:
                    for chunk in iter(lambda: original.read(65536), b""):
                        digest.update(chunk)
                current_revision = digest.hexdigest()
            if revision != current_revision:
                raise FileExistsError("文件已变更，请刷新并重新检查后操作")
        if operation == "delete":
            path.unlink()
            return
        if operation == "rename":
            if key not in {"custom_templates", "config_files"}:
                raise ValueError("此分区的文件名由模板清单管理，不支持重命名")
            target = self.path(key, new_name)
            if target.exists():
                raise FileExistsError("目标文件已存在")
            if target.suffix.lower() != path.suffix.lower():
                raise ValueError("重命名不可更改文件类型")
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
            return
        suffix = path.suffix.lower()
        if len(payload) > MAX_FILE_BYTES or (
            not payload and (key != "custom_templates" or suffix not in TEXT_SUFFIXES)
        ):
            raise ValueError("文件不能为空且不得超过 32 MiB")
        if key == "template_resources" and name not in RESOURCE_FILES:
            raise ValueError("请选择主题清单中的素材文件名")
        if key == "typst_fonts":
            if (
                "/" in name
                or suffix not in {".ttf", ".otf", ".ttc"}
                or payload[:4] not in {b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true"}
            ):
                raise ValueError("请上传有效的 TTF、OTF 或 TTC 字体")
        elif key == "config_files" and suffix not in IMAGE_SUFFIXES:
            raise ValueError("配置参考素材仅支持图片")
        elif (
            key == "custom_templates"
            and suffix
            not in TEXT_SUFFIXES | IMAGE_SUFFIXES | {".woff", ".woff2", ".ttf", ".otf"}
        ):
            raise ValueError("不支持此模板文件类型")
        if suffix in TEXT_SUFFIXES:
            text = payload.decode("utf-8")
            if suffix == ".json":
                json.loads(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        try:
            temporary.write_bytes(payload)
            if suffix in IMAGE_SUFFIXES:
                try:
                    TemplateResourceStore.validate(temporary, name)
                except (UnidentifiedImageError, Image.DecompressionBombError) as error:
                    raise ValueError("图片内容无效或超出像素预算") from error
            if operation == "create":
                # 硬链接创建具备排他性，避免并发创建时覆盖已有文件。
                os.link(temporary, path)
            else:
                temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
