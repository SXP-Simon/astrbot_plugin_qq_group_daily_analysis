"""
Config Manager - Centralized configuration management

This module provides a unified interface for accessing plugin configuration,
wrapping the existing config module with additional validation and defaults.
"""

from typing import Any, Dict, List, Optional

from astrbot.api import logger


class ConfigManager:
    """
    Centralized configuration manager for the plugin.

    Provides typed access to configuration values with defaults
    and validation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the configuration manager.

        Args:
            config: Raw configuration dictionary
        """
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default
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
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    # ========================================================================
    # Group Configuration
    # ========================================================================

    def get_enabled_groups(self) -> List[str]:
        """Get list of enabled group IDs."""
        groups = self.get("enabled_groups", [])
        return [str(g) for g in groups] if groups else []

    def is_group_enabled(self, group_id: str) -> bool:
        """Check if a group is enabled for analysis."""
        enabled = self.get_enabled_groups()
        return str(group_id) in enabled or not enabled  # Empty means all enabled

    def get_bot_qq_ids(self) -> List[str]:
        """Get list of bot QQ IDs to filter out."""
        ids = self.get("bot_qq_ids", [])
        return [str(i) for i in ids] if ids else []

    # ========================================================================
    # Analysis Configuration
    # ========================================================================

    def get_max_topics(self) -> int:
        """Get maximum number of topics to extract."""
        return int(self.get("max_topics", 5))

    def get_max_user_titles(self) -> int:
        """Get maximum number of user titles to generate."""
        return int(self.get("max_user_titles", 10))

    def get_max_golden_quotes(self) -> int:
        """Get maximum number of golden quotes to extract."""
        return int(self.get("max_golden_quotes", 5))

    def get_min_messages_for_analysis(self) -> int:
        """Get minimum messages required for analysis."""
        return int(self.get("min_messages", 50))

    # ========================================================================
    # LLM Configuration
    # ========================================================================

    def get_topic_provider_id(self) -> Optional[str]:
        """Get provider ID for topic analysis."""
        return self.get("topic_provider_id")

    def get_user_title_provider_id(self) -> Optional[str]:
        """Get provider ID for user title analysis."""
        return self.get("user_title_provider_id")

    def get_golden_quote_provider_id(self) -> Optional[str]:
        """Get provider ID for golden quote analysis."""
        return self.get("golden_quote_provider_id")

    def get_topic_max_tokens(self) -> int:
        """Get max tokens for topic analysis."""
        return int(self.get("topic_max_tokens", 2000))

    def get_user_title_max_tokens(self) -> int:
        """Get max tokens for user title analysis."""
        return int(self.get("user_title_max_tokens", 2000))

    def get_golden_quote_max_tokens(self) -> int:
        """Get max tokens for golden quote analysis."""
        return int(self.get("golden_quote_max_tokens", 1500))

    # ========================================================================
    # Prompt Configuration
    # ========================================================================

    def get_topic_analysis_prompt(self) -> Optional[str]:
        """Get custom prompt template for topic analysis."""
        return self.get("prompts.topic_analysis")

    def get_user_title_analysis_prompt(self) -> Optional[str]:
        """Get custom prompt template for user title analysis."""
        return self.get("prompts.user_title_analysis")

    def get_golden_quote_analysis_prompt(self) -> Optional[str]:
        """Get custom prompt template for golden quote analysis."""
        return self.get("prompts.golden_quote_analysis")

    # ========================================================================
    # Scheduling Configuration
    # ========================================================================

    def get_auto_analysis_enabled(self) -> bool:
        """Check if auto analysis is enabled."""
        return bool(self.get("auto_analysis_enabled", False))

    def get_analysis_time(self) -> str:
        """Get scheduled analysis time (HH:MM format)."""
        return str(self.get("analysis_time", "23:00"))

    def get_analysis_timezone(self) -> str:
        """Get timezone for scheduled analysis."""
        return str(self.get("timezone", "Asia/Shanghai"))

    # ========================================================================
    # Report Configuration
    # ========================================================================

    def get_report_format(self) -> str:
        """Get report format (text, markdown, image)."""
        return str(self.get("report_format", "text"))

    def get_include_statistics(self) -> bool:
        """Check if statistics should be included in reports."""
        return bool(self.get("include_statistics", True))

    def get_include_topics(self) -> bool:
        """Check if topics should be included in reports."""
        return bool(self.get("include_topics", True))

    def get_include_user_titles(self) -> bool:
        """Check if user titles should be included in reports."""
        return bool(self.get("include_user_titles", True))

    def get_include_golden_quotes(self) -> bool:
        """Check if golden quotes should be included in reports."""
        return bool(self.get("include_golden_quotes", True))

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Get the raw configuration dictionary."""
        return self._config.copy()

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary of updates to apply
        """
        self._config.update(updates)

    def validate(self) -> List[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate numeric ranges
        if self.get_max_topics() < 1 or self.get_max_topics() > 20:
            errors.append("max_topics must be between 1 and 20")

        if self.get_max_user_titles() < 1 or self.get_max_user_titles() > 50:
            errors.append("max_user_titles must be between 1 and 50")

        if self.get_max_golden_quotes() < 1 or self.get_max_golden_quotes() > 20:
            errors.append("max_golden_quotes must be between 1 and 20")

        # Validate time format
        time_str = self.get_analysis_time()
        try:
            hours, minutes = time_str.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                errors.append("analysis_time must be in HH:MM format (00:00-23:59)")
        except ValueError:
            errors.append("analysis_time must be in HH:MM format")

        return errors
