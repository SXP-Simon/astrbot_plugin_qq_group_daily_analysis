"""
配置管理模块 - 基础设施层
负责处理插件配置和PDF依赖检查
"""

import sys

from astrbot.api import AstrBotConfig
from astrbot.api.star import StarTools

from ...utils.logger import logger
from ..utils.template_utils import upgrade_str_format_template


class ConfigManager:
    """配置管理器

    配置结构采用分组嵌套方式，顶层分为以下分组：
    - basic: 基础设置
    - auto_analysis: 自动分析设置
    - llm: LLM 设置
    - analysis_features: 分析功能开关
    - incremental: 增量分析设置
    - pdf: PDF 设置
    - prompts: 提示词模板
    """

    def __init__(self, config: AstrBotConfig):
        self.config = config
        self._playwright_available = False
        self._playwright_version = None
        self._check_playwright_availability()

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

        glist = [str(g) for g in self.get_group_list()]
        target = str(group_id_or_umo)

        target_simple_id = target.split(":")[-1] if ":" in target else target
        target_parent_id = (
            target_simple_id.split("#", 1)[0]
            if "#" in target_simple_id
            else target_simple_id
        )

        def _is_match(
            item: str,
            target: str,
            target_simple_id: str,
            target_parent_id: str,
        ) -> bool:
            if ":" in item:
                if item == target:
                    return True

                # 允许 Telegram 话题会话通过“父 UMO”命中，
                # 例如: item=telegram2:GroupMessage:-1001
                #      target=telegram2:GroupMessage:-1001#2264
                if "#" in target_simple_id:
                    if ":" not in target:
                        return False
                    item_prefix, item_tail = item.rsplit(":", 1)
                    target_prefix, _ = target.rsplit(":", 1)
                    return (
                        item_prefix == target_prefix and item_tail == target_parent_id
                    )
                return False
            if item == target_simple_id:
                return True
            # 允许 Telegram 话题会话通过父群 ID 命中简单群号白/黑名单
            return "#" in target_simple_id and item == target_parent_id

        is_in_list = any(
            _is_match(item, target, target_simple_id, target_parent_id)
            for item in glist
        )

        if mode == "whitelist":
            return is_in_list
        if mode == "blacklist":
            return not is_in_list

        return True

    def get_max_messages(self) -> int:
        """获取最大消息数量"""
        return self._get_group("basic").get("max_messages", 1000)

    def get_analysis_days(self) -> int:
        """获取分析天数"""
        return self._get_group("basic").get("analysis_days", 1)

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

    def get_output_format(self) -> str:
        """获取输出格式"""
        return self._get_group("basic").get("output_format", "image")

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

    def get_debug_mode(self) -> bool:
        """获取是否启用调试模式"""
        return self._get_group("basic").get("debug_mode", False)

    def get_enable_base64_image(self) -> bool:
        """获取是否启用 Base64 图片传输"""
        return self._get_group("basic").get("enable_base64_image", False)

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

    def get_keep_original_persona(self) -> bool:
        """获取是否保持原始人格设定"""
        return self._get_group("analysis_features").get("keep_original_persona", False)

    def get_pdf_output_dir(self) -> str:
        """获取PDF输出目录"""
        from pathlib import Path

        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        try:
            default_path = StarTools.get_data_dir() / "reports"
            val = self._get_group("pdf").get("pdf_output_dir")
            return val if val else str(default_path)
        except Exception:
            val = self._get_group("pdf").get("pdf_output_dir")
            fallback_path = (
                Path(get_astrbot_data_path())
                / "plugin_data"
                / "astrbot_plugin_qq_group_daily_analysis"
                / "reports"
            )
            return val if val else str(fallback_path)

    def get_bot_self_ids(self) -> list:
        """获取机器人自身的 ID 列表 (兼容 bot_qq_ids)"""
        basic = self._get_group("basic")
        ids = basic.get("bot_self_ids", [])
        if not ids:
            ids = basic.get("bot_qq_ids", [])
        return ids

    def get_pdf_filename_format(self) -> str:
        """获取PDF文件名格式"""
        return self._get_group("pdf").get(
            "pdf_filename_format", "群聊分析报告_{group_id}_{date}.pdf"
        )

    def get_html_output_dir(self) -> str:
        """获取HTML输出目录"""
        from pathlib import Path

        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        try:
            default_path = StarTools.get_data_dir() / "self_hosted_html_reports"
            val = self._get_group("html").get("html_output_dir")
            return val if val else str(default_path)
        except Exception:
            val = self._get_group("html").get("html_output_dir")
            fallback_path = (
                Path(get_astrbot_data_path())
                / "plugin_data"
                / "astrbot_plugin_qq_group_daily_analysis"
                / "self_hosted_html_reports"
            )
            return val if val else str(fallback_path)

    def get_html_base_url(self) -> str:
        """获取HTML外链Base URL"""
        return self._get_group("html").get("html_base_url", "")

    def get_html_filename_format(self) -> str:
        """获取HTML文件名格式"""
        return self._get_group("html").get(
            "html_filename_format", "群聊分析报告_{group_id}_{date}.html"
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

    def _upgrade_config_item(self, group: str, key: str, setter_func):
        """升级指定配置项的值（从 str.format -> string.Template），并回写。"""
        # 如果是 prompts，则先取 prompts 分组，再取子分组 (group)
        if group in (
            "quality_analysis_prompts",
            "topic_analysis_prompts",
            "user_title_analysis_prompts",
            "golden_quote_analysis_prompts",
        ):
            target_group = self._get_group("prompts").get(group, {})
        else:
            target_group = self._get_group(group)

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

    def upgrade_prompt_templates(self):
        """启动时调用，扫描并升级所有可配置的模板（含 prompt 和文件名）。"""
        modified = False
        # 1. 提示词模板升级
        modified |= self._upgrade_config_item(
            "quality_analysis_prompts",
            "quality_v2_prompt",
            self.set_quality_analysis_prompt,
        )
        modified |= self._upgrade_config_item(
            "quality_analysis_prompts",
            "quality_summary_prompt",
            self.set_quality_summary_prompt,
        )
        modified |= self._upgrade_config_item(
            "topic_analysis_prompts",
            "topic_prompt",
            self.set_topic_analysis_prompt,
        )
        modified |= self._upgrade_config_item(
            "user_title_analysis_prompts",
            "user_title_prompt",
            self.set_user_title_analysis_prompt,
        )
        modified |= self._upgrade_config_item(
            "golden_quote_analysis_prompts",
            "golden_quote_v2_prompt",
            self.set_golden_quote_analysis_prompt,
        )

        # 2. 文件名格式升级
        modified |= self._upgrade_config_item(
            "pdf",
            "pdf_filename_format",
            self.set_pdf_filename_format,
        )
        modified |= self._upgrade_config_item(
            "html",
            "html_filename_format",
            self.set_html_filename_format,
        )

        if modified:
            logger.info(
                "已完成所有配置模板从 str.format 到 string.Template 的安全迁移。（已自动回写配置）"
            )
        return modified

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

    def set_output_format(self, format_type: str):
        """设置输出格式"""
        self._ensure_group("basic")["output_format"] = format_type
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
        逻辑：如果是白名单模式且名单不为空，或者为黑名单模式，则视为开启。
        """
        mode = self.get_scheduled_group_list_mode()
        lst = self.get_scheduled_group_list()
        return (mode == "whitelist" and len(lst) > 0) or (mode == "blacklist")

    def get_scheduled_group_list_mode(self) -> str:
        """获取定时分析名单模式 (whitelist/blacklist)"""
        return self._get_group("auto_analysis").get(
            "scheduled_group_list_mode", "whitelist"
        )

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

        # 兼容 UMO 匹配 (如果列表里写的是 ID，UMO 也能匹配上)
        def match_umo(umo: str, item: str) -> bool:
            if umo == item:
                return True
            if ":" in umo and umo.split(":")[-1] == item:
                return True
            return False

        if mode == "whitelist":
            if not group_list:
                # 白名单为空：此级别不开启 (按需开启逻辑)
                return False
            return any(match_umo(target, x) for x in group_list)
        else:  # blacklist
            if not group_list:
                # 黑名单为空：全通过
                return True
            return not any(match_umo(target, x) for x in group_list)

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

    def set_pdf_output_dir(self, directory: str):
        """设置PDF输出目录"""
        self._ensure_group("pdf")["pdf_output_dir"] = directory
        self.config.save_config()

    def set_pdf_filename_format(self, format_str: str):
        """设置PDF文件名格式"""
        self._ensure_group("pdf")["pdf_filename_format"] = format_str
        self.config.save_config()

    def set_html_filename_format(self, format_str: str):
        """设置HTML文件名格式"""
        self._ensure_group("html")["html_filename_format"] = format_str
        self.config.save_config()

    def get_report_template(self) -> str:
        """获取报告模板名称"""
        return self._get_group("basic").get("report_template", "scrapbook")

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
        lst = self.get_incremental_group_list()
        # 如果是白名单且不为空，或者是黑名单模式，则视为功能“开启”
        return (mode == "whitelist" and len(lst) > 0) or (mode == "blacklist")

    def get_incremental_group_list_mode(self) -> str:
        """获取增量分析名单模式 (whitelist/blacklist)"""
        return self._get_group("incremental").get(
            "incremental_group_list_mode", "whitelist"
        )

    def get_incremental_group_list(self) -> list[str]:
        """获取增量分析群列表"""
        return self._get_group("incremental").get("incremental_group_list", [])

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

    def get_incremental_interval_minutes(self) -> int:
        """获取增量分析间隔（分钟）"""
        return self._get_group("incremental").get("incremental_interval_minutes", 120)

    def get_incremental_max_daily_analyses(self) -> int:
        """获取每天最大增量分析次数"""
        return self._get_group("incremental").get("incremental_max_daily_analyses", 8)

    def get_incremental_safe_limit(self) -> int:
        """获取单次增量分析的安全分析/同步上限 (Safe Count)"""
        return self._get_group("incremental").get("incremental_safe_limit", 2000)

    def get_incremental_min_messages(self) -> int:
        """获取触发增量分析的最小消息数阈值"""
        return self._get_group("incremental").get("incremental_min_messages", 20)

    def get_incremental_topics_per_batch(self) -> int:
        """获取单次增量分析提取的最大话题数"""
        return self._get_group("incremental").get("incremental_topics_per_batch", 3)

    def get_incremental_quotes_per_batch(self) -> int:
        """获取单次增量分析提取的最大金句数"""
        return self._get_group("incremental").get("incremental_quotes_per_batch", 3)

    def get_incremental_active_start_hour(self) -> int:
        """获取增量分析活跃时段起始小时（24小时制）"""
        return self._get_group("incremental").get("incremental_active_start_hour", 8)

    def get_incremental_active_end_hour(self) -> int:
        """获取增量分析活跃时段结束小时（24小时制）"""
        return self._get_group("incremental").get("incremental_active_end_hour", 23)

    def get_incremental_stagger_seconds(self) -> int:
        """获取多群增量分析的交错间隔（秒），避免 API 压力"""
        return self._get_group("incremental").get("incremental_stagger_seconds", 30)

    @property
    def playwright_available(self) -> bool:
        """检查playwright是否可用"""
        return self._playwright_available

    @property
    def playwright_version(self) -> str | None:
        """获取playwright版本"""
        return self._playwright_version

    def _check_playwright_availability(self):
        """检查 playwright 可用性"""
        try:
            import importlib.util

            if importlib.util.find_spec("playwright") is None:
                raise ImportError

            import playwright
            from playwright.async_api import async_playwright  # noqa: F401

            self._playwright_available = True

            try:
                self._playwright_version = playwright.__version__
                logger.info(f"使用 playwright {self._playwright_version} 作为 PDF 引擎")
            except AttributeError:
                self._playwright_version = "unknown"
                logger.info("使用 playwright (版本未知) 作为 PDF 引擎")

        except ImportError:
            self._playwright_available = False
            self._playwright_version = None
            logger.warning(
                "playwright 未安装，PDF 功能将不可用。请使用 pip install playwright 安装，并运行 playwright install chromium"
            )

    def get_browser_path(self) -> str:
        """获取自定义浏览器路径"""
        return self._get_group("pdf").get("browser_path", "")

    def set_browser_path(self, path: str):
        """设置自定义浏览器路径"""
        self._ensure_group("pdf")["browser_path"] = path
        self.config.save_config()

    def reload_playwright(self) -> bool:
        """重新加载 playwright 模块"""
        try:
            logger.info("开始重新加载 playwright 模块...")

            modules_to_remove = [
                mod for mod in sys.modules.keys() if mod.startswith("playwright")
            ]
            logger.info(f"移除模块: {modules_to_remove}")
            for mod in modules_to_remove:
                del sys.modules[mod]

            try:
                import playwright

                self._playwright_available = True
                try:
                    self._playwright_version = playwright.__version__
                    logger.info(
                        f"重新加载成功，playwright 版本: {self._playwright_version}"
                    )
                except AttributeError:
                    self._playwright_version = "unknown"
                    logger.info("重新加载成功，playwright 版本未知")

                return True

            except ImportError:
                logger.info("playwright 重新导入可能需要重启 AstrBot")
                self._playwright_available = False
                self._playwright_version = None
                return False
            except Exception:
                logger.info("playwright 重新导入失败")
                self._playwright_available = False
                self._playwright_version = None
                return False

        except Exception as e:
            logger.error(f"重新加载 playwright 时出错: {e}")
            return False

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
