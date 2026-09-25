"""
配置管理模块 - 基础设施层
负责处理插件配置
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astrbot.api import AstrBotConfig
from astrbot.api.star import StarTools

from ...shared.constants import DEFAULT_ATRI_ASSETS_CDN_URL, PLUGIN_NAME
from ...utils.logger import logger
from .config_migrator import ConfigMigrator


class ConfigManager:
    """配置管理器

    配置结构采用分组嵌套方式，顶层分为以下分组：
    - basic: 基础设置
    - qq_official: QQ 官方机器人展示设置
    - auto_analysis: 自动分析设置
    - llm: LLM 设置
    - analysis_features: 分析功能开关
    - incremental: 增量分析设置
    - prompts: 提示词模板
    """

    StarTools = StarTools
    config: AstrBotConfig
    _migrator: ConfigMigrator

    def __init__(self, config: AstrBotConfig) -> None:
        self.config = config
        self._migrator = ConfigMigrator(self, star_tools=StarTools)
        self._migrator.run_all_migrations()

    def _protect_upgrade_data(self) -> None:
        """在插件升级且配置结构发生变更时备份旧配置（委托 ConfigMigrator）。"""
        migrator = getattr(self, "_migrator", None) or ConfigMigrator(
            self, star_tools=getattr(self, "StarTools", StarTools)
        )
        migrator.protect_upgrade_data()

    @staticmethod
    def _get_plugin_root() -> Path:
        """获取插件根目录（委托 ConfigMigrator）。"""
        return ConfigMigrator.get_plugin_root()

    @staticmethod
    def _get_plugin_version(plugin_root: Path) -> str:
        """从 metadata.yaml 读取当前插件版本（委托 ConfigMigrator）。"""
        return ConfigMigrator.get_plugin_version(plugin_root)

    @staticmethod
    def _get_schema_fingerprint(plugin_root: Path) -> str:
        """计算配置结构指纹（委托 ConfigMigrator）。"""
        return ConfigMigrator.get_schema_fingerprint(plugin_root)

    @staticmethod
    def _read_upgrade_protection_state(state_path: Path) -> dict:
        """读取上一次正常启动记录的升级保护状态（委托 ConfigMigrator）。"""
        return ConfigMigrator.read_upgrade_protection_state(state_path)

    @staticmethod
    def _save_upgrade_protection_state(state_path: Path, state: dict) -> None:
        """原子保存升级保护状态（委托 ConfigMigrator）。"""
        ConfigMigrator.save_upgrade_protection_state(state_path, state)

    def _write_upgrade_config_backup(self, config: dict, version: str) -> bool:
        """保存旧版本配置快照（委托 ConfigMigrator）。

        Args:
            config: 上一次正常加载时记录的插件配置快照。
            version: 该配置快照对应的旧插件版本。

        Returns:
            备份写入并完成轮换时返回 True，否则返回 False。
        """
        tools = getattr(self, "StarTools", StarTools)
        return ConfigMigrator.write_upgrade_config_backup_data(
            config, version, star_tools=tools
        )

    def get_custom_report_template_dir(self, template_name: str) -> Path | None:
        """获取指定报告模板的用户自定义模板目录。"""
        custom_dir = (
            StarTools.get_data_dir(PLUGIN_NAME)
            / "custom_t2i_templates/reporting_templates"
            / template_name
        )
        return custom_dir if custom_dir.is_dir() else None

    def _migrate_daily_comic_characters(self) -> None:
        """迁移旧版漫画参考图配置（委托 ConfigMigrator）。"""
        migrator = getattr(self, "_migrator", None) or ConfigMigrator(
            self, star_tools=getattr(self, "StarTools", StarTools)
        )
        migrator.migrate_daily_comic_character_references()

    def _migrate_daily_comic_character_prompts(self) -> None:
        """将旧版全局分镜提示词复制到既有角色方案（委托 ConfigMigrator）。"""
        migrator = getattr(self, "_migrator", None) or ConfigMigrator(
            self, star_tools=getattr(self, "StarTools", StarTools)
        )
        migrator.migrate_daily_comic_character_prompts()

    def _is_legacy_default_comic_prompt(self, prompt: object) -> bool:
        """判断是否为旧版默认漫画分镜提示词（委托 ConfigMigrator）。"""
        return ConfigMigrator.is_legacy_default_comic_prompt(prompt)

    def _migrate_legacy_comic_storyboard_prompts(self) -> None:
        """自动将旧版默认漫画分镜提示词升级（委托 ConfigMigrator）。"""
        migrator = getattr(self, "_migrator", None) or ConfigMigrator(
            self, star_tools=getattr(self, "StarTools", StarTools)
        )
        migrator.migrate_legacy_comic_storyboard_prompts()

    def _write_comic_config_backup(self, data: dict) -> bool:
        """写入漫画配置迁移备份（委托 ConfigMigrator）。

        Args:
            data: 需要保留的旧版漫画相关配置。

        Returns:
            备份写入是否成功。
        """
        return ConfigMigrator.write_comic_config_backup(data, star_tools=StarTools)

    def _copy_legacy_comic_reference_images(self, references: list[str]) -> list[str]:
        """复制旧参考图到角色模板对应的原生上传目录（委托 ConfigMigrator）。

        Args:
            references: 旧版全局参考图相对路径列表。

        Returns:
            可写入新角色方案的参考图相对路径列表。
        """
        return ConfigMigrator.copy_legacy_comic_reference_images(
            references, star_tools=StarTools
        )

    def _get_group(self, group: str) -> dict:
        """获取指定分组的配置字典，不存在时返回空字典"""
        return self.config.get(group, {})

    def _ensure_group(self, group: str) -> dict:
        """确保指定分组存在并返回其字典引用"""
        if group not in self.config:
            self.config[group] = {}
        return self.config[group]

    def get_group_list_mode(self) -> str:
        """获取群组列表模式 (whitelist/blacklist/none)"""
        return self._get_group("basic").get("group_list_mode", "none")

    def get_group_list(self) -> list[str]:
        """获取群组列表（用于黑白名单）"""
        return self._get_group("basic").get("group_list", [])

    def is_group_allowed(self, group_id_or_umo: str) -> bool:
        """
        根据配置的白/黑名单判断是否允许在该群聊中使用
        支持传入 simple group_id 或 UMO (Unified Message Origin)
        """
        mode = self.get_group_list_mode().lower()
        if mode not in ("whitelist", "blacklist", "none"):
            mode = "none"

        if mode == "none":
            return True

        glist = [str(g).strip() for g in self.get_group_list()]
        target = str(group_id_or_umo).strip()

        is_in_list = any(self._is_group_match(target, item) for item in glist)

        if mode == "whitelist":
            return is_in_list
        if mode == "blacklist":
            return not is_in_list

        return True

    def _is_group_match(self, target: str, item: str) -> bool:
        """
        核心匹配逻辑：判断名单中的 item 是否匹配目标的 target (Unified Message Origin, UMO 或 纯 ID)。
        支持处理 Telegram 话题 (#) 和 独立隔离会话 (_) 的双向穿透匹配。
        """
        if item == target:
            return True

        # 分解目标 UMO 的前缀和 ID 部分 (如 default:GroupMessage:ID)
        if ":" in target:
            target_prefix, target_id = target.rsplit(":", 1)
        else:
            target_prefix, target_id = "", target

        # 生成目标 ID 的所有“穿透”候选 (处理隔离模式和话题)
        candidates = {target_id}
        if "#" in target_id:
            candidates.add(target_id.split("#", 1)[0])
        if "_" in target_id:
            for part in target_id.split("_"):
                candidates.add(part)

        # 检查名单项 (item) 的格式
        if ":" in item:
            i_prefix, i_id = item.rsplit(":", 1)
            # 名单项带前缀时，前缀必须匹配 (如果 target 本身没前缀，则允许作为跨平台通用 ID 匹配)
            if target_prefix and i_prefix != target_prefix:
                return False
        else:
            i_id = item

        # [修复] 名单项 ID 也可能包含复合形式 (如 UserId_GroupId)，需要拆解匹配
        item_variants = {i_id}
        if "#" in i_id:
            item_variants.add(i_id.split("#", 1)[0])
        if "_" in i_id:
            for part in i_id.split("_"):
                item_variants.add(part)

        # 只要两边的 ID “核心部分”存在交集，即视为匹配成功
        return not item_variants.isdisjoint(candidates)

    def get_max_messages(self) -> int:
        """获取最大消息数量"""
        return self._get_group("basic").get("max_messages", 1000)

    def get_analysis_days(self) -> int:
        """获取分析天数"""
        return self._get_group("basic").get("analysis_days", 1)

    def get_enable_runtime_metrics(self) -> bool:
        """获取是否开启全链路性能指标与资源监控。"""
        return self._get_group("basic").get("enable_runtime_metrics", True)

    def get_auto_analysis_time(self) -> list[str]:
        """获取自动分析时间列表"""
        group = self._get_group("auto_analysis")
        val = group.get("auto_analysis_time", ["09:00"])
        # 兼容旧版本字符串配置
        if isinstance(val, str):
            val_list = [val]
            # 自动修复配置格式
            try:
                auto_group = self._ensure_group("auto_analysis")
                auto_group["auto_analysis_time"] = val_list
                self.config.save_config()
                logger.info(f"自动修复配置格式 auto_analysis_time: {val} -> {val_list}")
            except Exception as e:
                logger.warning(f"修复配置格式失败: {e}")
            return val_list
        return val if isinstance(val, list) else ["09:00"]

    def get_enable_auto_analysis(self) -> bool:
        """
        获取是否启用自动分析（兼容旧接口）。

        旧版本使用 auto_analysis.enable_auto_analysis 布尔值；
        新版本改为由 scheduled_group_list_mode + scheduled_group_list 推导。
        """
        return self.is_auto_analysis_enabled()

    def get_output_format(self) -> list[str]:
        """获取输出格式"""
        val = self._get_group("basic").get("output_format", ["image"])
        return val if isinstance(val, list) else [val]

    def get_qq_official_t2i_summary_dashboard_enabled(self) -> bool:
        """是否启用 QQ 官方 T2I 概览图。"""
        group = self._get_group("qq_official")
        if "enable_t2i_summary_dashboard" in group:
            return bool(group["enable_t2i_summary_dashboard"])
        return bool(group.get("enable_t2i_activity_histogram", True))

    def get_min_messages_threshold(self) -> int:
        """获取最小消息阈值"""
        return self._get_group("basic").get("min_messages_threshold", 50)

    def get_topic_analysis_enabled(self) -> bool:
        """获取是否启用话题分析"""
        return self._get_group("analysis_features").get("topic_analysis_enabled", True)

    def get_user_title_analysis_enabled(self) -> bool:
        """获取是否启用用户称号分析"""
        return self._get_group("analysis_features").get(
            "user_title_analysis_enabled", True
        )

    def get_golden_quote_analysis_enabled(self) -> bool:
        """获取是否启用金句分析"""
        return self._get_group("analysis_features").get(
            "golden_quote_analysis_enabled", True
        )

    def get_chat_quality_analysis_enabled(self) -> bool:
        """获取是否启用聊天质量分析"""
        return self._get_group("analysis_features").get(
            "chat_quality_analysis_enabled", False
        )

    def get_max_topics(self) -> int:
        """获取最大话题数量"""
        return self._get_group("analysis_features").get("max_topics", 5)

    def get_max_user_titles(self) -> int:
        """获取最大用户称号数量"""
        return self._get_group("analysis_features").get("max_user_titles", 8)

    def get_max_golden_quotes(self) -> int:
        """获取最大金句数量"""
        return self._get_group("analysis_features").get("max_golden_quotes", 5)

    def get_llm_retries(self) -> int:
        """获取LLM请求重试次数"""
        return self._get_group("llm").get("llm_retries", 2)

    def get_llm_backoff(self) -> int:
        """获取LLM请求重试退避基值（秒），实际退避会乘以尝试次数"""
        return self._get_group("llm").get("llm_backoff", 2)

    def get_enable_streaming_llm_call(self) -> bool:
        """获取是否启用流式 LLM 调用"""
        return self._get_group("llm").get("enable_streaming_llm_call", False)

    def get_enable_base64_image(self) -> bool:
        """获取是否启用 Base64 图片传输"""
        return self._get_group("basic").get("enable_base64_image", False)

    def get_napcat_stream_threshold_mb(self) -> float:
        """获取可触发 NapCat 流式上传兜底的本地图片最小大小。"""
        value = self._get_group("basic").get("napcat_stream_threshold_mb", 2.0)
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def get_t2i_rendering_strategies(self) -> list[dict]:
        """获取用户配置的两轮 T2I 渲染策略"""
        group = self._get_group("t2i_rendering")
        viewport_width = max(1, int(group.get("t2i_viewport_width", 1440)))
        viewport_height = max(1, int(group.get("t2i_viewport_height", 900)))

        return [
            # 第一轮：质量优先
            {
                "full_page": True,
                "type": group.get("t2i_r1_type", "png"),
                "quality": group.get("t2i_r1_quality", 100),
                "device_scale_factor_level": group.get("t2i_r1_device_scale", "ultra"),
                "timeout": group.get("t2i_r1_timeout", 30000),
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
            },
            # 第二轮：稳定性/回退优先
            {
                "full_page": True,
                "type": group.get("t2i_r2_type", "jpeg"),
                "quality": group.get("t2i_r2_quality", 80),
                "device_scale_factor_level": group.get("t2i_r2_device_scale", "normal"),
                "timeout": group.get("t2i_r2_timeout", 60000),
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
            },
        ]

    def get_t2i_font_source(self) -> str:
        """获取 T2I 字体源 (Mainland/Overseas)"""
        return self._get_group("t2i_rendering").get("t2i_font_source", "Overseas")

    def get_t2i_google_fonts_mirror(self) -> str:
        """根据环境选择获取 Google Fonts 镜像地址"""
        source = self.get_t2i_font_source()
        group = self._get_group("t2i_rendering")
        if source == "Mainland":
            return group.get("t2i_mainland_google_fonts", "https://fonts.loli.net")
        return group.get("t2i_overseas_google_fonts", "https://fonts.googleapis.com")

    def get_t2i_gstatic_mirror(self) -> str:
        """根据环境选择获取 Gstatic 镜像地址"""
        source = self.get_t2i_font_source()
        group = self._get_group("t2i_rendering")
        if source == "Mainland":
            return group.get("t2i_mainland_gstatic", "https://gstatic.loli.net")
        return group.get("t2i_overseas_gstatic", "https://fonts.gstatic.com")

    def get_t2i_atri_font_mirror(self) -> str:
        """获取 ATRI 主题字体与静态资源镜像地址"""
        return self._get_group("t2i_rendering").get(
            "t2i_atri_font_mirror",
            DEFAULT_ATRI_ASSETS_CDN_URL,
        )

    def get_llm_provider_id(self) -> str:
        """获取主 LLM Provider ID"""
        return self._get_group("llm").get("llm_provider_id", "")

    def get_topic_provider_id(self) -> str:
        """获取话题分析专用 Provider ID"""
        return self._get_group("llm").get("topic_provider_id", "")

    def get_user_title_provider_id(self) -> str:
        """获取用户称号分析专用 Provider ID"""
        return self._get_group("llm").get("user_title_provider_id", "")

    def get_golden_quote_provider_id(self) -> str:
        """获取金句分析专用 Provider ID"""
        return self._get_group("llm").get("golden_quote_provider_id", "")

    def get_quality_provider_id(self) -> str:
        """获取聊天质量分析专用 Provider ID"""
        return self._get_group("llm").get("quality_provider_id", "")

    def get_drawing_prompt_provider_id(self) -> str:
        """获取画图提示词专用 Provider ID"""
        return self._get_group("llm").get("drawing_prompt_provider_id", "")

    def get_keep_original_persona(self) -> bool:
        """获取是否继承会话原始人格设定"""
        return self._get_group("analysis_features").get("keep_original_persona", False)

    def get_use_plugin_specific_persona(self) -> bool:
        """获取是否强制使用插件指定的人格设定"""
        return self._get_group("analysis_features").get(
            "use_plugin_specific_persona", False
        )

    def get_plugin_specific_persona_id(self) -> str:
        """获取插件指定的全局人格 ID (通过 select_persona 接口选择)"""
        return self._get_group("analysis_features").get(
            "plugin_specific_persona_id", ""
        )

    def get_bot_self_ids(self) -> list:
        """获取机器人自身的 ID 列表 (兼容 bot_qq_ids)"""
        basic = self._get_group("basic")
        ids = basic.get("bot_self_ids", [])
        if not ids:
            ids = basic.get("bot_qq_ids", [])
        return ids

    def get_filter_bot_messages(self) -> bool:
        """获取是否过滤机器人自己的消息。"""
        return self._get_group("basic").get("filter_bot_messages", True)

    def set_filter_bot_messages(self, enabled: bool):
        """设置是否过滤机器人自己的消息。"""
        self._ensure_group("basic")["filter_bot_messages"] = enabled
        self.config.save_config()

    def get_html_output_dir(self) -> str:
        """获取HTML输出目录"""

        default_path = StarTools.get_data_dir(PLUGIN_NAME) / "self_hosted_html_reports"
        val = self._get_group("html").get("html_output_dir")
        return val if val else str(default_path)

    def get_html_base_url(self) -> str:
        """获取HTML外链Base URL"""
        return self._get_group("html").get("html_base_url", "")

    def get_html_only_url(self) -> bool:
        """获取是否仅输出外链而不发送文件本体"""
        return self._get_group("html").get("html_only_url", False)

    def set_html_only_url(self, enabled: bool):
        """设置是否仅输出外链而不发送文件本体"""
        self._ensure_group("html")["html_only_url"] = enabled
        self.config.save_config()

    def get_html_filename_format(self) -> str:
        """获取HTML文件名格式"""
        return self._get_group("html").get(
            "html_filename_format", "群聊分析报告_${group_id}_${date}_${ulid}.html"
        )

    def get_topic_analysis_prompt(self, style: str = "topic_prompt") -> str:
        """获取话题分析提示词模板"""
        prompts_config = self._get_group("prompts").get("topic_analysis_prompts", {})
        prompt = prompts_config.get(style, "")
        if prompt:
            return prompt
        return ""

    def get_user_title_analysis_prompt(self, style: str = "user_title_prompt") -> str:
        """获取用户称号分析提示词模板"""
        prompts_config = self._get_group("prompts").get(
            "user_title_analysis_prompts", {}
        )
        prompt = prompts_config.get(style, "")
        if prompt:
            return prompt
        return ""

    def get_golden_quote_analysis_prompt(
        self, style: str = "golden_quote_v2_prompt"
    ) -> str:
        """获取金句分析提示词模板"""
        prompts_config = self._get_group("prompts").get(
            "golden_quote_analysis_prompts", {}
        )
        prompt = prompts_config.get(style, "")
        if prompt:
            return prompt
        return ""

    def get_quality_analysis_prompt(self, style: str = "quality_v2_prompt") -> str:
        """获取聊天质量分析提示词模板"""
        prompts_config = self._get_group("prompts").get("quality_analysis_prompts", {})
        prompt = prompts_config.get(style, "")
        if prompt:
            return prompt
        return ""

    def set_quality_analysis_prompt(self, prompt: str):
        """设置聊天质量分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "quality_analysis_prompts" not in prompts:
            prompts["quality_analysis_prompts"] = {}
        prompts["quality_analysis_prompts"]["quality_v2_prompt"] = prompt
        self.config.save_config()

    def _upgrade_config_item(self, group: str, key: str, setter_func) -> bool:
        """升级指定配置项的值（委托 ConfigMigrator）。"""
        return self._migrator.upgrade_config_item(group, key, setter_func)

    def upgrade_prompt_templates(self) -> bool:
        """扫描并升级所有可配置的模板（委托 ConfigMigrator）。"""
        return self._migrator.upgrade_prompt_templates()

    def migrate_legacy_configs(self) -> bool:
        """升级旧版配置项的类型/结构（委托 ConfigMigrator）。"""
        return self._migrator.migrate_legacy_configs()

    def get_quality_summary_prompt(self, style: str = "quality_summary_prompt") -> str:
        """获取聊天质量汇总分析提示词模板"""
        prompts_config = self._get_group("prompts").get("quality_analysis_prompts", {})
        prompt = prompts_config.get(style, "")
        if prompt:
            return prompt
        return ""

    def set_topic_analysis_prompt(self, prompt: str):
        """设置话题分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "topic_analysis_prompts" not in prompts:
            prompts["topic_analysis_prompts"] = {}
        prompts["topic_analysis_prompts"]["topic_prompt"] = prompt
        self.config.save_config()

    def set_quality_summary_prompt(self, prompt: str):
        """设置聊天质量汇总分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "quality_analysis_prompts" not in prompts:
            prompts["quality_analysis_prompts"] = {}
        prompts["quality_analysis_prompts"]["quality_summary_prompt"] = prompt
        self.config.save_config()

    def set_user_title_analysis_prompt(self, prompt: str):
        """设置用户称号分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "user_title_analysis_prompts" not in prompts:
            prompts["user_title_analysis_prompts"] = {}
        prompts["user_title_analysis_prompts"]["user_title_prompt"] = prompt
        self.config.save_config()

    def set_golden_quote_analysis_prompt(self, prompt: str):
        """设置金句分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "golden_quote_analysis_prompts" not in prompts:
            prompts["golden_quote_analysis_prompts"] = {}
        prompts["golden_quote_analysis_prompts"]["golden_quote_v2_prompt"] = prompt
        self.config.save_config()

    def set_comic_storyboard_prompt(self, prompt: str):
        """设置漫画场景分析提示词模板"""
        prompts = self._ensure_group("prompts")
        if "comic_analysis_prompts" not in prompts:
            prompts["comic_analysis_prompts"] = {}
        prompts["comic_analysis_prompts"]["comic_storyboard_prompt"] = prompt
        self.config.save_config()

    def set_output_format(self, format_types: str | list[str]):
        """设置输出格式"""
        if isinstance(format_types, str):
            format_types = [
                f.strip() for f in format_types.replace("，", ",").split(",")
            ]
        for f in format_types:
            if f not in ("image", "text", "html"):
                raise ValueError(f"无效格式: {f}。有效: image, text, html")

        self._ensure_group("basic")["output_format"] = format_types
        self.config.save_config()

    def set_group_list_mode(self, mode: str):
        """设置群组列表模式"""
        self._ensure_group("basic")["group_list_mode"] = mode
        self.config.save_config()

    def set_group_list(self, groups: list[str]):
        """设置群组列表"""
        self._ensure_group("basic")["group_list"] = groups
        self.config.save_config()

    def get_max_concurrent_tasks(self) -> int:
        """获取自动分析最大并发群数"""
        return self._get_group("performance").get("max_concurrent_groups", 3)

    def get_llm_max_concurrent(self) -> int:
        """获取全局 LLM 最大并发请求数"""
        return self._get_group("performance").get("max_concurrent_llm", 3)

    def get_t2i_max_concurrent(self) -> int:
        """获取全局图片渲染（T2I）最大并发数"""
        return self._get_group("performance").get("max_concurrent_t2i", 1)

    def get_stagger_seconds(self) -> int:
        """获取多群分析任务启动时的交错间隔（秒）"""
        return self._get_group("performance").get("stagger_seconds", 2)

    def set_max_concurrent_tasks(self, count: int):
        """设置自动分析最大并发数"""
        self._ensure_group("performance")["max_concurrent_groups"] = count
        self.config.save_config()

    def set_max_messages(self, count: int):
        """设置最大消息数量"""
        self._ensure_group("basic")["max_messages"] = count
        self.config.save_config()

    def set_analysis_days(self, days: int):
        """设置分析天数"""
        self._ensure_group("basic")["analysis_days"] = days
        self.config.save_config()

    def set_auto_analysis_time(self, time_val: str | list[str]):
        """设置自动分析时间点"""
        self._ensure_group("auto_analysis")["auto_analysis_time"] = time_val
        self.config.save_config()

    def is_auto_analysis_enabled(self) -> bool:
        """
        判断自动分析功能是否通过名单“按需开启”。
        inherit 模式会继承基础群权限的开启状态；其他模式沿用自身名单判断。
        """
        mode = self.get_scheduled_group_list_mode()
        if mode == "inherit":
            basic_mode = self.get_group_list_mode().lower()
            if basic_mode == "whitelist":
                return bool(self.get_group_list())
            return True

        lst = self.get_scheduled_group_list()
        return (mode == "whitelist" and len(lst) > 0) or (mode == "blacklist")

    def get_scheduled_group_list_mode(self) -> str:
        """获取定时分析名单模式 (inherit/whitelist/blacklist)。"""
        mode = str(
            self._get_group("auto_analysis").get(
                "scheduled_group_list_mode", "whitelist"
            )
        ).lower()
        if mode not in ("inherit", "whitelist", "blacklist"):
            return "whitelist"
        return mode

    def set_scheduled_group_list_mode(self, mode: str):
        """设置定时分析名单模式"""
        self._ensure_group("auto_analysis")["scheduled_group_list_mode"] = mode
        self.config.save_config()

    def get_scheduled_group_list(self) -> list[str]:
        """获取定时分析目标群列表"""
        return self._get_group("auto_analysis").get("scheduled_group_list", [])

    def set_scheduled_group_list(self, groups: list[str]):
        """设置定时分析目标群列表"""
        self._ensure_group("auto_analysis")["scheduled_group_list"] = groups
        self.config.save_config()

    def is_scheduled_group_allowed(self, group_umo_or_id: str) -> bool:
        """判断当前群是否允许参与定时分析。

        Args:
            group_umo_or_id: 要检查的完整 UMO 或纯群号。

        Returns:
            当前群是否同时通过基础群权限和定时分析名单。
        """
        if not self.is_group_allowed(group_umo_or_id):
            return False

        mode = self.get_scheduled_group_list_mode()
        if mode == "inherit":
            return True
        return self.is_group_in_filtered_list(
            group_umo_or_id, mode, self.get_scheduled_group_list()
        )

    def is_group_in_filtered_list(
        self, group_umo_or_id: str, mode: str, group_list: list
    ) -> bool:
        """
        通用的名单判定逻辑。

        逻辑如下：
        - whitelist 模式：
            - 如果列表为空，则视为“此级别未开启”。
            - 如果不为空，仅在列表中的通过。
        - blacklist 模式：
            - 在列表中的不通过。
            - 如果列表为空，则全部通过。
        """
        group_list = [str(x).strip() for x in group_list]
        target = str(group_umo_or_id).strip()

        if mode == "whitelist":
            if not group_list:
                # 白名单为空：此级别不开启 (按需开启逻辑)
                return False
            return any(self._is_group_match(target, item) for item in group_list)
        else:  # blacklist
            if not group_list:
                # 黑名单为空：全通过
                return True
            return not any(self._is_group_match(target, item) for item in group_list)

    def set_min_messages_threshold(self, threshold: int):
        """设置最小消息阈值"""
        self._ensure_group("basic")["min_messages_threshold"] = threshold
        self.config.save_config()

    def set_topic_analysis_enabled(self, enabled: bool):
        """设置是否启用话题分析"""
        self._ensure_group("analysis_features")["topic_analysis_enabled"] = enabled
        self.config.save_config()

    def set_user_title_analysis_enabled(self, enabled: bool):
        """设置是否启用用户称号分析"""
        self._ensure_group("analysis_features")["user_title_analysis_enabled"] = enabled
        self.config.save_config()

    def set_golden_quote_analysis_enabled(self, enabled: bool):
        """设置是否启用金句分析"""
        self._ensure_group("analysis_features")["golden_quote_analysis_enabled"] = (
            enabled
        )
        self.config.save_config()

    def set_chat_quality_analysis_enabled(self, enabled: bool):
        """设置是否启用聊天质量分析"""
        self._ensure_group("analysis_features")["chat_quality_analysis_enabled"] = (
            enabled
        )
        self.config.save_config()

    def set_max_topics(self, count: int):
        """设置最大话题数量"""
        self._ensure_group("analysis_features")["max_topics"] = count
        self.config.save_config()

    def set_max_user_titles(self, count: int):
        """设置最大用户称号数量"""
        self._ensure_group("analysis_features")["max_user_titles"] = count
        self.config.save_config()

    def set_max_golden_quotes(self, count: int):
        """设置最大金句数量"""
        self._ensure_group("analysis_features")["max_golden_quotes"] = count
        self.config.save_config()

    def set_html_filename_format(self, format_str: str):
        """设置HTML文件名格式"""
        self._ensure_group("html")["html_filename_format"] = format_str
        self.config.save_config()

    def get_report_template(self) -> str:
        """获取报告模板名称"""
        val = self._get_group("basic").get("report_template")
        if not val and isinstance(self.config, dict):
            val = self.config.get("report_template")
        return str(val).strip() if val else "scrapbook"

    def set_report_template(self, template_name: str):
        """设置报告模板名称"""
        self._ensure_group("basic")["report_template"] = template_name
        self.config.save_config()

    def get_enable_user_card(self) -> bool:
        """获取是否使用用户群名片"""
        return self._get_group("basic").get("enable_user_card", False)

    def get_enable_analysis_reply(self) -> bool:
        """获取是否在群分析完成后发送文本回复"""
        return self._get_group("basic").get("enable_analysis_reply", False)

    def set_enable_analysis_reply(self, enabled: bool):
        """设置是否在群分析完成后发送文本回复"""
        self._ensure_group("basic")["enable_analysis_reply"] = enabled
        self.config.save_config()

    def get_show_report_caption(self) -> bool:
        """获取是否发送 \"📊 每日群聊分析报告已生成\" 前缀文字。"""
        return self._get_group("basic").get("show_report_caption", True)

    def set_show_report_caption(self, enabled: bool):
        """设置是否发送 \"📊 每日群聊分析报告已生成\" 前缀文字。"""
        self._ensure_group("basic")["show_report_caption"] = enabled
        self.config.save_config()

    def get_profile_display_mode(self) -> str:
        """获取人格标签展示模式。"""
        mode = str(self._get_group("basic").get("profile_display_mode", "mbti")).lower()
        if mode not in {"mbti", "sbti", "acgti"}:
            return "mbti"
        return mode

    def get_profile_image_opacity(self) -> float:
        """获取人格背景图透明度。"""
        value = self._get_group("basic").get("profile_image_opacity", 0.12)
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.12

    def get_profile_image_size_mode(self) -> str:
        """获取人格背景图尺寸模式。"""
        mode = str(
            self._get_group("basic").get("profile_image_size_mode", "contain")
        ).lower()
        if mode not in {"contain", "cover"}:
            return "contain"
        return mode

    def get_profile_mapping_config(self) -> str:
        """获取人格映射配置(JSON 文本)。"""
        return str(self._get_group("basic").get("profile_mapping_config", "")).strip()

    # ========== 群文件/群相册上传配置 ==========

    def get_enable_group_file_upload(self) -> bool:
        """获取是否启用群文件上传"""
        return self._get_group("qq_group_upload").get("enable_group_file_upload", False)

    def get_group_file_folder(self) -> str:
        """获取群文件上传目录名，空字符串表示根目录"""
        return self._get_group("qq_group_upload").get("group_file_folder", "")

    def get_enable_group_album_upload(self) -> bool:
        """获取是否启用群相册上传（仅 NapCat）"""
        return self._get_group("qq_group_upload").get(
            "enable_group_album_upload", False
        )

    def get_group_album_name(self) -> str:
        """获取目标群相册名称，空字符串表示默认相册"""
        return self._get_group("qq_group_upload").get("group_album_name", "")

    def get_group_album_strict_mode(self) -> bool:
        """获取群相册上传严格模式开关。"""
        return bool(
            self._get_group("qq_group_upload").get("group_album_strict_mode", True)
        )

    def set_group_album_strict_mode(self, enabled: bool):
        """设置群相册上传严格模式"""
        self._ensure_group("qq_group_upload")["group_album_strict_mode"] = enabled
        self.config.save_config()

    # ========== 增量分析配置 ==========

    def get_incremental_enabled(self) -> bool:
        """获取是否开启了增量分析（由名单状态决定）"""
        mode = self.get_incremental_group_list_mode()
        if mode == "inherit":
            return self.is_auto_analysis_enabled()

        lst = self.get_incremental_group_list()
        # 如果是白名单且不为空，或者是黑名单模式，则视为功能“开启”
        return (mode == "whitelist" and len(lst) > 0) or (mode == "blacklist")

    def get_incremental_group_list_mode(self) -> str:
        """获取增量分析名单模式 (inherit/whitelist/blacklist)。"""
        mode = str(
            self._get_group("incremental").get(
                "incremental_group_list_mode", "whitelist"
            )
        ).lower()
        if mode not in ("inherit", "whitelist", "blacklist"):
            return "whitelist"
        return mode

    def get_incremental_group_list(self) -> list[str]:
        """获取增量分析群列表"""
        return self._get_group("incremental").get("incremental_group_list", [])

    def is_incremental_group_allowed(self, group_umo_or_id: str) -> bool:
        """判断当前群是否应使用增量分析。

        Args:
            group_umo_or_id: 要检查的完整 UMO 或纯群号。

        Returns:
            当前群是否通过基础、定时和增量三级名单。
        """
        if not self.is_scheduled_group_allowed(group_umo_or_id):
            return False

        mode = self.get_incremental_group_list_mode()
        if mode == "inherit":
            return True
        return self.is_group_in_filtered_list(
            group_umo_or_id, mode, self.get_incremental_group_list()
        )

    def get_incremental_fallback_enabled(self) -> bool:
        """获取增量分析失败回退到全量分析的开关（默认启用）"""
        return self._get_group("incremental").get("incremental_fallback_enabled", True)

    def get_incremental_report_immediately(self) -> bool:
        """获取是否启用增量分析立即发送报告（调试用）"""
        return self._get_group("incremental").get(
            "incremental_report_immediately", False
        )

    def set_incremental_report_immediately(self, enabled: bool):
        """设置增量分析是否立即发送报告"""
        self._ensure_group("incremental")["incremental_report_immediately"] = enabled
        self.config.save_config()

    def get_incremental_min_messages(self) -> int:
        """获取触发增量分析的最小消息数阈值"""
        value = self._get_group("incremental").get("incremental_min_messages", 300)
        return max(1, int(value))

    def get_incremental_topics_per_batch(self) -> int:
        """获取单次增量分析提取的最大话题数"""
        return self._get_group("incremental").get("incremental_topics_per_batch", 3)

    def get_incremental_quotes_per_batch(self) -> int:
        """获取单次增量分析提取的最大金句数"""
        return self._get_group("incremental").get("incremental_quotes_per_batch", 3)

    # ========== 每日群漫画配置 ==========

    def get_enable_daily_comic(self) -> bool:
        """获取漫画功能总开关。"""
        return self._get_group("daily_comic").get("enable_daily_comic", False)

    def get_enable_auto_daily_comic(self) -> bool:
        """获取是否在分析完成后自动生成漫画。"""
        return self._get_group("daily_comic").get("enable_auto_daily_comic", True)

    def get_comic_group_list_mode(self) -> str:
        """获取漫画生成名单模式。

        Returns:
            规范化后的漫画名单模式。默认 inherit，表示继承基础群权限，
            避免同一批群需要在多个配置里重复填写。
        """
        mode = str(
            self._get_group("daily_comic").get("comic_group_list_mode", "inherit")
        ).lower()
        if mode not in ("inherit", "whitelist", "blacklist"):
            return "inherit"
        return mode

    def get_comic_group_list(self) -> list[str]:
        """获取漫画生成白/黑名单列表。

        Returns:
            配置的群 UMO 或纯群号列表。配置格式异常时按空列表处理。
        """
        group_list = self._get_group("daily_comic").get("comic_group_list", [])
        if not isinstance(group_list, list):
            return []
        return group_list

    def is_comic_group_allowed(
        self, group_umo_or_id: str, inherit_allowed: bool | None = None
    ) -> bool:
        """判断当前群是否允许生成漫画。

        Args:
            group_umo_or_id: 要检查的完整 UMO 或纯群号。
            inherit_allowed: 上游入口已完成权限判断时传入其结果。自动报告
                漫画会传入 True，避免重复读取基础/定时/增量名单；手动漫画
                不传入时会按基础群权限实时判断。

        Returns:
            当前群是否允许生成漫画。
        """
        mode = self.get_comic_group_list_mode()
        if mode == "inherit":
            if inherit_allowed is not None:
                return bool(inherit_allowed)
            return self.is_group_allowed(group_umo_or_id)

        return self.is_group_in_filtered_list(
            group_umo_or_id,
            mode,
            self.get_comic_group_list(),
        )

    def get_drawing_backend(self) -> str:
        """获取漫画绘图后端 (builtin/general_plugin/big_banana)。"""
        group = self._get_group("daily_comic")
        return str(group.get("drawing_backend", "builtin")).strip() or "builtin"

    def get_drawing_external_fallback(self) -> bool:
        """外部绘图后端失败时是否回退内置后端。"""
        return bool(
            self._get_group("daily_comic").get("drawing_external_fallback", True)
        )

    def get_drawing_provider_configs(self) -> list[dict]:
        """获取按优先级排序的已启用绘图供应商候选。

        空条目或格式错误的条目会被忽略。绘图供应商配置表是唯一的连接配置
        来源；没有有效候选时，调用方会返回明确的未配置错误。

        Returns:
            已启用供应商的配置字典列表。
        """
        providers = self._get_group("daily_comic").get("drawing_provider_overrides", [])
        if not isinstance(providers, list):
            return []

        template_protocols = {
            "google": "google",
            "openai": "chat",
            "zai": "chat",
            "grok2api": "grok",
            "agnes_ai": "agnes_ai",
            "agnes_ai_china": "agnes_ai",
            "xai": "xai",
            "minimax": "minimax",
            "stepfun": "stepfun",
            "openai_images": "images",
            "doubao": "doubao",
            "sensenova": "sensenova",
            "dashscope": "dashscope",
        }
        valid_protocols = {"images", "chat", "grok", "gemini", *template_protocols}
        candidates = []
        for index, provider in enumerate(providers):
            if not isinstance(provider, dict) or not provider.get("enable", True):
                continue
            template_key = str(provider.get("__template_key", "")).strip().lower()
            name_val = str(provider.get("name", "")).strip().lower()
            endpoint_mode = str(provider.get("endpoint_mode", "")).strip().lower()
            api_url_val = str(provider.get("api_url", "")).strip().lower()
            model_val = str(provider.get("model", "")).strip().lower()

            inferred_key = template_key or name_val or endpoint_mode
            if inferred_key not in template_protocols:
                if (
                    "dashscope" in api_url_val
                    or "aliyuncs.com" in api_url_val
                    or "qwen" in model_val
                    or "wan" in model_val
                ):
                    inferred_key = "dashscope"
                elif (
                    "generativelanguage.googleapis.com" in api_url_val
                    or "gemini" in model_val
                ):
                    inferred_key = "google"
                elif "sensenova" in api_url_val or "sensechat" in model_val:
                    inferred_key = "sensenova"
                elif "x.ai" in api_url_val or "grok" in model_val:
                    inferred_key = "xai"
                elif "minimax" in api_url_val or "image-01" in model_val:
                    inferred_key = "minimax"
                elif "stepfun" in api_url_val or "step-" in model_val:
                    inferred_key = "stepfun"
                elif "doubao" in api_url_val or "volces.com" in api_url_val:
                    inferred_key = "doubao"
                elif "api_protocol" in provider:
                    inferred_key = str(provider["api_protocol"]).strip().lower()

            protocol = template_protocols.get(
                inferred_key, str(provider.get("api_protocol", "images")).strip()
            )
            api_key = str(provider.get("api_key", "")).strip()
            if protocol not in valid_protocols or not api_key:
                logger.warning("跳过索引 %s 处无效的漫画绘图供应商配置", index)
                continue
            candidate = provider.copy()
            candidate["api_protocol"] = protocol
            candidate["__template_key"] = inferred_key or template_key or "images"
            candidate["api_key"] = api_key
            candidate["_index"] = index
            try:
                candidate["_priority"] = int(provider.get("priority", 0))
            except (TypeError, ValueError):
                candidate["_priority"] = 0
            candidates.append(candidate)

        return sorted(
            candidates,
            key=lambda item: (-item["_priority"], item["_index"]),
        )

    def get_drawing_output_exception_retries(self) -> int:
        group = self._get_group("daily_comic")
        return int(group.get("drawing_output_exception_retries", 3))

    def get_drawing_output_exception_retry_keywords(self) -> list[str]:
        group = self._get_group("daily_comic")
        keywords = group.get("drawing_output_exception_retry_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        return [str(k) for k in keywords if str(k).strip()]

    def get_drawing_retry_delay(self) -> int:
        group = self._get_group("daily_comic")
        return int(group.get("drawing_retry_delay", 2))

    def get_drawing_network_retries(self) -> int:
        group = self._get_group("daily_comic")
        return int(group.get("drawing_network_retries", 2))

    def get_drawing_download_proxy(self) -> str:
        group = self._get_group("daily_comic")
        return group.get("drawing_download_proxy", "").strip()

    def get_drawing_proxy(self) -> str:
        """获取漫画生图 API 的全局代理地址。"""
        return str(self._get_group("daily_comic").get("drawing_proxy", "")).strip()

    def get_enable_comic_album_upload(self) -> bool:
        group = self._get_group("qq_group_upload")
        return bool(group.get("enable_comic_album_upload", False))

    def get_comic_album_name(self) -> str:
        return str(
            self._get_group("qq_group_upload").get("comic_album_name", "daily_analysis")
        ).strip()

    def get_drawing_reference_image(self) -> str:
        """获取当前选中的漫画参考图相对路径。

        Returns:
            当前角色方案最后添加的参考图；未配置角色方案时兼容旧版字段。
        """
        character = self.get_selected_comic_character()
        reference_images = (
            character.get("reference_images", [])
            if character
            else self._get_group("daily_comic").get("drawing_reference_image", [])
        )
        if isinstance(reference_images, str):
            reference_images = [reference_images]
        if not isinstance(reference_images, list):
            return ""
        for reference_image in reversed(reference_images):
            if isinstance(reference_image, str) and reference_image.strip():
                return reference_image.strip()
        return ""

    def get_drawing_reference_images(self) -> list[str]:
        """Get every valid reference image for the selected comic character.

        Returns:
            Relative image paths in their configured order.
        """
        character = self.get_selected_comic_character()
        reference_images = (
            character.get("reference_images", [])
            if character
            else self._get_group("daily_comic").get("drawing_reference_image", [])
        )
        if isinstance(reference_images, str):
            reference_images = [reference_images]
        if not isinstance(reference_images, list):
            return []
        return [
            reference_image.strip()
            for reference_image in reference_images
            if isinstance(reference_image, str) and reference_image.strip()
        ]

    def get_selected_comic_character(self) -> dict | None:
        """获取本次漫画应使用的角色方案。

        开启随机后，同一运行环境自然日内固定选择同一个已启用方案；关闭时始终使用
        第一个已启用方案。角色列表为空时返回 None，调用方将回退到既有文生图行为。

        Returns:
            角色方案配置；没有可用方案时返回 None。
        """
        characters = self._get_group("daily_comic").get("comic_characters", [])
        enabled_characters = (
            [
                character
                for character in characters
                if isinstance(character, dict) and character.get("enable", True)
            ]
            if isinstance(characters, list)
            else []
        )
        if not enabled_characters:
            return None

        if not self._get_group("daily_comic").get(
            "random_daily_comic_character", False
        ):
            return enabled_characters[0]

        timezone_name = os.environ.get("TZ", "").strip()
        if timezone_name:
            try:
                current_time = datetime.now(ZoneInfo(timezone_name))
            except ZoneInfoNotFoundError:
                logger.warning(
                    f"环境变量 TZ={timezone_name!r} 不是有效 IANA 时区，"
                    "每日漫画角色将使用系统本地时区。"
                )
                current_time = datetime.now().astimezone()
        else:
            current_time = datetime.now().astimezone()
        today = current_time.date().isoformat()
        state_path = self._get_comic_character_state_path()
        state = self._read_comic_character_state(state_path)
        selected_character = state.get("selected_character")
        if state.get("date") == today and selected_character in enabled_characters:
            return selected_character

        selected_character = random.choice(enabled_characters)
        self._save_comic_character_state(
            state_path,
            {"date": today, "selected_character": selected_character},
        )
        character_name = str(selected_character.get("name", "")).strip() or "未命名方案"
        logger.info(f"今日漫画角色已随机选择: {character_name}")
        return selected_character

    def get_comic_character_persona_id(self, character: dict | None) -> str:
        """获取角色方案绑定的漫画专用人格 ID。

        Args:
            character: 当前选中的角色方案。

        Returns:
            人格 ID；未配置时为空字符串。
        """
        if not isinstance(character, dict):
            return ""
        return str(character.get("persona_id", "")).strip()

    def get_comic_character_storyboard_prompt(self, character: dict | None) -> str:
        """获取角色专属分镜提示词，未配置时回退全局默认模板。

        Args:
            character: 当前选中的角色方案。

        Returns:
            本次漫画分镜应使用的提示词模板。
        """
        if isinstance(character, dict):
            prompt = str(character.get("storyboard_prompt", "")).strip()
            if prompt:
                return prompt
        return self.get_comic_storyboard_prompt()

    @staticmethod
    def _get_comic_character_state_path() -> Path:
        """获取每日随机角色状态文件路径。"""
        return StarTools.get_data_dir(PLUGIN_NAME) / "comic_character_daily_state.json"

    @staticmethod
    def _read_comic_character_state(state_path: Path) -> dict:
        """读取每日随机角色状态。

        Args:
            state_path: 状态文件路径。

        Returns:
            可用状态字典；文件不存在或无效时返回空字典。
        """
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _save_comic_character_state(state_path: Path, state: dict) -> None:
        """原子写入每日随机角色状态。

        Args:
            state_path: 状态文件路径。
            state: 待保存状态。
        """
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = state_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            temporary_path.replace(state_path)
        except OSError as exc:
            logger.warning(f"保存每日漫画角色选择失败: {exc}")

    def get_comic_storyboard_prompt(
        self, style: str = "comic_storyboard_prompt"
    ) -> str:
        """获取分镜生成提示词模板"""
        prompts_config = self._get_group("prompts").get("comic_analysis_prompts", {})
        return prompts_config.get(style, "")

    def save_config(self):
        """保存配置到AstrBot配置系统"""
        try:
            self.config.save_config()
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def reload_config(self):
        """重新加载配置"""
        try:
            logger.info("重新加载配置...")
            logger.info("配置重载完成")
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
