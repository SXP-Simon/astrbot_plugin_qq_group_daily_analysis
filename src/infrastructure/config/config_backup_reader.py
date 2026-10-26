"""读取配置备份及其原始 JSON，不依赖当前配置结构。"""

import json
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
BackupKind = Literal["upgrade", "comic_migration", "other"]
MAX_BACKUP_BYTES = 8 * 1024 * 1024


class ConfigBackupInfo(TypedDict):
    """备份列表的文件信息，缺失元数据不从文件名推测。"""

    filename: str
    size_bytes: int
    kind: BackupKind
    plugin_version: str | None
    saved_at: str | None
    error: str | None


class ConfigBackupDetail(TypedDict):
    """备份元数据与完整 JSON 内容。"""

    backup: ConfigBackupInfo
    content: JsonValue


class ConfigBackupReader:
    """限制在插件备份目录中的只读文件适配器。"""

    def __init__(self, directory: Path):
        self.directory = directory

    def read(self, filename: str) -> ConfigBackupDetail:
        """读取一份备份，拒绝目录跳转、符号链接和超大文件。

        Args:
            filename: 列表返回的 JSON 文件名。

        Returns:
            文件内记录的版本、时间及未经业务转换的 JSON。

        Raises:
            ValueError: 文件名无效、内容损坏或超过大小限制。
            OSError: 文件不存在或无法读取。
        """
        if (
            not filename
            or Path(filename).name != filename
            or any(char in filename for char in ("/", "\\"))
            or not filename.endswith(".json")
        ):
            raise ValueError("请选择列表中的 JSON 备份文件")
        path = self.directory / filename
        if path.is_symlink() or path.resolve().parent != self.directory.resolve():
            raise ValueError("无法读取备份目录以外的文件")
        with path.open("rb") as stream:
            content = stream.read(MAX_BACKUP_BYTES + 1)
        if len(content) > MAX_BACKUP_BYTES:
            raise ValueError("备份超过 8 MiB，暂时无法在页面中查看")
        try:
            document: JsonValue = json.loads(content.decode("utf-8-sig"))
            # 标准 JSON 不接受 NaN / Infinity，避免接口返回浏览器无法解析的数据。
            json.dumps(document, allow_nan=False)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise ValueError("备份不是有效的 UTF-8 JSON 文件") from exc
        metadata = document if isinstance(document, dict) else {}
        version = metadata.get("plugin_version")
        timestamp = metadata.get("backed_up_at") or metadata.get("migrated_at")
        info: ConfigBackupInfo = {
            "filename": filename,
            "size_bytes": len(content),
            "kind": "upgrade"
            if filename.startswith("plugin_config_")
            else "comic_migration"
            if filename.startswith("comic_character_migration_")
            else "other",
            "plugin_version": version
            if isinstance(version, str) and version.strip()
            else None,
            "saved_at": timestamp
            if isinstance(timestamp, str) and timestamp.strip()
            else None,
            "error": None,
        }
        return {"backup": info, "content": document}

    def list_backups(self) -> list[ConfigBackupInfo]:
        """列出备份；个别文件损坏不会阻止其余文件显示。

        Returns:
            按文件名倒序排列的元数据，无法解析的文件包含错误说明。
        """
        if not self.directory.exists():
            return []
        items: list[ConfigBackupInfo] = []
        for path in sorted(
            self.directory.glob("*.json"), key=lambda item: item.name, reverse=True
        ):
            try:
                items.append(self.read(path.name)["backup"])
            except (ValueError, OSError) as exc:
                try:
                    size = 0 if path.is_symlink() else path.stat().st_size
                except OSError:
                    size = 0
                items.append(
                    {
                        "filename": path.name,
                        "size_bytes": size,
                        "kind": "other",
                        "plugin_version": None,
                        "saved_at": None,
                        "error": str(exc)
                        if isinstance(exc, ValueError)
                        else "文件已删除或无法读取",
                    }
                )
        return items
