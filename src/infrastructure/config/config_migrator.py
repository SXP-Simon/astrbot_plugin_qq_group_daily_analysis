"""
配置迁移与升级器 (Config Migrator)

负责 AstrBot 群聊分析插件的跨版本配置平滑迁移与自动升级，包括：
- 提示词模板从旧版 `str.format` 到 `string.Template`（`$VAR`）的自动检测与无损升级
- 旧版输出格式 `output_format` 从字符串到列表的兼容转换
- 漫画角色方案、全局参考图迁移、备份保护与默认提示词正反例升级
- 配置结构指纹比对与跨版本升级配置自动快照保护
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from astrbot.api.star import StarTools

from ...shared.constants import PLUGIN_NAME
from ...utils.logger import logger
from ...utils.template_utils import upgrade_str_format_template

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .config_manager import ConfigManager

StarToolsType = type[StarTools]


class ConfigMigrator:
    """配置迁移与版本升级器。"""

    def __init__(
        self,
        config_manager: ConfigManager,
        star_tools: StarToolsType | None = None,
    ):
        """初始化配置迁移器。

        Args:
            config_manager: 配置管理器主实例。
            star_tools: Star 工具类替身或模块（用于路径查找与测试替身注入）。
        """
        self.cm = config_manager
        self.star_tools: StarToolsType = star_tools or StarTools

    def run_all_migrations(self) -> None:
        """执行所有版本升级、数据结构迁移与结构保护检查。"""
        self.migrate_legacy_configs()
        self.upgrade_prompt_templates()
        self.migrate_daily_comic_character_references()
        self.migrate_daily_comic_character_prompts()
        self.migrate_legacy_comic_storyboard_prompts()
        self.protect_upgrade_data()

    def migrate_legacy_configs(self) -> bool:
        """升级旧版配置项的类型与数据结构，确保兼容新 Schema。

        Returns:
            bool: 是否发生了数据修改。
        """
        modified = False

        val = self.cm._get_group("basic").get("output_format")
        if isinstance(val, str):
            self.cm._ensure_group("basic")["output_format"] = [val]
            logger.info("output_format 已从旧版 string 自动迁移为 list")
            modified = True

        if modified:
            self.cm.save_config()
            logger.info("旧版配置迁移完成，已自动回写")
        return modified

    def upgrade_config_item(
        self,
        group: str,
        key: str,
        setter_func: Callable[[str], None],
    ) -> bool:
        """升级指定配置项的值（从 str.format -> string.Template），并回写。

        Args:
            group: 配置分组名或 prompt 子分组名。
            key: 配置键。
            setter_func: 配置项设置回调函数。

        Returns:
            bool: 该配置项是否被升级。
        """
        if group in (
            "quality_analysis_prompts",
            "topic_analysis_prompts",
            "user_title_analysis_prompts",
            "golden_quote_analysis_prompts",
            "comic_analysis_prompts",
        ):
            target_group = self.cm._get_group("prompts").get(group, {})
        else:
            target_group = self.cm._get_group(group)

        val = target_group.get(key, "")
        if not val or not isinstance(val, str):
            return False

        upgraded_val, upgraded = upgrade_str_format_template(val)
        if upgraded and upgraded_val != val:
            setter_func(upgraded_val)
            logger.info(
                f"配置项 {group}.{key} 发现旧版语法并已自动升级为 string.Template 格式。"
            )
            return True
        return False

    def upgrade_prompt_templates(self) -> bool:
        """扫描并升级所有可配置的提示词模板与文件名格式模板。

        Returns:
            bool: 是否升级了任何模板。
        """
        modified = False
        if hasattr(self.cm, "set_quality_analysis_prompt"):
            modified |= self.upgrade_config_item(
                "quality_analysis_prompts",
                "quality_v2_prompt",
                self.cm.set_quality_analysis_prompt,
            )
        if hasattr(self.cm, "set_quality_summary_prompt"):
            modified |= self.upgrade_config_item(
                "quality_analysis_prompts",
                "quality_summary_prompt",
                self.cm.set_quality_summary_prompt,
            )
        if hasattr(self.cm, "set_topic_analysis_prompt"):
            modified |= self.upgrade_config_item(
                "topic_analysis_prompts",
                "topic_prompt",
                self.cm.set_topic_analysis_prompt,
            )
        if hasattr(self.cm, "set_user_title_analysis_prompt"):
            modified |= self.upgrade_config_item(
                "user_title_analysis_prompts",
                "user_title_prompt",
                self.cm.set_user_title_analysis_prompt,
            )
        if hasattr(self.cm, "set_golden_quote_analysis_prompt"):
            modified |= self.upgrade_config_item(
                "golden_quote_analysis_prompts",
                "golden_quote_v2_prompt",
                self.cm.set_golden_quote_analysis_prompt,
            )
        if hasattr(self.cm, "set_comic_storyboard_prompt"):
            modified |= self.upgrade_config_item(
                "comic_analysis_prompts",
                "comic_storyboard_prompt",
                self.cm.set_comic_storyboard_prompt,
            )

        if hasattr(self.cm, "set_html_filename_format"):
            modified |= self.upgrade_config_item(
                "html",
                "html_filename_format",
                self.cm.set_html_filename_format,
            )

        if modified:
            logger.info(
                "已完成所有配置模板从 str.format 到 string.Template 的安全迁移。（已自动回写配置）"
            )
        return modified

    def _save_config(self) -> None:
        """安全触发配置保存。"""
        if hasattr(self.cm, "config") and hasattr(self.cm.config, "save_config"):
            self.cm.config.save_config()
        elif hasattr(self.cm, "save_config"):
            self.cm.save_config()

    def migrate_daily_comic_character_references(self) -> None:
        """将旧版全局参考图平滑迁移到角色方案模板列表。"""
        daily_comic = self.cm._get_group("daily_comic")
        characters = daily_comic.get("comic_characters")
        if isinstance(characters, list) and len(characters) > 0:
            return

        old_references = daily_comic.get("drawing_reference_image")
        if isinstance(old_references, str):
            # 早期版本允许 URL 或任意本地路径，原生文件控件不能安全地继续使用它们。
            backup_data = {"drawing_reference_image": old_references}
            backup_func = getattr(
                self.cm, "_write_comic_config_backup", self.write_comic_config_backup
            )
            if not backup_func(backup_data):
                logger.warning(
                    "旧版漫画参考图备份失败，将保留原配置并在下次重载时重试。"
                )
                return
            daily_comic["drawing_reference_image"] = []
            self._save_config()
            logger.info(
                "已备份并清除不受支持的旧版漫画参考图配置，请在 WebUI 重新选择图片。"
            )
            return

        references = (
            [
                reference.strip()
                for reference in old_references
                if isinstance(reference, str) and reference.strip()
            ]
            if isinstance(old_references, list)
            else []
        )

        if not references:
            return

        specific_persona_id = ""
        if self.cm.get_use_plugin_specific_persona():
            specific_persona_id = self.cm.get_plugin_specific_persona_id().strip()

        copy_func = getattr(
            self.cm,
            "_copy_legacy_comic_reference_images",
            self.copy_legacy_comic_reference_images,
        )
        migrated_references = copy_func(references)
        if len(migrated_references) != len(references):
            logger.warning(
                "旧版漫画参考图尚未完整迁移，将保留原配置并在下次重载时重试。"
            )
            return
        backup_data = {
            "drawing_reference_image": references,
            "use_plugin_specific_persona": (self.cm.get_use_plugin_specific_persona()),
            "plugin_specific_persona_id": specific_persona_id,
        }
        backup_func = getattr(
            self.cm, "_write_comic_config_backup", self.write_comic_config_backup
        )
        if not backup_func(backup_data):
            logger.warning("旧版漫画参考图备份失败，将保留原配置并在下次重载时重试。")
            return
        daily_comic["comic_characters"] = [
            {
                "__template_key": "character",
                "name": "默认角色方案",
                "enable": True,
                "persona_id": specific_persona_id,
                "reference_images": migrated_references,
                "storyboard_prompt": self.cm.get_comic_storyboard_prompt(),
            }
        ]
        daily_comic["drawing_reference_image"] = []
        self._save_config()
        logger.info(
            "已将旧版漫画参考图迁移到“默认角色方案”，原始配置已备份到插件数据目录。"
        )

    def migrate_daily_comic_character_prompts(self) -> None:
        """将旧版全局分镜提示词复制到既有角色方案。"""
        state_path = (
            self.star_tools.get_data_dir(PLUGIN_NAME)
            / "comic_character_prompt_migration.json"
        )
        if state_path.exists():
            return

        daily_comic = self.cm._get_group("daily_comic")
        characters = daily_comic.get("comic_characters", [])
        default_prompt = self.cm.get_comic_storyboard_prompt()
        modified = False
        if isinstance(characters, list):
            for character in characters:
                if not isinstance(character, dict):
                    continue
                if not str(character.get("storyboard_prompt", "")).strip():
                    character["storyboard_prompt"] = default_prompt
                    modified = True

        try:
            if modified:
                self._save_config()
                logger.info("已将默认漫画场景分析提示词迁移到既有角色方案。")
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"completed": True}), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"迁移漫画角色场景提示词失败，将在下次重载时重试: {exc}")

    def migrate_legacy_comic_storyboard_prompts(self) -> None:
        """自动将旧版默认漫画分镜提示词升级迁移至包含 GOOD/BAD 正反例的新版模板。"""
        try:
            from ..analysis.analyzers.comic_analyzer import (
                DEFAULT_COMIC_STORYBOARD_PROMPT,
            )
        except Exception:
            from src.infrastructure.analysis.analyzers.comic_analyzer import (
                DEFAULT_COMIC_STORYBOARD_PROMPT,
            )

        modified = False

        prompts = self.cm._get_group("prompts")
        comic_prompts = prompts.get("comic_analysis_prompts")
        if isinstance(comic_prompts, dict):
            current_global = comic_prompts.get("comic_storyboard_prompt")
            if self.is_legacy_default_comic_prompt(current_global):
                comic_prompts["comic_storyboard_prompt"] = (
                    DEFAULT_COMIC_STORYBOARD_PROMPT
                )
                modified = True

        daily_comic = self.cm._get_group("daily_comic")
        characters = daily_comic.get("comic_characters", [])
        if isinstance(characters, list):
            for char in characters:
                if not isinstance(char, dict):
                    continue
                char_prompt = char.get("storyboard_prompt")
                if self.is_legacy_default_comic_prompt(char_prompt):
                    char["storyboard_prompt"] = DEFAULT_COMIC_STORYBOARD_PROMPT
                    modified = True

        if modified:
            try:
                self._save_config()
                logger.info(
                    "已自动将历史旧版漫画分镜提示词升级迁移为包含 GOOD/BAD 正反例的新版规范模板。"
                )
            except Exception as exc:
                logger.warning(f"自动迁移漫画分镜提示词失败: {exc}")

    def protect_upgrade_data(self) -> None:
        """在插件升级且配置结构发生变更时备份旧配置。"""
        plugin_root = self._get_plugin_root()
        current_version = self.get_plugin_version(plugin_root)
        current_schema_fingerprint = self.get_schema_fingerprint(plugin_root)
        state_path = (
            self.star_tools.get_data_dir(PLUGIN_NAME) / "upgrade_protection_state.json"
        )
        previous_state = self.read_upgrade_protection_state(state_path)
        previous_version = str(previous_state.get("version", "")).strip()

        if not previous_state:
            logger.debug("升级保护基线已建立，后续配置结构变化时可备份本次快照。")

        if previous_state.get(
            "schema_fingerprint"
        ) != current_schema_fingerprint and isinstance(
            previous_state.get("config"), dict
        ):
            backup_func = getattr(
                self.cm,
                "_write_upgrade_config_backup",
                self.write_upgrade_config_backup,
            )
            if not backup_func(previous_state["config"], previous_version):
                logger.warning("插件旧配置备份失败，本次不会更新升级保护状态。")
                return

        config_data = dict(self.cm.config) if self.cm.config else {}
        self.save_upgrade_protection_state(
            state_path,
            {
                "version": current_version,
                "schema_fingerprint": current_schema_fingerprint,
                "config": config_data,
            },
        )

    def _get_plugin_root(self) -> Path:
        """获取插件根目录（支持测试替身覆盖 cm._get_plugin_root）。

        Returns:
            Path: 插件根目录路径。
        """
        if hasattr(self.cm, "_get_plugin_root") and callable(self.cm._get_plugin_root):
            return self.cm._get_plugin_root()
        return self.get_plugin_root()

    @staticmethod
    def get_plugin_root() -> Path:
        """获取插件根目录。

        Returns:
            Path: 插件根目录绝对路径。
        """
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def get_plugin_version(plugin_root: Path) -> str:
        """从 metadata.yaml 读取当前插件版本。

        Args:
            plugin_root: 插件根目录路径。

        Returns:
            str: 版本号字符串，读取失败时返回 'unknown'。
        """
        try:
            metadata = (plugin_root / "metadata.yaml").read_text(encoding="utf-8")
            match = re.search(r"^version:\s*([^\s#]+)", metadata, re.MULTILINE)
            if match:
                return match.group(1)
        except OSError as exc:
            logger.warning(f"读取插件版本失败，将使用未知版本标识: {exc}")
        return "unknown"

    @staticmethod
    def get_schema_fingerprint(plugin_root: Path) -> str:
        """计算配置结构指纹，忽略描述等纯界面字段。

        Args:
            plugin_root: 插件根目录路径。

        Returns:
            str: 配置结构 SHA256 指纹。
        """
        try:
            schema = json.loads(
                (plugin_root / "_conf_schema.json").read_text(encoding="utf-8-sig")
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"读取插件配置结构失败: {exc}")
            return ""

        def extract_shape(items: dict) -> dict:
            shape = {}
            for key, item in items.items():
                if not isinstance(item, dict):
                    continue
                entry = {"type": item.get("type")}
                for property_name in ("default", "options", "file_types"):
                    if property_name in item:
                        entry[property_name] = item[property_name]
                if isinstance(item.get("items"), dict):
                    entry["items"] = extract_shape(item["items"])
                if isinstance(item.get("templates"), dict):
                    entry["templates"] = {
                        template_key: extract_shape(template.get("items", {}))
                        for template_key, template in item["templates"].items()
                        if isinstance(template, dict)
                    }
                shape[key] = entry
            return shape

        serialized_shape = json.dumps(
            extract_shape(schema),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized_shape.encode("utf-8")).hexdigest()

    @staticmethod
    def read_upgrade_protection_state(state_path: Path) -> dict:
        """读取上一次正常启动记录的升级保护状态。

        Args:
            state_path: 升级状态记录文件路径。

        Returns:
            dict: 升级保护状态字典。
        """
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def save_upgrade_protection_state(state_path: Path, state: dict) -> None:
        """原子保存升级保护状态。

        Args:
            state_path: 升级状态记录文件路径。
            state: 待写入的状态字典。
        """
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = state_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary_path.replace(state_path)
        except OSError as exc:
            logger.warning(f"保存插件升级保护状态失败: {exc}")

    @staticmethod
    def write_upgrade_config_backup_data(
        config: dict[str, object],
        version: str,
        star_tools: StarToolsType | None = None,
    ) -> bool:
        """保存旧版本配置快照，并最多保留二十份。

        Args:
            config: 上一次正常加载时记录的插件配置快照。
            version: 该配置快照对应的旧插件版本。
            star_tools: Star 工具类替身或模块。

        Returns:
            bool: 备份写入并完成轮换时返回 True，否则返回 False。
        """
        try:
            tools = star_tools or StarTools
            backup_dir = tools.get_data_dir(PLUGIN_NAME) / "config_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", version) or "unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = backup_dir / f"plugin_config_{safe_version}_{timestamp}.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "backed_up_at": datetime.now().isoformat(),
                        "plugin_version": version,
                        "config": config,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            backups = sorted(
                backup_dir.glob("plugin_config_*.json"),
                key=lambda path: (path.stat().st_mtime, path.name),
            )
            for expired_backup in backups[:-20]:
                expired_backup.unlink()
            logger.info(
                "检测到插件配置结构变化，已备份上一次正常启动保存的配置快照："
                f"旧版本={version}，文件={backup_path.name}，路径={backup_path.resolve()}，"
                f"当前保留={min(len(backups), 20)} 份。"
            )
            return True
        except OSError as exc:
            logger.warning(f"备份插件旧配置失败: {exc}")
            return False

    def write_upgrade_config_backup(
        self,
        config: dict[str, object],
        version: str,
        star_tools: StarToolsType | None = None,
    ) -> bool:
        """保存旧版本配置快照。

        Args:
            config: 上一次正常加载时记录的插件配置快照。
            version: 该配置快照对应的旧插件版本。
            star_tools: Star 工具类替身或模块。

        Returns:
            bool: 备份写入并完成轮换时返回 True，否则返回 False。
        """
        tools = star_tools or self.star_tools
        return self.write_upgrade_config_backup_data(config, version, star_tools=tools)

    @staticmethod
    def is_legacy_default_comic_prompt(prompt: object) -> bool:
        """判断是否为旧版默认漫画分镜提示词（尚未包含 GOOD/BAD 正反例规范）。

        Args:
            prompt: 待检查的提示词对象。

        Returns:
            bool: 是否为旧版默认提示词。
        """
        if not isinstance(prompt, str) or not prompt.strip():
            return False
        text = prompt.strip()
        if "GOOD EXAMPLE" in text:
            return False
        return (
            '请输出包含 "scene" 字段的 JSON 对象。' in text
            or '请输出包含 \\"scene\\" 字段的 JSON 对象。' in text
            or (
                "你是一个资深的漫画分镜师与 AI 绘画提示词专家。" in text
                and "【核心视觉、台词与双层排版规则】" in text
            )
        )

    @staticmethod
    def write_comic_config_backup(
        data: Mapping[str, object],
        star_tools: StarToolsType | None = None,
    ) -> bool:
        """写入漫画配置迁移备份。

        Args:
            data: 需要保留的旧版漫画相关配置。
            star_tools: Star 工具类替身或模块。

        Returns:
            bool: 备份写入是否成功。
        """
        try:
            tools = star_tools or StarTools
            backup_dir = tools.get_data_dir(PLUGIN_NAME) / "config_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"comic_character_migration_{timestamp}.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "migrated_at": datetime.now().isoformat(),
                        "config": dict(data),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return True
        except OSError as exc:
            logger.warning(f"保存漫画配置迁移备份失败: {exc}")
            return False

    @staticmethod
    def copy_legacy_comic_reference_images(
        references: list[str],
        star_tools: StarToolsType | None = None,
    ) -> list[str]:
        """复制旧参考图到角色模板对应的原生上传目录。

        Args:
            references: 旧版全局参考图相对路径列表。
            star_tools: Star 工具类替身或模块。

        Returns:
            list[str]: 可写入新角色方案的参考图相对路径列表。
        """
        tools = star_tools or StarTools
        plugin_data_dir = tools.get_data_dir(PLUGIN_NAME)
        relative_dir = Path(
            "files/daily_comic/comic_characters/templates/character/reference_images"
        )
        target_dir = plugin_data_dir / relative_dir
        migrated_references = []
        for index, reference in enumerate(references, start=1):
            try:
                source_path = (plugin_data_dir / reference).resolve()
                source_path.relative_to(plugin_data_dir.resolve())
                if not source_path.is_file():
                    logger.warning(f"旧版漫画参考图不存在，跳过迁移: {reference}")
                    continue

                target_dir.mkdir(parents=True, exist_ok=True)
                target_name = f"migrated_{index}_{source_path.name}"
                target_path = target_dir / target_name
                shutil.copy2(source_path, target_path)
                migrated_references.append((relative_dir / target_name).as_posix())
            except (OSError, ValueError) as exc:
                logger.warning(f"迁移旧版漫画参考图失败 {reference}: {exc}")
        return migrated_references
