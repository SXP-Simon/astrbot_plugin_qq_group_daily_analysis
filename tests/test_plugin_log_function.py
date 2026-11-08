from src.infrastructure.logging.plugin_log_buffer import PluginLogBuffer


def test_function_metadata_survives_query_trace_stream_and_copy():
    buffer = PluginLogBuffer()
    streamed = []
    buffer.register_listener(streamed.append)
    entry = buffer.record_log(
        "WARNING", "示例日志", trace_id="example-trace",
        location="worker.py:42", function_name="Worker.run",
    )
    assert streamed == [entry]
    assert streamed[0].to_dict()["function_name"] == "Worker.run"
    items, total = buffer.query(search="WORKER.RUN")
    assert total == 1
    assert items[0]["location"] == "worker.py:42"
    assert "[worker.py:42] [Worker.run]" in items[0]["raw"]
    assert buffer.get_trace_logs("example-trace") == items


def test_old_logs_without_function_keep_location_and_raw_format():
    buffer = PluginLogBuffer()
    entry = buffer.record_log("INFO", "已有记录", location="old.py:8")
    assert entry.function_name is None
    assert "[old.py:8]: 已有记录" in entry.raw
    assert buffer.query(search="Worker.run") == ([], 0)
