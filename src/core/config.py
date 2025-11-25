"""
配置管理模块
负责处理插件配置和PDF依赖检查
"""

import sys
from astrbot.api import logger, AstrBotConfig


class ConfigManager:
    """配置管理器"""

    def __init__(self, config: AstrBotConfig):
        self.config = config
        self._pyppeteer_available = False
        self._pyppeteer_version = None
        self._check_pyppeteer_availability()

    def get_group_list_mode(self) -> str:
        """获取群组列表模式 (whitelist/blacklist/none)"""
        return self.config.get("group_list_mode", "none")

    def get_group_list(self) -> list[str]:
        """获取群组列表（用于黑白名单）"""
        return self.config.get("group_list", [])

    def is_group_allowed(self, group_id: str) -> bool:
        """根据配置的白/黑名单判断是否允许在该群聊中使用"""
        mode = self.get_group_list_mode().lower()
        if mode not in ("whitelist", "blacklist", "none"):
            mode = "none"

        # none模式下，不进行黑白名单检查，由调用方决定（通常是回退到 enabled_groups）
        if mode == "none":
            return True

        glist = [str(g) for g in self.get_group_list()]
        group_id_str = str(group_id)

        if mode == "whitelist":
            return group_id_str in glist if glist else False
        if mode == "blacklist":
            return group_id_str not in glist if glist else True

        return True

    def get_max_concurrent_tasks(self) -> int:
        """获取自动分析最大并发数"""
        return self.config.get("max_concurrent_tasks", 5)

    def get_max_messages(self) -> int:
        """获取最大消息数量"""
        return self.config.get("max_messages", 1000)

    def get_analysis_days(self) -> int:
        """获取分析天数"""
        return self.config.get("analysis_days", 1)

    def get_auto_analysis_time(self) -> str:
        """获取自动分析时间"""
        return self.config.get("auto_analysis_time", "09:00")

    def get_enable_auto_analysis(self) -> bool:
        """获取是否启用自动分析"""
        return self.config.get("enable_auto_analysis", False)

    def get_output_format(self) -> str:
        """获取输出格式"""
        return self.config.get("output_format", "image")

    def get_min_messages_threshold(self) -> int:
        """获取最小消息阈值"""
        return self.config.get("min_messages_threshold", 50)

    def get_topic_analysis_enabled(self) -> bool:
        """获取是否启用话题分析"""
        return self.config.get("topic_analysis_enabled", True)

    def get_user_title_analysis_enabled(self) -> bool:
        """获取是否启用用户称号分析"""
        return self.config.get("user_title_analysis_enabled", True)

    def get_golden_quote_analysis_enabled(self) -> bool:
        """获取是否启用金句分析"""
        return self.config.get("golden_quote_analysis_enabled", True)

    def get_max_topics(self) -> int:
        """获取最大话题数量"""
        return self.config.get("max_topics", 5)

    def get_max_user_titles(self) -> int:
        """获取最大用户称号数量"""
        return self.config.get("max_user_titles", 8)

    def get_max_golden_quotes(self) -> int:
        """获取最大金句数量"""
        return self.config.get("max_golden_quotes", 5)

    def get_llm_timeout(self) -> int:
        """获取LLM请求超时时间（秒）"""
        return self.config.get("llm_timeout", 30)

    def get_llm_retries(self) -> int:
        """获取LLM请求重试次数"""
        return self.config.get("llm_retries", 2)

    def get_llm_backoff(self) -> int:
        """获取LLM请求重试退避基值（秒），实际退避会乘以尝试次数"""
        return self.config.get("llm_backoff", 2)

    def get_topic_max_tokens(self) -> int:
        """获取话题分析最大token数"""
        return self.config.get("topic_max_tokens", 12288)

    def get_golden_quote_max_tokens(self) -> int:
        """获取金句分析最大token数"""
        return self.config.get("golden_quote_max_tokens", 4096)

    def get_user_title_max_tokens(self) -> int:
        """获取用户称号分析最大token数"""
        return self.config.get("user_title_max_tokens", 4096)

    def get_llm_provider_id(self) -> str:
        """获取主 LLM Provider ID"""
        return self.config.get("llm_provider_id", "")

    def get_topic_provider_id(self) -> str:
        """获取话题分析专用 Provider ID"""
        return self.config.get("topic_provider_id", "")

    def get_user_title_provider_id(self) -> str:
        """获取用户称号分析专用 Provider ID"""
        return self.config.get("user_title_provider_id", "")

    def get_golden_quote_provider_id(self) -> str:
        """获取金句分析专用 Provider ID"""
        return self.config.get("golden_quote_provider_id", "")

    def get_pdf_output_dir(self) -> str:
        """获取PDF输出目录"""
        return self.config.get(
            "pdf_output_dir", "data/plugins/astrbot-qq-group-daily-analysis/reports"
        )

    def get_bot_qq_ids(self) -> list:
        """获取bot QQ号列表"""
        return self.config.get("bot_qq_ids", [])

    def get_pdf_filename_format(self) -> str:
        """获取PDF文件名格式"""
        return self.config.get(
            "pdf_filename_format", "群聊分析报告_{group_id}_{date}.pdf"
        )

    def get_topic_analysis_prompt(self, style: str = "topic_prompt") -> str:
        """
        获取话题分析提示词模板

        Args:
            style: 提示词风格，默认为 "topic_prompt"

        Returns:
            提示词模板字符串
        """
        # 直接从配置中获取 prompts 对象
        prompts_config = self.config.get("topic_analysis_prompts", {})
        # 获取指定的 prompt
        prompt = prompts_config.get(style, "topic_prompt")
        if prompt:
            return prompt
        # 兼容旧配置
        return self.config.get("topic_analysis_prompt", "")

    def get_user_title_analysis_prompt(self, style: str = "user_title_prompt") -> str:
        """
        获取用户称号分析提示词模板

        Args:
            style: 提示词风格，默认为 "user_title_prompt"

        Returns:
            提示词模板字符串
        """
        # 直接从配置中获取 prompts 对象
        prompts_config = self.config.get("user_title_analysis_prompts", {})
        # 获取指定的 prompt
        prompt = prompts_config.get(style, "user_title_prompt")
        if prompt:
            return prompt
        # 兼容旧配置
        return self.config.get("user_title_analysis_prompt", "")

    def get_golden_quote_analysis_prompt(
        self, style: str = "golden_quote_prompt"
    ) -> str:
        """
        获取金句分析提示词模板

        Args:
            style: 提示词风格，默认为 "golden_quote_prompt"

        Returns:
            提示词模板字符串
        """
        # 直接从配置中获取 prompts 对象
        prompts_config = self.config.get("golden_quote_analysis_prompts", {})
        # 获取指定的 prompt
        prompt = prompts_config.get(style, "golden_quote_prompt")
        if prompt:
            return prompt
        # 兼容旧配置
        return self.config.get("golden_quote_analysis_prompt", "")

    def set_topic_analysis_prompt(self, prompt: str):
        """设置话题分析提示词模板"""
        self.config["topic_analysis_prompt"] = prompt
        self.config.save_config()

    def set_user_title_analysis_prompt(self, prompt: str):
        """设置用户称号分析提示词模板"""
        self.config["user_title_analysis_prompt"] = prompt
        self.config.save_config()

    def set_golden_quote_analysis_prompt(self, prompt: str):
        """设置金句分析提示词模板"""
        self.config["golden_quote_analysis_prompt"] = prompt
        self.config.save_config()

    def set_output_format(self, format_type: str):
        """设置输出格式"""
        self.config["output_format"] = format_type
        self.config.save_config()

    def set_group_list_mode(self, mode: str):
        """设置群组列表模式"""
        self.config["group_list_mode"] = mode
        self.config.save_config()

    def set_group_list(self, groups: list[str]):
        """设置群组列表"""
        self.config["group_list"] = groups
        self.config.save_config()

    def set_max_concurrent_tasks(self, count: int):
        """设置自动分析最大并发数"""
        self.config["max_concurrent_tasks"] = count
        self.config.save_config()

    def set_max_messages(self, count: int):
        """设置最大消息数量"""
        self.config["max_messages"] = count
        self.config.save_config()

    def set_analysis_days(self, days: int):
        """设置分析天数"""
        self.config["analysis_days"] = days
        self.config.save_config()

    def set_auto_analysis_time(self, time_str: str):
        """设置自动分析时间"""
        self.config["auto_analysis_time"] = time_str
        self.config.save_config()

    def set_enable_auto_analysis(self, enabled: bool):
        """设置是否启用自动分析"""
        self.config["enable_auto_analysis"] = enabled
        self.config.save_config()

    def set_min_messages_threshold(self, threshold: int):
        """设置最小消息阈值"""
        self.config["min_messages_threshold"] = threshold
        self.config.save_config()

    def set_topic_analysis_enabled(self, enabled: bool):
        """设置是否启用话题分析"""
        self.config["topic_analysis_enabled"] = enabled
        self.config.save_config()

    def set_user_title_analysis_enabled(self, enabled: bool):
        """设置是否启用用户称号分析"""
        self.config["user_title_analysis_enabled"] = enabled
        self.config.save_config()

    def set_golden_quote_analysis_enabled(self, enabled: bool):
        """设置是否启用金句分析"""
        self.config["golden_quote_analysis_enabled"] = enabled
        self.config.save_config()

    def set_max_topics(self, count: int):
        """设置最大话题数量"""
        self.config["max_topics"] = count
        self.config.save_config()

    def set_max_user_titles(self, count: int):
        """设置最大用户称号数量"""
        self.config["max_user_titles"] = count
        self.config.save_config()

    def set_max_golden_quotes(self, count: int):
        """设置最大金句数量"""
        self.config["max_golden_quotes"] = count
        self.config.save_config()

    def set_pdf_output_dir(self, directory: str):
        """设置PDF输出目录"""
        self.config["pdf_output_dir"] = directory
        self.config.save_config()

    def set_pdf_filename_format(self, format_str: str):
        """设置PDF文件名格式"""
        self.config["pdf_filename_format"] = format_str
        self.config.save_config()

    def get_report_template(self) -> str:
        """获取报告模板名称"""
        return self.config.get("report_template", "scrapbook")

    def set_report_template(self, template_name: str):
        """设置报告模板名称"""
        self.config["report_template"] = template_name
        self.config.save_config()

    def get_enable_user_card(self) -> bool:
        """获取是否使用用户群名片"""
        return self.config.get("enable_user_card", False)

    @property
    def pyppeteer_available(self) -> bool:
        """检查pyppeteer是否可用"""
        return self._pyppeteer_available

    @property
    def pyppeteer_version(self) -> str | None:
        """获取pyppeteer版本"""
        return self._pyppeteer_version

    def _check_pyppeteer_availability(self):
        """检查 pyppeteer 可用性"""
        try:
            import pyppeteer

            self._pyppeteer_available = True

            # 检查版本
            try:
                self._pyppeteer_version = pyppeteer.__version__
                logger.info(f"使用 pyppeteer {self._pyppeteer_version} 作为 PDF 引擎")
            except AttributeError:
                self._pyppeteer_version = "unknown"
                logger.info("使用 pyppeteer (版本未知) 作为 PDF 引擎")

        except ImportError:
            self._pyppeteer_available = False
            self._pyppeteer_version = None
            logger.warning(
                "pyppeteer 未安装，PDF 功能将不可用。请使用 /安装PDF 命令安装 pyppeteer==1.0.2"
            )

    def reload_pyppeteer(self) -> bool:
        """重新加载 pyppeteer 模块"""
        try:
            logger.info("开始重新加载 pyppeteer 模块...")

            # 移除所有 pyppeteer 相关模块
            modules_to_remove = [
                mod for mod in sys.modules.keys() if mod.startswith("pyppeteer")
            ]
            logger.info(f"移除模块: {modules_to_remove}")
            for mod in modules_to_remove:
                del sys.modules[mod]

            # 强制重新导入
            try:
                import pyppeteer

                # 更新全局变量
                self._pyppeteer_available = True
                try:
                    self._pyppeteer_version = pyppeteer.__version__
                    logger.info(
                        f"重新加载成功，pyppeteer 版本: {self._pyppeteer_version}"
                    )
                except AttributeError:
                    self._pyppeteer_version = "unknown"
                    logger.info("重新加载成功，pyppeteer 版本未知")

                return True

            except ImportError:
                logger.info("pyppeteer 重新导入需要重启 AstrBot 才能生效")
                logger.info(
                    "💡 提示：pyppeteer 安装成功，但需要重启 AstrBot 后才能使用 PDF 功能"
                )
                self._pyppeteer_available = False
                self._pyppeteer_version = None
                return False
            except Exception:
                logger.info("pyppeteer 重新导入需要重启 AstrBot 才能生效")
                logger.info(
                    "💡 提示：pyppeteer 安装成功，但需要重启 AstrBot 后才能使用 PDF 功能"
                )
                self._pyppeteer_available = False
                self._pyppeteer_version = None
                return False

        except Exception as e:
            logger.error(f"重新加载 pyppeteer 时出错: {e}")
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
            # 重新从AstrBot配置系统读取所有配置
            logger.info("重新加载配置...")
            # 配置会自动从self.config中重新读取
            logger.info("配置重载完成")
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
