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
from src.domain.value_objects import (
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
)
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge
from src.shared.trace_context import TraceContext


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

    # 6. 任务级隔离验证 (trace_id scoped)
    store.save_checkpoint(
        group_id="group_A",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"topics": ["任务1独有话题"]},
        trace_id="trace_task_001",
    )
    store.save_checkpoint(
        group_id="group_A",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"topics": ["任务2独有话题"]},
        trace_id="trace_task_002",
    )

    # 验证两个同日同群同阶段的任务快照互不覆盖
    t1_data = store.get_checkpoint(
        "group_A", "2026-09-10", "LLM_ANALYSIS", trace_id="trace_task_001"
    )
    t2_data = store.get_checkpoint(
        "group_A", "2026-09-10", "LLM_ANALYSIS", trace_id="trace_task_002"
    )
    assert t1_data["topics"] == ["任务1独有话题"]
    assert t2_data["topics"] == ["任务2独有话题"]

    # 7. 清除群当天的所有快照
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


def test_trace_id_generation_anti_collision_and_special_chars():
    """极端情况 1：高并发同毫秒调用 TraceContext.generate 必须绝对唯一，且特殊群名正确清洗"""
    # 1. 模拟同毫秒高频生成 1000 次，必须全部唯一，零碰撞
    trace_ids = {
        TraceContext.generate(prefix="manual", group_name="测试群_A")
        for _ in range(1000)
    }
    assert len(trace_ids) == 1000

    # 2. 极端群名包含各种特殊字符、换行、反斜杠、Unicode 特殊符号
    evil_group_name = "【超级/测试\\群: *?<>|\n\r\t】🔥"
    trace_id_special = TraceContext.generate(prefix="auto", group_name=evil_group_name)
    assert "/" not in trace_id_special
    assert "\\" not in trace_id_special
    assert ":" not in trace_id_special
    assert "\n" not in trace_id_special
    assert trace_id_special.startswith("auto_")


def test_checkpoint_store_corner_cases_expiration_and_fallback(temp_db: Path):
    """极端情况 2：TTL 到期自愈、坏数据/损坏 JSON 容错、老表平滑升级与回退检索"""
    store = CheckpointStore(temp_db)

    # 1. 过期快照 (TTL = 0s) 自动失效
    store.save_checkpoint(
        group_id="exp_group",
        date_str="2026-09-10",
        stage_name="CLEAN_MESSAGES",
        data={"msgs": [1, 2, 3]},
        trace_id="trace_expired_1",
        ttl_seconds=-10,  # 已过期
    )
    assert (
        store.get_checkpoint(
            "exp_group",
            "2026-09-10",
            "CLEAN_MESSAGES",
            trace_id="trace_expired_1",
        )
        is None
    )

    # 2. 坏 JSON 字符串容错返回 None 不抛崩溃异常
    with store._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO stage_checkpoints (
                checkpoint_id, group_id, date_str, stage_name, data_json, created_at, expire_at, trace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "corrupt_id",
                "corrupt_grp",
                "2026-09-10",
                "LLM_ANALYSIS",
                "{corrupt: invalid json string",
                time.time(),
                time.time() + 1000,
                "trace_corrupt",
            ),
        )
    corrupted = store.get_checkpoint(
        "corrupt_grp", "2026-09-10", "LLM_ANALYSIS", trace_id="trace_corrupt"
    )
    assert corrupted is None

    # 3. 兼容历史无 trace_id 的老数据平滑回退读取
    store.save_checkpoint(
        group_id="legacy_grp",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"legacy": True},
        trace_id="",  # 老格式 (trace_id为空)
    )
    # 无 trace_id 读取
    assert store.get_checkpoint("legacy_grp", "2026-09-10", "LLM_ANALYSIS") == {
        "legacy": True
    }
    # 传入新 trace_id 读取也能平滑回退到老格式
    assert store.get_checkpoint(
        "legacy_grp",
        "2026-09-10",
        "LLM_ANALYSIS",
        trace_id="non_exist_trace_id",
    ) == {"legacy": True}

    # 4. 严防跨任务脏读：若存在 Task A 快照，Task B 查找缺失快照时绝不能脏读 Task A 的快照
    store.save_checkpoint(
        group_id="isolated_grp",
        date_str="2026-09-10",
        stage_name="LLM_ANALYSIS",
        data={"task": "task_A"},
        trace_id="trace_task_A",
    )
    # Task B 查询不存在的快照时必须返回 None，不能回退捞取 Task A 的数据
    assert (
        store.get_checkpoint(
            "isolated_grp",
            "2026-09-10",
            "LLM_ANALYSIS",
            trace_id="trace_task_B",
        )
        is None
    )


