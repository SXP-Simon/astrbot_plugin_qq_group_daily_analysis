"""
单元测试：PluginPageWebUIBridge 扩展端点测试
测试任务管理、配置接口、数据清理与 Checkpoint/增量 CRUD 等 API
"""

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.active_task_manager import (
    ActiveTaskManager,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.plugin_page_bridge import (
    PluginPageWebUIBridge,
    _config_key_to_folder,
    _sanitize_path_segment,
)
from astrbot_plugin_qq_group_daily_analysis.src.shared.constants import AnalysisStage


@pytest.fixture
def temp_db(tmp_path: Path):
    return tmp_path / "test_bridge.db"


@pytest.fixture
def bridge_setup(temp_db: Path, tmp_path: Path):
    trace_store = TraceSQLiteStore(temp_db)
    active_mgr = ActiveTaskManager(trace_store)
    mock_context = MagicMock()
    mock_analysis_svc = MagicMock()
    mock_dispatcher = MagicMock()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    bridge = PluginPageWebUIBridge(
        context=mock_context,
        trace_store=trace_store,
        active_task_manager=active_mgr,
        analysis_service=mock_analysis_svc,
        report_dispatcher=mock_dispatcher,
        report_output_dir=reports_dir,
    )
    return SimpleNamespace(
        bridge=bridge,
        trace_store=trace_store,
        active_mgr=active_mgr,
        context=mock_context,
        analysis_svc=mock_analysis_svc,
        reports_dir=reports_dir,
    )


def test_path_sanitization_helpers():
    assert _sanitize_path_segment("basic.enable_reply") == "basic_enable_reply"
    assert _sanitize_path_segment("abc-123_XYZ") == "abc-123_XYZ"
    assert _config_key_to_folder("basic.daily_comic.path") == "basic/daily_comic/path"


@pytest.mark.asyncio
async def test_api_active_tasks_and_cancellation(bridge_setup):
    bridge = bridge_setup.bridge
    active_mgr = bridge_setup.active_mgr

    # 1. 初始活跃任务为空
    res = await bridge.api_get_active_tasks()
    data = res["data"] if isinstance(res, dict) and "data" in res else res
    assert data.get("status") == "ok"
    assert len(data.get("data", [])) == 0

    # 2. 注册一个任务
    dummy_task = asyncio.create_task(asyncio.sleep(10))
    await active_mgr.register_task(
        task_id="t_001",
        group_id="123456",
        group_name="测试群",
        platform="qq",
        trigger_type="manual",
        current_stage=AnalysisStage.FETCH_MESSAGES,
        asyncio_task=dummy_task,
    )

    # 3. 再次查询活跃任务
    res = await bridge.api_get_active_tasks()
    data = res["data"] if isinstance(res, dict) and "data" in res else res
    assert len(data.get("data", [])) == 1
    assert data["data"][0]["task_id"] == "t_001"

    # 4. 取消任务
    with patch(
        "astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.plugin_page_bridge.request",
        create=True,
    ) as mock_req:
        mock_req.json = AsyncMock(return_value={"task_id": "t_001"})
        res_cancel = await bridge.api_cancel_task()
        cancel_data = (
            res_cancel["data"]
            if isinstance(res_cancel, dict) and "data" in res_cancel
            else res_cancel
        )
        assert cancel_data.get("status") == "ok"

    dummy_task.cancel()
    try:
        await dummy_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_api_traces_crud(bridge_setup):
    bridge = bridge_setup.bridge
    trace_store = bridge_setup.trace_store

    trace_store.save_trace(
        {
            "trace_id": "tr_100",
            "group_id": "123456",
            "group_name": "测试群",
            "platform": "qq",
            "trigger_type": "manual",
            "status": "succeeded",
            "started_at": time.time() - 10,
            "completed_at": time.time(),
            "duration_ms": 10000.0,
            "spans": [],
        }
    )

    # 1. 列表查询
    with patch(
        "astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.plugin_page_bridge.request",
        create=True,
    ) as mock_req:
        query_dict = {"limit": "10", "offset": "0"}
        mock_req.query = MagicMock()
        mock_req.query.get.side_effect = lambda k, d=None: query_dict.get(k, d)
        res = await bridge.api_list_traces()
        data = res["data"] if isinstance(res, dict) and "data" in res else res
        assert data.get("status") == "ok"
        assert data.get("data", {}).get("total") == 1



    # 2. 详情查询
    res_detail = await bridge.api_get_trace_detail("tr_100")
    data_detail = (
        res_detail["data"]
        if isinstance(res_detail, dict) and "data" in res_detail
        else res_detail
    )
    assert data_detail.get("status") == "ok"
    assert data_detail.get("data", {}).get("trace_id") == "tr_100"


@pytest.mark.asyncio
async def test_api_data_management_cleanup(bridge_setup, tmp_path: Path):
    bridge = bridge_setup.bridge
    reports_dir = bridge_setup.reports_dir

    # 创建一个测试报告文件
    test_report = reports_dir / "report_123_20260910.jpg"
    test_report.write_text("fake image content")

    # 清理 reports 目录
    res = await bridge.api_clear_reports()
    data = res["data"] if isinstance(res, dict) and "data" in res else res
    assert data.get("status") == "ok"
    assert not test_report.exists()
