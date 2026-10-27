import inspect
import logging
import os

from src.infrastructure.logging.plugin_log_buffer import (
    PluginLogBuffer,
    global_log_buffer,
)
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

    global_log_buffer.clear()
    expected_line = inspect.currentframe().f_lineno + 1
    logger_module.logger.info("记录真实业务调用位置")

    assert len(records) == 1
    assert os.path.normcase(records[0].pathname) == os.path.normcase(__file__)
    assert records[0].lineno == expected_line

    # 验证插件内部 log_buffer 也准确捕获了代码点与行号
    items, total = global_log_buffer.query(limit=10)
    assert total >= 1
    latest = items[0]
    assert latest["location"] == f"test_plugin_logger.py:{expected_line}"
    assert f"[test_plugin_logger.py:{expected_line}]" in latest["raw"]


def test_plugin_log_buffer_record_log_extracts_location():
    buf = PluginLogBuffer()
    buf.record_log(
        level="INFO",
        msg="测试消息",
        logger_name="test",
        location="some_service.py:42",
    )
    items, total = buf.query(limit=10)
    assert total == 1
    assert items[0]["location"] == "some_service.py:42"
    assert "[some_service.py:42]" in items[0]["raw"]


def test_plugin_log_buffer_query_matches_location():
    buf = PluginLogBuffer()
    buf.record_log(
        level="INFO",
        msg="普通的系统日志",
        location="unique_worker.py:100",
    )
    items, total = buf.query(search="unique_worker")
    assert total == 1
    assert items[0]["location"] == "unique_worker.py:100"

    items_empty, total_empty = buf.query(search="non_existent_module")
    assert total_empty == 0


def test_host_info_filter_does_not_remove_plugin_debug_buffer(monkeypatch, caplog):
    """宿主过滤 DEBUG 输出时，插件 WebUI 缓冲仍保留排障细节。"""
    backend_logger = logging.getLogger("test.host_info_filter")
    caplog.set_level(logging.INFO, logger=backend_logger.name)
    buffer = PluginLogBuffer()
    monkeypatch.setattr(logger_module, "astrbot_logger", backend_logger)
    monkeypatch.setattr(logger_module, "global_log_buffer", buffer)
    logger_module.logger.debug("仅在插件缓冲查看的选择细节")
    logger_module.logger.info("用户可见的请求摘要")
    assert "选择细节" not in caplog.text
    assert "请求摘要" in caplog.text
    items, _ = buffer.query(limit=10)
    assert any(item["level"] == "DEBUG" and "选择细节" in item["message"] for item in items)
