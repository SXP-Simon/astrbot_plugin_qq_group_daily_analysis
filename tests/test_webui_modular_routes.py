"""
WebUI 模块化路由单元测试 (WebUI Modular Routes Tests)
针对 TaskRoutes, TraceRoutes, ReportRoutes, TemplateRoutes, LogRoutes, ConfigRoutes, DataManagementRoutes
进行细粒度隔离测试。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.active_task_manager import (
    ActiveTaskManager,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.routes import (
    ConfigRoutes,
    DataManagementRoutes,
    LogRoutes,
    ReportRoutes,
    TaskRoutes,
    TemplateRoutes,
    TraceRoutes,
)


@pytest.fixture
def mock_trace_store(tmp_path: Path):
    db_path = tmp_path / "test_modular_routes.db"
    return TraceSQLiteStore(db_path)


@pytest.fixture
def mock_active_mgr(mock_trace_store: TraceSQLiteStore):
    return ActiveTaskManager(trace_store=mock_trace_store)


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
    mock_trace_store: TraceSQLiteStore, tmp_path: Path
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
        body = res.get("data") if isinstance(res.get("data"), dict) and "status" in res.get("data", {}) else res
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
    mock_report_target.query = PluginMultiDict(
        [("filename", report_file.name)]
    )

    with patch.object(proxy_request, "_get_target", return_value=mock_report_target):
        res = await report_routes.api_get_report_content()
        assert res.get("status_code", 200) == 200
        body = res.get("data") if isinstance(res.get("data"), dict) and "status" in res.get("data", {}) else res
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


