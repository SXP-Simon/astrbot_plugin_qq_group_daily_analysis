"""
配置管理器 - 集中化配置管理

该模块提供了一个访问插件配置的统一接口，
封装了现有的配置模块，并增加了验证和默认值功能。
"""

from typing import Any, Dict, List, Optional

from astrbot.api import logger


class ConfigManager:
    """
    插件的集中配置管理器。

    提供带有默认值和验证的配置值类型化访问。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化配置管理器。

        Args:
            config: 原始配置字典
        """
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值。

        Args:
            key: 配置键（支持点号表示法）
            default: 如果键未找到则返回默认值

        Returns:
            配置值或默认值
        """
        try:
            keys = key.split(".")
            value = self._config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
                if value is None:
                    return default
            return value
        except Exception:
            return default

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值。

        Args:
            key: 配置键
            value: 要设置的值
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    # ========================================================================
    # 群组配置
    # ========================================================================

    def get_enabled_groups(self) -> List[str]:
        """获取启用的群组 ID 列表。"""
        groups = self.get("enabled_groups", [])
        return [str(g) for g in groups] if groups else []

    def is_group_enabled(self, group_id: str) -> bool:
        """检查群组是否启用了分析。"""
        enabled = self.get_enabled_groups()
        return str(group_id) in enabled or not enabled  # 空列表意味着全部启用

    def get_bot_qq_ids(self) -> List[str]:
        """获取要过滤掉的机器人 QQ ID 列表。"""
        ids = self.get("bot_qq_ids", [])
        return [str(i) for i in ids] if ids else []

    # ========================================================================
    # 分析配置
    # ========================================================================

    def get_max_topics(self) -> int:
        """获取要提取的最大话题数。"""
        return int(self.get("max_topics", 5))

    def get_max_user_titles(self) -> int:
        """获取要生成的最大用户称号数。"""
        return int(self.get("max_user_titles", 10))

    def get_max_golden_quotes(self) -> int:
        """获取要提取的最大金句数。"""
        return int(self.get("max_golden_quotes", 5))

    def get_min_messages_for_analysis(self) -> int:
        """获取分析所需的最小消息数。"""
        return int(self.get("min_messages", 50))

    # ========================================================================
    # LLM 配置
    def get_topic_provider_id(self) -> Optional[str]:
        """获取话题分析的提供商 ID"""
        return self.get("topic_provider_id")

    def get_user_title_provider_id(self) -> Optional[str]:
        """获取用户称号分析的提供商 ID"""
        return self.get("user_title_provider_id")

    def get_golden_quote_provider_id(self) -> Optional[str]:
        """获取金句分析的提供商 ID"""
        return self.get("golden_quote_provider_id")

    def get_topic_max_tokens(self) -> int:
        """获取话题分析的最大 token 数"""
        return int(self.get("topic_max_tokens", 2000))

    def get_user_title_max_tokens(self) -> int:
        """获取用户称号分析的最大 token 数"""
        return int(self.get("user_title_max_tokens", 2000))

    def get_golden_quote_max_tokens(self) -> int:
        """获取金句分析的最大 token 数"""
        return int(self.get("golden_quote_max_tokens", 1500))

    # ========================================================================
    # 提示词配置
    # ========================================================================

    def get_topic_analysis_prompt(self) -> Optional[str]:
        """获取话题分析的自定义提示词模板"""
        return self.get("prompts.topic_analysis")

    def get_user_title_analysis_prompt(self) -> Optional[str]:
        """获取用户称号分析的自定义提示词模板"""
        return self.get("prompts.user_title_analysis")

    def get_golden_quote_analysis_prompt(self) -> Optional[str]:
        """获取金句分析的自定义提示词模板"""
        return self.get("prompts.golden_quote_analysis")

    # ========================================================================
    # 调度配置
    # ========================================================================

    def get_auto_analysis_enabled(self) -> bool:
        """检查是否启用了自动分析"""
        return bool(self.get("auto_analysis_enabled", False))

    def get_analysis_time(self) -> str:
        """获取计划分析时间 (HH:MM 格式)"""
        return str(self.get("analysis_time", "23:00"))

    def get_analysis_timezone(self) -> str:
        """获取计划分析的时区"""
        return str(self.get("timezone", "Asia/Shanghai"))

    # ========================================================================
    # 报告配置
    # ========================================================================

    def get_report_format(self) -> str:
        """获取报告格式 (text, markdown, image)"""
        return str(self.get("report_format", "text"))

    def get_include_statistics(self) -> bool:
        """检查是否在报告中包含统计信息"""
        return bool(self.get("include_statistics", True))

    def get_include_topics(self) -> bool:
        """检查是否在报告中包含话题"""
        return bool(self.get("include_topics", True))

    def get_include_user_titles(self) -> bool:
        """检查是否在报告中包含用户称号"""
        return bool(self.get("include_user_titles", True))

    def get_include_golden_quotes(self) -> bool:
        """检查是否在报告中包含金句"""
        return bool(self.get("include_golden_quotes", True))

    # ========================================================================
    # 工具方法
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._config.copy()

    def update(self, updates: Dict[str, Any]) -> None:
        """
        使用新值更新配置

        Args:
            updates: 要应用的更新字典
        """
        self._config.update(updates)

    def validate(self) -> List[str]:
        """
        验证配置

        Returns:
            验证错误消息列表（如果有效则为空）
        """
        errors = []

        # 验证数值范围
        if self.get_max_topics() < 1 or self.get_max_topics() > 20:
            errors.append("max_topics 必须在 1 到 20 之间")

        if self.get_max_user_titles() < 1 or self.get_max_user_titles() > 50:
            errors.append("max_user_titles 必须在 1 到 50 之间")

        if self.get_max_golden_quotes() < 1 or self.get_max_golden_quotes() > 20:
            errors.append("max_golden_quotes 必须在 1 到 20 之间")

        # 验证时间格式
        time_str = self.get_analysis_time()
        try:
            hours, minutes = time_str.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                errors.append("analysis_time 必须是 HH:MM 格式 (00:00-23:59)")
        except ValueError:
            errors.append("analysis_time 必须是 HH:MM 格式")

        return errors
