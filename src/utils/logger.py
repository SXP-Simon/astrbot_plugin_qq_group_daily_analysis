from astrbot.api import logger as astrbot_logger


class PluginLogger:
    """
    日志代理类：插件级统一日志装饰器

    自动向所有通过该实例输出的日志信息前缀添加 `[群分析插件]` 标签，
    以便用户在 AstrBot 混合日志流中快速定位属于本插件的输出。
    不直接继承 logging.LoggerAdapter 以符合框架规范。
    """

    def __init__(self, prefix: str = "[群分析插件]"):
        self.prefix = prefix

    def _format_msg(self, msg: str) -> str:
        return f"{self.prefix} {msg}"

    def info(self, msg: str, *args, **kwargs):
        astrbot_logger.info(self._format_msg(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        astrbot_logger.error(self._format_msg(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        astrbot_logger.warning(self._format_msg(msg), *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        astrbot_logger.debug(self._format_msg(msg), *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        astrbot_logger.critical(self._format_msg(msg), *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        astrbot_logger.exception(self._format_msg(msg), *args, **kwargs)


# 导出带前缀的 logger
logger = PluginLogger()