@pytest.mark.asyncio
async def test_run_incremental_analysis_enforces_days_lookback_boundary(
    dummy_plugin_kv: DummyPluginKV, temp_db: Path
):
    """测试增量分析全链路：当旧游标停留在数天前 (例如周一)，配置为 1 天时，严格受 days 边界约束，绝不过界拉取和分析历史消息。"""
    from src.application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from src.domain.value_objects.unified_message import (
        MessageContent,
        MessageContentType,
        UnifiedMessage,
    )

    now_ts = int(time.time())
    three_days_ago_ts = now_ts - 3 * 86400  # 周一 (3天前)
    two_days_ago_ts = now_ts - 2 * 86400  # 周二 (2天前)
    one_hour_ago_ts = now_ts - 3600  # 周三/今天 (1小时前)

    # 1. 模拟 IncrementalStore 游标停留在 3 天前
    inc_store = IncrementalStore(dummy_plugin_kv)
    await inc_store.update_last_analyzed_cursor(
        "group_999", three_days_ago_ts, ["msg_old_1"]
    )

    mock_config = MagicMock()
    mock_config.get_analysis_days = MagicMock(return_value=1)  # 仅分析 1 天
    mock_config.get_incremental_min_messages = MagicMock(return_value=1)
    mock_config.get_max_messages = MagicMock(return_value=500)
    mock_config.get_filter_bot_messages = MagicMock(return_value=False)
    mock_config.get_bot_self_ids = MagicMock(return_value=[])
    mock_config.get_user_title_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_golden_quote_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_chat_quality_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_topic_analysis_enabled = MagicMock(return_value=True)
    mock_config.get_incremental_topics_per_batch = MagicMock(return_value=3)
    mock_config.get_incremental_quotes_per_batch = MagicMock(return_value=3)
    mock_config.get_group_platform_id = MagicMock(return_value="onebot_test")
    mock_config.get_llm_max_concurrent = MagicMock(return_value=2)
    mock_config.get_llm_queue_timeout = MagicMock(return_value=60)

    # 3. 模拟 Adapter
    mock_adapter = AsyncMock()
    mock_adapter.is_group_muted = AsyncMock(return_value=False)
    fetched_messages = [
        UnifiedMessage(
            message_id="msg_mon",
            sender_id="u1",
            sender_name="User1",
            group_id="group_999",
            timestamp=three_days_ago_ts + 10,
            text_content="周一的话题消息",
            contents=(
                MessageContent(
                    type=MessageContentType.TEXT, text="周一的话题消息"
                ),
            ),
        ),
        UnifiedMessage(
            message_id="msg_tue",
            sender_id="u2",
            sender_name="User2",
            group_id="group_999",
            timestamp=two_days_ago_ts,
            text_content="周二的话题消息",
            contents=(
                MessageContent(
                    type=MessageContentType.TEXT, text="周二的话题消息"
                ),
            ),
        ),
        UnifiedMessage(
            message_id="msg_wed",
            sender_id="u3",
            sender_name="User3",
            group_id="group_999",
            timestamp=one_hour_ago_ts,
            text_content="周三今天的话题消息",
            contents=(
                MessageContent(
                    type=MessageContentType.TEXT, text="周三今天的话题消息"
                ),
            ),
        ),
    ]
    mock_adapter.fetch_messages = AsyncMock(return_value=fetched_messages)

    mock_bot_manager = MagicMock()
    mock_bot_manager.get_adapter = MagicMock(return_value=mock_adapter)

    # 4. 模拟 LLM Analyzer 与 StatisticsService
    mock_llm_analyzer = AsyncMock()
    analyzed_topics = [
        SummaryTopic(
            topic="周三今天的新鲜话题",
            detail="讨论了周三的事情",
            contributors=["User3"],
        )
    ]
    mock_llm_analyzer.analyze_incremental_concurrent = AsyncMock(
        return_value=(
            analyzed_topics,
            [],
            TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            None,
        )
    )

    mock_stat_service = MagicMock()
    mock_stat_service.calculate_group_statistics = MagicMock(
        return_value=GroupStatistics(
            message_count=1,
            total_characters=10,
            participant_count=1,
            most_active_period="12:00-13:00",
            golden_quotes=[],
            emoji_count=0,
        )
    )
    mock_stat_service._convert_to_legacy_dict = MagicMock(
        side_effect=lambda msgs: [
            {"id": m.message_id, "text": m.text_content} for m in msgs
        ]
    )

    mock_domain_service = MagicMock()
    mock_domain_service.analyze_user_activity = MagicMock(return_value={})

    chk_store = CheckpointStore(temp_db)
    service = AnalysisApplicationService(
        config_manager=mock_config,
        bot_manager=mock_bot_manager,
        history_manager=MagicMock(),
        report_generator=MagicMock(),
        llm_analyzer=mock_llm_analyzer,
        statistics_service=mock_stat_service,
        analysis_domain_service=mock_domain_service,
        checkpoint_store=chk_store,
        incremental_store=inc_store,
    )

    # 5. 执行增量分析
    result = await service.execute_incremental_analysis(
        group_id="group_999",
        platform_id="onebot_test",
    )

    # 6. 验证
    assert result["success"] is True
    # 验证 adapter.fetch_messages 的 since_ts 参数被约束在 1 天内
    fetch_call_args = mock_adapter.fetch_messages.call_args
    assert fetch_call_args is not None
    assert (
        fetch_call_args.kwargs["since_ts"] >= now_ts - 86400 - 5
    )  # 允许 5s 运行误差

    # 验证传入统计与转换的消息只有周三的消息 (msg_wed)，周一与周二的消息被严格过滤
    legacy_msgs_passed = (
        mock_stat_service._convert_to_legacy_dict.call_args[0][0]
    )
    assert len(legacy_msgs_passed) == 1
    assert legacy_msgs_passed[0].message_id == "msg_wed"
    assert legacy_msgs_passed[0].text_content == "周三今天的话题消息"


