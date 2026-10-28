"""
WebUI 模块化路由单元测试 (WebUI Modular Routes Tests)
针对 TaskRoutes, TraceRoutes, ReportRoutes, TemplateRoutes, LogRoutes, ConfigRoutes, DataManagementRoutes
进行细粒度隔离测试。
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.active_task_manager import (
    ActiveTaskManager,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.routes import (
    DataManagementRoutes,
    LogRoutes,
    ReportRoutes,
    TaskRoutes,
    TemplateRoutes,
    TraceRoutes,
)


@pytest.fixture
def mock_trace_store(tmp_path):
    db_path = tmp_path / "test_modular_routes.db"
    return TraceSQLiteStore(db_path)


@pytest.fixture
def mock_active_mgr():
    return ActiveTaskManager()


@pytest.mark.asyncio
async def test_task_routes_direct(
    mock_trace_store: TraceSQLiteStore, mock_active_mgr: ActiveTaskManager
):
    """测试 TaskRoutes 独立路由行为"""
    mock_svc = MagicMock()
    routes = TaskRoutes(
        trace_store=mock_trace_store,
        active_task_manager=mock_active_mgr,
        analysis_service=mock_svc,
    )

    # 1. 查询活跃任务
    res = await routes.api_get_active_tasks()
    assert res.get("status_code", 200) == 200
    assert "data" in res

    # 2. 取消不存在的任务
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as req:
        req.json = AsyncMock(return_value={"task_id": "non_existent"})
        cancel_res = await routes.api_cancel_task()
        assert cancel_res.get("status_code", 404) == 404


@pytest.mark.asyncio
async def test_resume_task_uses_new_trace_and_preserves_terminal_source(
    mock_trace_store: TraceSQLiteStore,
    mock_active_mgr: ActiveTaskManager,
    monkeypatch: pytest.MonkeyPatch,
):
    """验证终态任务续跑使用新 Trace，并从旧 Trace 读取 Checkpoint。"""
    from astrbot_plugin_qq_group_daily_analysis.src.application.services.task_lifecycle_service import (
        TaskLifecycleService,
    )

    route_module = importlib.import_module(TaskRoutes.__module__)
    trace_context = route_module.TraceContext
    trace_context.set_global_store(mock_trace_store)
    trace_context.set_global_lifecycle_service(None)

    mock_trace_store.save_trace(
        {
            "trace_id": "resume-source",
            "group_id": "123",
            "group_name": "测试群",
            "platform": "onebot",
            "status": "running",
        }
    )
    TaskLifecycleService(mock_trace_store).transition(
        "resume-source", route_module.TaskEvent.FAIL
    )

    class FakeRequest:
        query: dict[str, str] = {}

        async def json(self) -> dict[str, object]:
            return {}

    monkeypatch.setattr(route_module, "request", FakeRequest())
    monkeypatch.setattr(
        route_module,
        "json_response",
        lambda data, **kwargs: {
            "status_code": kwargs.get("status_code", 200),
            "data": data,
        },
    )
    monkeypatch.setattr(
        route_module,
        "error_response",
        lambda message, **kwargs: {
            "status_code": kwargs.get("status_code", 400),
            "message": message,
        },
    )

    resumed_args: list[dict[str, object]] = []

    async def run_resumed_task(**kwargs: object) -> None:
        resumed_args.append(kwargs)

    routes = TaskRoutes(mock_trace_store, mock_active_mgr, MagicMock())
    monkeypatch.setattr(routes, "_run_resumed_task", run_resumed_task)

    response = await routes.api_resume_task("resume-source")
    await asyncio.sleep(0)

    assert isinstance(response, dict)
    new_trace_id = response["data"]["data"]["trace_id"]
    assert new_trace_id != "resume-source"
    assert resumed_args[0]["trace_id"] == new_trace_id
    assert resumed_args[0]["checkpoint_trace_id"] == "resume-source"
    assert mock_trace_store.get_trace("resume-source")["status"] == "failed"
    assert mock_trace_store.get_trace(new_trace_id)["status"] == "running"
    await mock_active_mgr.finish_task(new_trace_id)

    mock_trace_store.save_trace(
        {
            "trace_id": "already-running",
            "group_id": "456",
            "status": "running",
        }
    )
    conflict_response = await routes.api_resume_task("already-running")
    assert isinstance(conflict_response, dict)
    assert conflict_response["status_code"] == 409
    assert len(resumed_args) == 1


@pytest.mark.asyncio
async def test_trace_routes_direct(
    mock_trace_store: TraceSQLiteStore, mock_active_mgr: ActiveTaskManager
):
    """测试 TraceRoutes 独立路由行为"""
    mock_context = MagicMock()
    mock_context.platform_manager = None
    mock_context.persona_manager = None
    mock_svc = MagicMock()

    routes = TraceRoutes(
        context=mock_context,
        trace_store=mock_trace_store,
        active_task_manager=mock_active_mgr,
        analysis_service=mock_svc,
    )

    # 1. 概览指标
    metrics_res = await routes.api_get_metrics_summary()
    assert metrics_res.get("status_code", 200) == 200

    # 2. 查询不存在的 trace
    detail_res = await routes.api_get_trace_detail("non_existent_trace")
    assert detail_res.get("status_code", 404) == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [False, True])
async def test_trace_detail_uses_live_rounds_but_never_overwrites_terminal_status(
    mock_trace_store, mock_active_mgr, monkeypatch, terminal
):
    """启动快照不遮挡实时轮次，仓储终态不被仍在清理的内存任务覆盖。"""
    from astrbot_plugin_qq_group_daily_analysis.src.application.services.task_lifecycle_service import (
        TaskLifecycleService,
    )
    from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_event import (
        TaskEvent,
    )

    route_module = importlib.import_module(TraceRoutes.__module__)
    trace = route_module.TraceContext(trace_id="live-round-detail", group_id="123")
    mock_trace_store.save_trace(trace.to_dict())
    monkeypatch.setattr(
        route_module.TraceContext, "get_active_trace", staticmethod(lambda _: trace)
    )
    monkeypatch.setattr(route_module, "json_response", lambda payload: payload)
    routes = TraceRoutes(MagicMock(), mock_trace_store, mock_active_mgr, MagicMock())
    with trace.span("RENDER_REPORT") as span:
        span["payload"]["render_attempts"] = [
            {"attempt": 1, "status": "running", "strategy_name": "本地备用"}
        ]
        if terminal:
            TaskLifecycleService(mock_trace_store).transition(
                trace.trace_id, TaskEvent.CANCEL
            )
        result = await routes.api_get_trace_detail(trace.trace_id)
        if terminal:
            assert result["data"]["status"] == "aborted"
            assert result["data"]["spans"] == []
        else:
            assert result["data"]["status"] == "running"
            assert (
                result["data"]["spans"][0]["payload"]["render_attempts"][0]["status"]
                == "running"
            )


@pytest.mark.asyncio
async def test_trace_detail_rechecks_terminal_status_when_active_trace_disappears(
    mock_trace_store, mock_active_mgr, monkeypatch
):
    """在两次查询之间完成取消，详情不能返回第一次读到的运行快照。"""
    from astrbot_plugin_qq_group_daily_analysis.src.application.services.task_lifecycle_service import (
        TaskLifecycleService,
    )
    from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_event import (
        TaskEvent,
    )

    route_module = importlib.import_module(TraceRoutes.__module__)
    mock_trace_store.save_trace(
        {"trace_id": "cancel-between-reads", "group_id": "123", "status": "running"}
    )

    def finish_before_active_lookup_returns(trace_id):
        TaskLifecycleService(mock_trace_store).transition(trace_id, TaskEvent.CANCEL)
        return None

    monkeypatch.setattr(
        route_module.TraceContext,
        "get_active_trace",
        staticmethod(finish_before_active_lookup_returns),
    )
    monkeypatch.setattr(route_module, "json_response", lambda payload: payload)
    routes = TraceRoutes(MagicMock(), mock_trace_store, mock_active_mgr, MagicMock())
    result = await routes.api_get_trace_detail("cancel-between-reads")
    assert result["data"]["status"] == "aborted"


@pytest.mark.asyncio
async def test_template_routes_direct():
    """测试 TemplateRoutes 独立路由行为"""
    mock_svc = MagicMock()
    mock_svc.report_generator = None
    mock_svc.config_manager = MagicMock()

    routes = TemplateRoutes(analysis_service=mock_svc)

    with patch("src.infrastructure.webui.plugin_page_bridge.request") as req:
        req.query = {"template_name": ""}
        preview_res = await routes.api_get_template_preview()
        assert preview_res.get("status_code", 400) == 400


@pytest.mark.asyncio
async def test_log_routes_direct(mock_active_mgr: ActiveTaskManager):
    """测试 LogRoutes 独立路由行为"""
    routes = LogRoutes(active_task_manager=mock_active_mgr)

    with patch("src.infrastructure.webui.plugin_page_bridge.request") as req:
        req.query = {"limit": "10", "offset": "0"}
        logs_res = await routes.api_get_plugin_logs()
        assert logs_res.get("status_code", 200) == 200

        clear_res = await routes.api_clear_plugin_logs()
        assert clear_res.get("status_code", 200) == 200


@pytest.mark.asyncio
async def test_data_management_checkpoint_and_report_query_parsing(
    mock_trace_store: TraceSQLiteStore, tmp_path
):
    """测试 DataManagementRoutes 与 ReportRoutes 正确解析 PluginMultiDict 查询参数"""
    from astrbot.api.web import PluginMultiDict
    from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.web_compat import (
        request as proxy_request,
    )

    mock_ckpt_store = MagicMock()
    mock_ckpt_store.get_checkpoint_detail.return_value = {
        "group_id": "123",
        "date_str": "2026-09-26",
        "stage_name": "CLEAN_MESSAGES",
        "raw_payload": {"cleaned_count": 10},
    }

    mock_svc = MagicMock()
    mock_svc.checkpoint_store = mock_ckpt_store
    data_routes = DataManagementRoutes(
        trace_store=mock_trace_store,
        analysis_service=mock_svc,
    )

    # 1. 测试 Checkpoint Detail 查询解析
    mock_target = MagicMock()
    mock_target.query = PluginMultiDict(
        [
            ("group_id", "123"),
            ("date_str", "2026-09-26"),
            ("stage_name", "CLEAN_MESSAGES"),
            ("trace_id", "tr_1"),
        ]
    )

    with patch.object(proxy_request, "_get_target", return_value=mock_target):
        res = await data_routes.api_get_checkpoint_detail()
        assert res.get("status_code", 200) == 200
        body = (
            res.get("data")
            if isinstance(res.get("data"), dict) and "status" in res.get("data", {})
            else res
        )
        assert body.get("status") == "ok"
        detail_data = body.get("data") or body.get("detail")
        assert detail_data is not None
        assert detail_data["group_id"] == "123"

    # 2. 测试 Report Content 查询解析
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "report_123_20260926_120000.jpg"
    report_file.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_content")

    report_routes = ReportRoutes(
        trace_store=mock_trace_store,
        analysis_service=None,
        report_output_dir=reports_dir,
    )

    mock_report_target = MagicMock()
    mock_report_target.query = PluginMultiDict([("filename", report_file.name)])

    with patch.object(proxy_request, "_get_target", return_value=mock_report_target):
        res = await report_routes.api_get_report_content()
        assert res.get("status_code", 200) == 200
        body = (
            res.get("data")
            if isinstance(res.get("data"), dict) and "status" in res.get("data", {})
            else res
        )
        assert body.get("status") == "ok"
        report_data = body.get("data")
        assert report_data is not None
        assert report_data["filename"] == report_file.name
        assert "data_url" in report_data


@pytest.mark.asyncio
async def test_trace_and_log_routes_query_resilience(
    mock_trace_store: TraceSQLiteStore, mock_active_mgr: ActiveTaskManager
):
    """测试 TraceRoutes 与 LogRoutes 针对空字符串、异常数字与 PluginMultiDict 的高容错性"""
    from astrbot.api.web import PluginMultiDict
    from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.web_compat import (
        request as proxy_request,
    )

    mock_context = MagicMock()
    mock_context.platform_manager = None
    mock_context.persona_manager = None
    mock_svc = MagicMock()

    trace_routes = TraceRoutes(
        context=mock_context,
        trace_store=mock_trace_store,
        active_task_manager=mock_active_mgr,
        analysis_service=mock_svc,
    )

    mock_trace_target = MagicMock()
    mock_trace_target.query = PluginMultiDict(
        [
            ("limit", ""),
            ("offset", ""),
            ("group_id", ""),
            ("status", ""),
            ("trigger_type", ""),
            ("search", ""),
            ("start_time", ""),
            ("end_time", ""),
            ("granularity", "invalid_val"),
            ("range_count", ""),
        ]
    )

    with patch.object(proxy_request, "_get_target", return_value=mock_trace_target):
        res = await trace_routes.api_list_traces()
        assert res.get("status_code", 200) == 200
        trends_res = await trace_routes.api_get_analytics_trends()
        assert trends_res.get("status_code", 200) == 200

    log_routes = LogRoutes(active_task_manager=mock_active_mgr)
    mock_log_target = MagicMock()
    mock_log_target.query = PluginMultiDict(
        [("limit", ""), ("offset", ""), ("level", ""), ("search", "")]
    )
    with patch.object(proxy_request, "_get_target", return_value=mock_log_target):
        logs_res = await log_routes.api_get_plugin_logs()
        assert logs_res.get("status_code", 200) == 200


@pytest.mark.asyncio
async def test_incremental_and_checkpoint_routes_resilience(
    mock_trace_store: TraceSQLiteStore,
):
    """测试 DataManagementRoutes 增量批次与 Checkpoint 列表在空值与多值参数下的容错性"""
    from astrbot.api.web import PluginMultiDict
    from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.web_compat import (
        request as proxy_request,
    )

    mock_ckpt_store = MagicMock()
    mock_ckpt_store.list_all_checkpoints.return_value = ([], 0)
    mock_inc_store = AsyncMock()
    mock_inc_store.get_all_batches_with_details.return_value = []
    mock_inc_store.get_last_analyzed_cursor.return_value = (None, set())

    mock_svc = MagicMock()
    mock_svc.checkpoint_store = mock_ckpt_store
    mock_svc.incremental_store = mock_inc_store

    data_routes = DataManagementRoutes(
        trace_store=mock_trace_store,
        analysis_service=mock_svc,
    )

    # 1. 批次列表空群号与正常群号
    mock_inc_target = MagicMock()
    mock_inc_target.query = PluginMultiDict([("group_id", "group_999")])
    with patch.object(proxy_request, "_get_target", return_value=mock_inc_target):
        inc_res = await data_routes.api_get_incremental_batches()
        assert inc_res.get("status_code", 200) == 200

    # 2. Checkpoints 列表带有空筛选字段
    mock_ckpt_target = MagicMock()
    mock_ckpt_target.query = PluginMultiDict(
        [("limit", ""), ("offset", ""), ("group_id", ""), ("date_str", "")]
    )
    with patch.object(proxy_request, "_get_target", return_value=mock_ckpt_target):
        ckpt_res = await data_routes.api_list_checkpoints()
        assert ckpt_res.get("status_code", 200) == 200


@pytest.mark.asyncio
async def test_report_routes_subdirectory_support(
    mock_trace_store: TraceSQLiteStore, tmp_path
):
    """测试 ReportRoutes 递归扫描子目录中的 HTML 报告与预览读取"""
    from astrbot.api.web import PluginMultiDict
    from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.web_compat import (
        request as proxy_request,
    )

    reports_dir = tmp_path / "reports"
    sub_dir = reports_dir / "344184506"
    sub_dir.mkdir(parents=True, exist_ok=True)
    report_file = sub_dir / "20261005.html"
    report_file.write_text("<html>hello</html>", encoding="utf-8")

    report_routes = ReportRoutes(
        trace_store=mock_trace_store,
        analysis_service=None,
        report_output_dir=reports_dir,
    )

    # 1. 列表能发现子目录中的报告，且群号识别为父目录名
    res = await report_routes.api_get_report_history()
    body = (
        res.get("data")
        if isinstance(res.get("data"), dict) and "status" in res.get("data", {})
        else res
    )
    assert body.get("status") == "ok"
    data_payload = body.get("data", {})
    items = (
        data_payload.get("items") if isinstance(data_payload, dict) else data_payload
    )
    assert len(items) == 1
    assert items[0]["filename"] == "20261005.html"
    assert items[0]["group_id"] == "344184506"

    # 2. 预览能正确定位到子目录中的文件
    mock_target = MagicMock()
    mock_target.query = PluginMultiDict([("filename", "20261005.html")])
    with patch.object(proxy_request, "_get_target", return_value=mock_target):
        content_res = await report_routes.api_get_report_content()
        c_body = (
            content_res.get("data")
            if isinstance(content_res.get("data"), dict)
            and "status" in content_res.get("data", {})
            else content_res
        )
        assert c_body.get("status") == "ok"
        assert c_body["data"]["html_content"] == "<html>hello</html>"


@pytest.mark.asyncio
async def test_report_routes_database_first_querying_and_migration(
    mock_trace_store: TraceSQLiteStore, tmp_path
):
    """测试 ReportRoutes 优先从 report_artifacts 表极速拉取并关联 trace_id，且支持分页"""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "report_112233_20261005.html"
    report_file.write_text("<html>fast</html>", encoding="utf-8")

    # 手动登记入库
    mock_trace_store.register_report_artifact(
        filename="report_112233_20261005.html",
        group_id="112233",
        file_format="html",
        relative_path="report_112233_20261005.html",
        created_at=1700000000.0,
        trace_id="trace_target_test",
    )

    report_routes = ReportRoutes(
        trace_store=mock_trace_store,
        analysis_service=None,
        report_output_dir=reports_dir,
    )

    res = await report_routes.api_get_report_history()
    body = (
        res.get("data")
        if isinstance(res.get("data"), dict) and "status" in res.get("data", {})
        else res
    )
    assert body.get("status") == "ok"
    data_payload = body.get("data", {})
    items = (
        data_payload.get("items") if isinstance(data_payload, dict) else data_payload
    )
    assert data_payload.get("total") == 1
    assert len(items) == 1
    assert items[0]["filename"] == "report_112233_20261005.html"
    assert items[0]["trace_id"] == "trace_target_test"
    assert items[0]["group_id"] == "112233"
    assert items[0]["modified_at"] == 1700000000.0
    assert items[0]["created_at"] == 1700000000.0


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [0, 1, 99])
async def test_report_scan_matches_indexed_pagination(
    tmp_path, mock_trace_store, monkeypatch, offset
):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    for group in ("12345", "67890"):
        for day in (1, 2, 3):
            file = reports_dir / f"report_{group}_2026100{day}.html"
            file.write_text("<html>report</html>", encoding="utf-8")
            import os

            os.utime(file, (day, day))
    route_module = importlib.import_module(ReportRoutes.__module__)
    req = MagicMock(query={"group_id": "12345", "limit": "1", "offset": str(offset)})
    monkeypatch.setattr(route_module, "request", req)
    routes = ReportRoutes(mock_trace_store, None, report_output_dir=reports_dir)
    cold = await routes.api_get_report_history()
    warm = await routes.api_get_report_history()
    for result in (cold, warm):
        body = (
            result.get("data")
            if isinstance(result.get("data"), dict) and "status" in result["data"]
            else result
        )
        assert body["status"] == "ok"
        assert body["data"]["total"] == 3
        items = body["data"]["items"]
        assert len(items) == (0 if offset == 99 else 1)
        if items:
            assert items[0]["group_id"] == "12345"
            assert items[0]["filename"] == f"report_12345_2026100{3 - offset}.html"


@pytest.mark.asyncio
async def test_report_scan_applies_search_before_pagination(
    tmp_path, mock_trace_store, monkeypatch
):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    for day in (1, 2):
        (reports_dir / f"report_12345_2026100{day}.html").write_text(
            "report", encoding="utf-8"
        )
    route_module = importlib.import_module(ReportRoutes.__module__)
    monkeypatch.setattr(
        route_module, "request", MagicMock(query={"search": "20261001", "limit": "1"})
    )
    routes = ReportRoutes(mock_trace_store, None, report_output_dir=reports_dir)
    for _ in range(2):
        result = await routes.api_get_report_history()
        body = (
            result.get("data")
            if isinstance(result.get("data"), dict) and "status" in result["data"]
            else result
        )
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["filename"] == "report_12345_20261001.html"
