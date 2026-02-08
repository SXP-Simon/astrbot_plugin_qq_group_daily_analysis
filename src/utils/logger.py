import logging
from typing import Any

from astrbot.api import logger as astrbot_logger


class PluginLoggerAdapter(logging.LoggerAdapter):
    """
    日志适配器：插件级统一日志装饰器

    自动向所有通过该实例输出的日志信息前缀添加 `[QQ群分析]` 标签，
    以便用户在 AstrBot 混合日志流中快速定位属于本插件的输出。
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """
        加工日志消息，注入插件专有前缀。

        Args:
            msg (str): 原始日志消息
            kwargs (Any): 额外的日志参数映射

        Returns:
            tuple[str, Any]: (格式化后的消息, 参数)
        """
        return f"[QQ群分析] {msg}", kwargs


# 导出带前缀的 logger
logger = PluginLoggerAdapter(astrbot_logger, {})