@pytest.mark.asyncio
async def test_incremental_store_query_batches_and_cleanup_cross_days(
    dummy_plugin_kv: DummyPluginKV,
):
    """验证 IncrementalStore 跨天查询与保留期清理：严格按时间窗口检索，清理超出保留期的陈旧批次。"""
    store = IncrementalStore(dummy_plugin_kv)
    now = time.time()
    three_days_ago = now - 3 * 86400  # 周一 (3天前)
    two_days_ago = now - 2 * 86400  # 周二 (2天前)
    one_hour_ago = now - 3600  # 周三/今天 (1小时前)

    # 1. 插入三个不同日期的批次
    batch_mon = IncrementalBatch(
        batch_id="batch_monday",
        group_id="group_multiday",
        timestamp=three_days_ago,
        messages_count=100,
        characters_count=1000,
        topics=[
            {
                "topic": "周一旧话题",
                "detail": "周一内容",
                "contributors": ["Alice"],
            }
        ],
    )
    batch_tue = IncrementalBatch(
        batch_id="batch_tuesday",
        group_id="group_multiday",
        timestamp=two_days_ago,
        messages_count=80,
        characters_count=800,
        topics=[
            {
                "topic": "周二旧话题",
                "detail": "周二内容",
                "contributors": ["Bob"],
            }
        ],
    )
    batch_wed = IncrementalBatch(
        batch_id="batch_wednesday",
        group_id="group_multiday",
        timestamp=one_hour_ago,
        messages_count=50,
        characters_count=500,
        topics=[
            {
                "topic": "周三今天话题",
                "detail": "周三内容",
                "contributors": ["Charlie"],
            }
        ],
    )

    await store.save_batch(batch_mon)
    await store.save_batch(batch_tue)
    await store.save_batch(batch_wed)
    assert await store.get_batch_count("group_multiday") == 3

    # 2. 查询 1 天时间窗口 [now - 86400, now] -> 必须只返回周三当天的批次
    window_start = now - 86400
    window_end = now
    window_batches = await store.query_batches(
        "group_multiday", window_start, window_end
    )
    assert len(window_batches) == 1
    assert window_batches[0].batch_id == "batch_wednesday"
    assert window_batches[0].topics[0]["topic"] == "周三今天话题"

    # 3. 执行过期清理 (清理 2 天前的批次) -> 周一(3天前)批次被清理，周二与周三批次保留
    deleted_count = await store.cleanup_old_batches(
        "group_multiday", before_timestamp=now - 2.5 * 86400
    )
    assert deleted_count == 1
    assert await store.get_batch_count("group_multiday") == 2
    assert await store.get_batch_detail("group_multiday", "batch_monday") is None
    assert (
        await store.get_batch_detail("group_multiday", "batch_tuesday")
        is not None
    )
    assert (
        await store.get_batch_detail("group_multiday", "batch_wednesday")
        is not None
    )


