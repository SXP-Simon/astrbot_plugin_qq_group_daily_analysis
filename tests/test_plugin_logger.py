import inspect
import logging

from src.utils import logger as logger_module


def test_plugin_logger_records_business_call_site(monkeypatch):
    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    backend_logger = logging.getLogger("test.plugin_logger")
    backend_logger.handlers.clear()
    backend_logger.addHandler(CaptureHandler())
    backend_logger.setLevel(logging.DEBUG)
    backend_logger.propagate = False
    monkeypatch.setattr(logger_module, "astrbot_logger", backend_logger)

    expected_line = inspect.currentframe().f_lineno + 1
    logger_module.logger.info("记录真实业务调用位置")

    assert len(records) == 1
    assert records[0].pathname == __file__
    assert records[0].lineno == expected_line
