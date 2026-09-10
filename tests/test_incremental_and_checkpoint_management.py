"""
增量分析批次管理与 Checkpoint 快照观测 CRUD 单元测试套件
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.models.data_models import (
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
)
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge


class DummyPluginKV:
    """模拟 AstrBot 插件 KV 存储引擎"""

    def __init__(self):
        self._kv: dict[str, Any] = {}

    async def get_kv_data(self, key: str, default: Any = None) -> Any:
        return self._kv.get(key, default)

    async def put_kv_data(self, key: str, value: Any) -> None:
        if value is None:
            self._kv.pop(key, None)
        else:
            self._kv[key] = value


@pytest.fixture
def dummy_plugin_kv():
    return DummyPluginKV()


@pytest.fixture
def temp_db(tmp_path: Path):
    return tmp_path / "test_traces_and_checkpoints.db"


@pytest.mark.asyncio
async def test_incremental_store_crud_and_registration(dummy_plugin_kv: DummyPluginKV):
    """验证 IncrementalStore 的批次保存、注册、详情读取、单点删除和一键重置"""
    store = IncrementalStore(dummy_plugin_kv)

    # 1. 初始状态
    assert await store.get_tracked_groups() == []
    assert await store.get_batch_count("group_123") == 0

    # 2. 保存批次
    batch1 = IncrementalBatch(
        batch_id="batch_001",
        group_id="group_123",
        timestamp=time.time() - 3600,
        messages_count=50,
        characters_count=300,
        topics=[
            {
                "topic": "架构讨论",
                "detail": "讨论了系统架构设计",
                "contributors": ["Alice"],
            }
        ],
        token_usage={
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
        user_stats={"u1": {"name": "Alice", "message_count": 50}},
        participant_ids=["u1"],
    )
    batch2 = IncrementalBatch(
        batch_id="batch_002",
        group_id="group_123",
        timestamp=time.time() - 1800,
        messages_count=30,
        characters_count=150,
        topics=[
            {
                "topic": "午餐闲聊",
                "detail": "午餐吃什么讨论",
                "contributors": ["Bob"],
            }
        ],
        token_usage={
            "prompt_tokens": 80,
            "completion_tokens": 15,
            "total_tokens": 95,
        },
        user_stats={"u2": {"name": "Bob", "message_count": 30}},
        participant_ids=["u2"],
    )

    assert await store.save_batch(batch1) is True
    assert await store.save_batch(batch2) is True
    assert await store.get_tracked_groups() == ["group_123"]
    assert await store.get_batch_count("group_123") == 2

    # 3. 获取详情与列表
    detail1 = await store.get_batch_detail("group_123", "batch_001")
    assert detail1 is not None
    assert detail1.batch_id == "batch_001"
    assert detail1.messages_count == 50
    assert len(detail1.topics) == 1
    assert detail1.topics[0]["topic"] == "架构讨论"

    batch_list = await store.get_all_batches_with_details("group_123")
    assert len(batch_list) == 2
    # 按时间倒序
    assert batch_list[0]["batch_id"] == "batch_002"
    assert batch_list[1]["batch_id"] == "batch_001"

    # 4. 更新游标并检查
    await store.update_last_analyzed_cursor(
        "group_123", 1725960000, {"msg_1", "msg_2"}
    )
    ts, ids = await store.get_last_analyzed_cursor("group_123")
    assert ts == 1725960000
    assert ids == {"msg_1", "msg_2"}

    # 5. 单点删除批次 1
    deleted = await store.delete_batch("group_123", "batch_001")
    assert deleted is True
    assert await store.get_batch_count("group_123") == 1
    assert await store.get_batch_detail("group_123", "batch_001") is None
    # 再次删除应返回 False
    assert await store.delete_batch("group_123", "batch_001") is False

    # 6. 一键重置群增量数据
    reset_count = await store.reset_group("group_123")
    assert reset_count == 1
    assert await store.get_batch_count("group_123") == 0
    assert await store.get_batch_detail("group_123", "batch_002") is None
    ts_reset, ids_reset = await store.get_last_analyzed_cursor("group_123")
    assert ts_reset == 0
    assert len(ids_reset) == 0


def test_checkpoint_store_crud_and_filtering(temp_db: Path):
    """验证 CheckpointStore 的保存、列表过滤、详情读取与单点删除"""
    store = CheckpointStore(temp_db)

    # 1. 保存两个不同阶段与群的 Checkpoint
    store.save_checkpoint(
        group_id="group_A",
        date_str="2026-09-10",
        stage_name="CLEAN_MESSAGES",
        data={"cleaned_count": 100, "user_count": 10},
    )
    store.save_checkpoint(
        group_id="group_A",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"topics": ["测试话题1"], "titles": ["测试头衔1"]},
    )
    store.save_checkpoint(
        group_id="group_B",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"topics": ["群B话题"]},
    )

    # 2. 检查去重群组列表
    groups = store.get_distinct_checkpoint_groups()
    assert "group_A" in groups
    assert "group_B" in groups

    # 3. 条件分页查询
    all_items, total = store.list_all_checkpoints(limit=10)
    assert total == 3
    assert len(all_items) == 3

    # 按 group_id 过滤
    a_items, a_total = store.list_all_checkpoints(group_id="group_A")
    assert a_total == 2
    assert len(a_items) == 2

    # 按 stage_name 过滤
    llm_items, llm_total = store.list_all_checkpoints(stage_name="LLM_ANALYSIS")
    assert llm_total == 2

    # 4. 获取单个 Checkpoint 详情与产物 JSON
    detail = store.get_checkpoint_detail("group_A", "2026-09-10", "LLM_ANALYSIS")
    assert detail is not None
    assert detail["group_id"] == "group_A"
    assert detail["stage_name"] == "LLM_ANALYSIS"
    assert detail["data"]["topics"] == ["测试话题1"]

    # 5. 单点删除阶段快照
    assert store.delete_checkpoint("group_A", "2026-09-10", "CLEAN_MESSAGES") is True
    assert store.get_checkpoint("group_A", "2026-09-10", "CLEAN_MESSAGES") is None
    # 另一个阶段快照仍然完好
    assert store.get_checkpoint("group_A", "2026-09-10", "LLM_ANALYSIS") is not None

    # 6. 清除群当天的所有快照
    store.clear_checkpoints("group_A", "2026-09-10")
    assert store.get_checkpoint("group_A", "2026-09-10", "LLM_ANALYSIS") is None


@pytest.mark.asyncio
async def test_plugin_webui_bridge_incremental_and_checkpoint_apis(
    dummy_plugin_kv: DummyPluginKV, temp_db: Path
):
    """验证 WebUI Bridge 的增量批次与 Checkpoint 管理 REST API 端点"""
    trace_store = TraceSQLiteStore(temp_db)
    chk_store = CheckpointStore(temp_db)
    incr_store = IncrementalStore(dummy_plugin_kv)

    # 准备测试数据
    await incr_store.save_batch(
        IncrementalBatch(
            batch_id="b_test_1",
            group_id="10001",
            timestamp=time.time(),
            messages_count=10,
            topics=[],
        )
    )
    await incr_store.update_last_analyzed_cursor("10001", 1725900000, {"m1"})

    chk_store.save_checkpoint(
        group_id="10001",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"result": "ok"},
    )

    mock_analysis_service = MagicMock()
    mock_analysis_service.incremental_store = incr_store
    mock_analysis_service.checkpoint_store = chk_store

    bridge = PluginPageWebUIBridge(
        context=MagicMock(),
        trace_store=trace_store,
        active_task_manager=MagicMock(),
        analysis_service=mock_analysis_service,
    )

    def _unpack(res: Any) -> Any:
        # 兼容 AstrBot json_response fallback 包装
        if isinstance(res, dict) and "data" in res:
            inner = res["data"]
            if isinstance(inner, dict) and "data" in inner:
                return inner["data"]
            return inner
        return res

    # 1. API: get_incremental_groups
    groups_res = await bridge.api_get_incremental_groups()
    assert "10001" in _unpack(groups_res)["groups"]

    # 2. API: get_incremental_batches
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.query = {"group_id": "10001"}
        batches_res = await bridge.api_get_incremental_batches()
        assert batches_res["status_code"] == 200
        data = _unpack(batches_res)
        assert len(data["batches"]) == 1
        assert data["cursor"]["timestamp"] == 1725900000

    # 3. API: get_incremental_batch_detail
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.query = {"group_id": "10001", "batch_id": "b_test_1"}
        detail_res = await bridge.api_get_incremental_batch_detail()
        assert detail_res["status_code"] == 200
        assert _unpack(detail_res)["batch_id"] == "b_test_1"

    # 4. API: delete_incremental_batch
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.json = AsyncMock(
            return_value={"group_id": "10001", "batch_id": "b_test_1"}
        )
        mock_req.query = {}
        del_res = await bridge.api_delete_incremental_batch()
        assert del_res["status_code"] == 200
        assert _unpack(del_res)["deleted"] is True

    # 5. API: reset_incremental_group
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.json = AsyncMock(return_value={"group_id": "10001"})
        mock_req.query = {}
        reset_res = await bridge.api_reset_incremental_group()
        assert reset_res["status_code"] == 200

    # 6. API: list_checkpoints & get_checkpoint_groups
    chk_groups_res = await bridge.api_get_checkpoint_groups()
    assert "10001" in _unpack(chk_groups_res)["groups"]

    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.query = {"group_id": "10001"}
        chk_list_res = await bridge.api_list_checkpoints()
        assert chk_list_res["status_code"] == 200
        assert _unpack(chk_list_res)["total"] == 1

    # 7. API: get_checkpoint_detail
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.query = {
            "group_id": "10001",
            "date_str": "2026-09-10",
            "stage_name": "LLM_ANALYSIS",
        }
        chk_detail_res = await bridge.api_get_checkpoint_detail()
        assert chk_detail_res["status_code"] == 200
        assert _unpack(chk_detail_res)["data"]["result"] == "ok"

    # 8. API: delete_checkpoint
    with patch("src.infrastructure.webui.plugin_page_bridge.request") as mock_req:
        mock_req.json = AsyncMock(
            return_value={
                "group_id": "10001",
                "date_str": "2026-09-10",
                "stage_name": "LLM_ANALYSIS",
            }
        )
        mock_req.query = {}
        chk_del_res = await bridge.api_delete_checkpoint()
        assert chk_del_res["status_code"] == 200
        assert _unpack(chk_del_res)["deleted"] is True
