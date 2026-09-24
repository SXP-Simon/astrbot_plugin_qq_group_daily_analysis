"""
配置访问仓储接口 - 领域层
定义插件配置与群组偏好读取的抽象协议，解耦应用层与具体配置载体。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IConfigProvider(Protocol):
    """配置访问抽象协议"""

    def is_group_allowed(self, group_id_or_umo: str) -> bool:
        """检查指定群聊是否在允许分析的名单中"""
        ...

    def get_filter_bot_messages(self) -> bool:
        """检查是否过滤机器人消息"""
        ...

    def get_bot_self_ids(self) -> list:
        """获取机器人自身的账号ID列表"""
        ...

    def get_output_format(self) -> list[str]:
        """获取输出格式列表"""
        ...

    def get_report_template(self) -> str:
        """获取报告模板名称"""
        ...

    def get_llm_max_concurrent(self) -> int:
        """获取 LLM 全局最大并发度"""
        ...

    def get_analysis_days(self) -> int:
        """获取分析回溯天数"""
        ...

    def get_max_messages(self) -> int:
        """获取最大分析消息数"""
        ...

    def get_min_messages_threshold(self) -> int:
        """获取最小消息阈值"""
        ...

    def get_topic_analysis_enabled(self) -> bool:
        """是否启用话题总结"""
        ...

    def get_user_title_analysis_enabled(self) -> bool:
        """是否启用用户称号分析"""
        ...

    def get_golden_quote_analysis_enabled(self) -> bool:
        """是否启用金句分析"""
        ...

    def get_chat_quality_analysis_enabled(self) -> bool:
        """是否启用聊天质量锐评"""
        ...

    def get_incremental_min_messages(self) -> int:
        """获取增量批次最小触发消息数"""
        ...

    def get_incremental_topics_per_batch(self) -> int:
        """获取增量批次提取话题上限"""
        ...

    def get_incremental_quotes_per_batch(self) -> int:
        """获取增量批次提取金句上限"""
        ...

    def get_max_user_titles(self) -> int:
        """获取最多生成的用户称号数量"""
        ...

    def get_enable_daily_comic(self) -> bool:
        """是否启用每日群漫画"""
        ...

    def get_selected_comic_character(self) -> dict | None:
        """获取当前选中的漫画角色配置"""
        ...

    def get_comic_character_persona_id(self, character: dict | None) -> str:
        """获取漫画角色绑定的人格ID"""
        ...

    def get_comic_character_storyboard_prompt(self, character: dict | None) -> str:
        """获取漫画角色专属分镜提示词"""
        ...

    def get_drawing_reference_images(self) -> list[str]:
        """获取当前漫画角色的所有参考图路径列表"""
        ...

    def get_drawing_backend(self) -> str:
        """获取绘图后端类型"""
        ...

    def get_drawing_external_fallback(self) -> bool:
        """是否启用外部生图失败回退机制"""
        ...

    def get_drawing_provider_configs(self) -> list[dict]:
        """获取已启用的漫画生图供应商配置列表"""
        ...

    def get_drawing_output_exception_retry_keywords(self) -> list[str]:
        """获取生图异常重试触发关键词列表"""
        ...

    def set_output_format(self, format_types: str | list[str]) -> None:
        """设置分析报告输出格式"""
        ...

    def set_report_template(self, template_name: str) -> None:
        """设置报告模板名称"""
        ...

    def get_group_list_mode(self) -> str:
        """获取基础群名单模式 (whitelist, blacklist, none)"""
        ...

    def get_group_list(self) -> list[str]:
        """获取基础群名单列表"""
        ...

    def set_group_list(self, groups: list[str]) -> None:
        """设置基础群名单列表"""
        ...

    def get_scheduled_group_list_mode(self) -> str:
        """获取定时分析名单模式 (inherit, whitelist, blacklist)"""
        ...

    def get_scheduled_group_list(self) -> list[str]:
        """获取定时分析目标群列表"""
        ...

    def is_scheduled_group_allowed(self, group_umo_or_id: str) -> bool:
        """判断当前群是否允许参与定时分析（需同时通过基础群权限和定时名单）"""
        ...

    def get_incremental_group_list_mode(self) -> str:
        """获取增量分析名单模式 (inherit, whitelist, blacklist)"""
        ...

    def get_incremental_group_list(self) -> list[str]:
        """获取增量分析群列表"""
        ...

    def is_incremental_group_allowed(self, group_umo_or_id: str) -> bool:
        """判断当前群是否允许使用增量分析（需通过基础、定时和增量三级名单）"""
        ...

    def get_comic_group_list_mode(self) -> str:
        """获取漫画生成名单模式 (inherit, whitelist, blacklist)"""
        ...

    def get_comic_group_list(self) -> list[str]:
        """获取漫画生成群列表"""
        ...

    def is_comic_group_allowed(
        self, group_umo_or_id: str, inherit_allowed: bool | None = None
    ) -> bool:
        """判断当前群是否允许生成漫画"""
        ...

    def is_auto_analysis_enabled(self) -> bool:
        """是否启用自动定时分析"""
        ...

    def get_auto_analysis_time(self) -> list[str]:
        """获取自动定时分析时间列表"""
        ...

    def get_incremental_enabled(self) -> bool:
        """是否启用增量分析模式"""
        ...

    def get_incremental_report_immediately(self) -> bool:
        """是否在增量分析完成后立即发送报告"""
        ...

    def set_incremental_report_immediately(self, enabled: bool) -> None:
        """设置是否在增量分析完成后立即发送报告"""
        ...

    def set_filter_bot_messages(self, enabled: bool) -> None:
        """设置是否过滤机器人消息"""
        ...
