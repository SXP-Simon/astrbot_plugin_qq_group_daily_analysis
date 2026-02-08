import logging

from astrbot.api import logger as astrbot_logger


class PluginLoggerAdapter(logging.LoggerAdapter):
    """
    插件日志适配器
    自动为日志添加 [QQ群分析] 前缀，方便区分
    """

    def process(self, msg, kwargs):
        return f"[QQ群分析] {msg}", kwargs


# 导出带前缀的 logger
logger = PluginLoggerAdapter(astrbot_logger, {})
