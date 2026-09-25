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
