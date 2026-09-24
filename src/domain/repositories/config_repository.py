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
