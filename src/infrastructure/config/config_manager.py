"""
配置管理模块 - 基础设施层
负责处理插件配置和PDF依赖检查
"""

import sys

from astrbot.api import AstrBotConfig, logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


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
        """获取是否启用自动分析"""
        return self._get_group("auto_analysis").get("enable_auto_analysis", False)

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

    def get_topic_max_tokens(self) -> int:
        """获取话题分析最大token数"""
        return self._get_group("llm").get("topic_max_tokens", 12288)

    def get_golden_quote_max_tokens(self) -> int:
        """获取金句分析最大token数"""
        return self._get_group("llm").get("golden_quote_max_tokens", 4096)

    def get_user_title_max_tokens(self) -> int:
        """获取用户称号分析最大token数"""
        return self._get_group("llm").get("user_title_max_tokens", 4096)

    def get_debug_mode(self) -> bool:
        """获取是否启用调试模式"""
        return self._get_group("basic").get("debug_mode", False)

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

    def get_pdf_output_dir(self) -> str:
        """获取PDF输出目录"""
        try:
            plugin_name = "astrbot_plugin_qq_group_daily_analysis"
            data_path = get_astrbot_data_path()
            default_path = data_path / "plugin_data" / plugin_name / "reports"
            return self._get_group("pdf").get("pdf_output_dir", str(default_path))
        except Exception:
            return self._get_group("pdf").get(
                "pdf_output_dir",
                "data/plugins/astrbot_plugin_qq_group_daily_analysis/reports",
            )

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
        self, style: str = "golden_quote_prompt"
    ) -> str:
        """获取金句分析提示词模板"""
        prompts_config = self._get_group("prompts").get(
            "golden_quote_analysis_prompts", {}
        )
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
        prompts["golden_quote_analysis_prompts"]["golden_quote_prompt"] = prompt
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
        """获取自动分析最大并发数"""
        return self._get_group("auto_analysis").get("max_concurrent_tasks", 3)

    def set_max_concurrent_tasks(self, count: int):
        """设置自动分析最大并发数"""
        self._ensure_group("auto_analysis")["max_concurrent_tasks"] = count
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
        """设置自动分析时间"""
        self._ensure_group("auto_analysis")["auto_analysis_time"] = time_val
        self.config.save_config()

    def set_enable_auto_analysis(self, enabled: bool):
        """设置是否启用自动分析"""
        self._ensure_group("auto_analysis")["enable_auto_analysis"] = enabled
        self.config.save_config()

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

    # ========== 增量分析配置 ==========

    def get_incremental_enabled(self) -> bool:
        """获取是否启用增量分析模式"""
        return self._get_group("incremental").get("incremental_enabled", False)

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

    def get_incremental_max_messages(self) -> int:
        """获取单次增量分析的最大消息数"""
        return self._get_group("incremental").get("incremental_max_messages", 300)

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