@pytest.mark.asyncio
async def test_incremental_final_report_aggregates_only_in_window_batches(
    dummy_plugin_kv: DummyPluginKV,
):
    """验证最终报告生成阶段：即使存储中残留有历史旧批次，也仅聚合滑动窗口内批次，彻底杜绝历史话题泄漏。"""
    from src.application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from src.domain.services.incremental_merge_service import (
        IncrementalMergeService,
    )

    store = IncrementalStore(dummy_plugin_kv)
    now = time.time()

    # 1. 存储中存在 3 天前的旧批次与 2 小时前的新批次
    batch_old = IncrementalBatch(
        batch_id="batch_old_mon",
        group_id="grp_final_test",
        timestamp=now - 3 * 86400,
        messages_count=100,
        characters_count=1000,
        topics=[
            {
                "topic": "周一已结题旧话题",
                "detail": "旧详情",
                "contributors": ["OldUser"],
            }
        ],
    )
    batch_new = IncrementalBatch(
        batch_id="batch_new_wed",
        group_id="grp_final_test",
        timestamp=now - 7200,
        messages_count=40,
        characters_count=400,
        topics=[
            {
                "topic": "周三今日新鲜事",
                "detail": "新详情",
                "contributors": ["NewUser"],
            }
        ],
    )
    await store.save_batch(batch_old)
    await store.save_batch(batch_new)

    # 2. Mock 配置
    mock_config = MagicMock()
    mock_config.get_analysis_days = MagicMock(return_value=1)  # 仅汇总 1 天
    mock_config.get_user_title_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_golden_quote_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_chat_quality_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_llm_max_concurrent = MagicMock(return_value=2)
    mock_config.get_llm_queue_timeout = MagicMock(return_value=60)
    mock_config.get_max_user_titles = MagicMock(return_value=5)

    mock_adapter = AsyncMock()
    mock_adapter.is_group_muted = AsyncMock(return_value=False)
    mock_bot_manager = MagicMock()
    mock_bot_manager.get_adapter = MagicMock(return_value=mock_adapter)

    mock_history = AsyncMock()

    merge_service = IncrementalMergeService()

    service = AnalysisApplicationService(
        config_manager=mock_config,
        bot_manager=mock_bot_manager,
        history_manager=mock_history,
        report_generator=MagicMock(),
        llm_analyzer=AsyncMock(),
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
        incremental_store=store,
        incremental_merge_service=merge_service,
    )

    # 3. 执行最终报告生成流程
    result = await service.execute_incremental_final_report(
        group_id="grp_final_test", platform_id="onebot"
    )

    # 4. 验证
    assert result["success"] is True
    analysis_result = result["analysis_result"]
    # 验证话题列表中仅包含周三今日新鲜事，完全不包含周一旧话题
    topic_titles = [t.topic for t in analysis_result["topics"]]
    assert "周三今日新鲜事" in topic_titles
    assert "周一已结题旧话题" not in topic_titles
    # 验证消息量仅为周三当天的 40 条
    assert analysis_result["statistics"].message_count == 40




