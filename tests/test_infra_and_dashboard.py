"""
单元测试与自测用例：TraceSQLiteStore, CheckpointStore, TraceContext, ActiveTaskManager, WebUIBridge
"""

import asyncio
import sys
import time
from pathlib import Path

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from src.domain.models.data_models import (
    GoldenQuote,
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.active_task_manager import ActiveTaskManager
from src.shared.trace_context import TraceContext

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


@pytest.fixture
def temp_db(tmp_path: Path):
    return tmp_path / "test_traces.db"


def test_trace_sqlite_store_crud_and_metrics(temp_db: Path):
    store = TraceSQLiteStore(temp_db)

    # 1. 插入一条完整 Trace
    trace_data = {
        "trace_id": "test_trace_001",
        "group_id": "123456",
        "group_name": "测试群A",
        "platform": "qq",
        "trigger_type": "manual",
        "status": "succeeded",
        "started_at": time.time() - 10,
        "completed_at": time.time(),
        "duration_ms": 10000.0,
        "spans": [
            {
                "span_id": "test_trace_001_FETCH",
                "stage_name": "FETCH_MESSAGES",
                "status": "success",
                "started_at": time.time() - 10,
                "duration_ms": 1500.0,
                "payload": {"msg_count": 2000},
            },
            {
                "span_id": "test_trace_001_TOPICS",
                "stage_name": "LLM_TOPICS",
                "status": "success",
                "started_at": time.time() - 8.5,
                "duration_ms": 4000.0,
            },
        ],
        "context_metrics": {
            "raw_message_count": 2000,
            "cleaned_message_count": 1200,
            "compression_ratio": 0.6,
            "incremental_batches": 2,
        },
        "token_usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 1200,
            "total_tokens": 6200,
            "estimated_cost": 0.008,
            "per_analyzer": {"topics": {"total_tokens": 3000}},
        },
    }

    store.save_trace(trace_data)

    # 2. 读取并验证
    retrieved = store.get_trace("test_trace_001")
    assert retrieved is not None
    assert retrieved["trace_id"] == "test_trace_001"
    assert retrieved["group_name"] == "测试群A"
    assert retrieved["status"] == "succeeded"
    assert len(retrieved["spans"]) == 2
    assert retrieved["context_metrics"]["raw_message_count"] == 2000
    assert retrieved["context_metrics"]["compression_ratio"] == 0.6
    assert retrieved["token_usage"]["total_tokens"] == 6200

    # 3. 列表分页查询、时间范围与搜索
    items, total = store.list_traces(
        limit=10,
        search="测试群A",
        start_time=time.time() - 3600,
        end_time=time.time() + 3600,
        sort_by="started_at",
        sort_order="desc",
    )
    assert total == 1
    assert items[0]["trace_id"] == "test_trace_001"
    assert items[0]["total_tokens"] == 6200

    # 3.1 查询群组列表
    groups = store.get_distinct_groups()
    assert len(groups) == 1
    assert groups[0]["group_id"] == "123456"

    # 4. KPI 概览统计
    metrics = store.get_metrics_summary()
    assert metrics["total_traces"] == 1
    assert metrics["succeeded_count"] == 1
    assert metrics["failed_count"] == 0
    assert metrics["total_tokens_spent"] == 6200
    assert metrics["success_rate"] == 100.0


def test_trace_startup_crash_reconciliation(temp_db: Path):
    store = TraceSQLiteStore(temp_db)

    # 插入一条处于 running 状态的未完成任务（模拟进程掉电）
    store.save_trace(
        {
            "trace_id": "crashed_job_001",
            "group_id": "777",
            "group_name": "崩溃群",
            "status": "running",
            "started_at": time.time() - 100,
        }
    )

    # 开机自愈对账扫描
    reconciled = store.reconcile_crashed_traces_on_startup()
    assert reconciled == 1

    # 校验已被自动修正为 aborted，并带上崩溃自愈元数据
    trace = store.get_trace("crashed_job_001")
    assert trace is not None
    assert trace["status"] == "aborted"
    assert trace["error_stage"] == "CRASH_RECOVERY"
    assert "开机已自动回收" in trace["error_message"]


def test_checkpoint_store(temp_db: Path):
    store = CheckpointStore(temp_db)

    # 1. 保存阶段产物
    topics_data = {"topics": ["AI开发", "Python3.12"]}
    store.save_checkpoint("group_101", "2026-08-25", "topics", topics_data)

    # 2. 读取
    cached = store.get_checkpoint("group_101", "2026-08-25", "topics")
    assert cached == topics_data

    # 3. 未命中
    assert store.get_checkpoint("group_101", "2026-08-25", "quotes") is None

    # 4. 清理
    store.clear_checkpoints("group_101", "2026-08-25")
    assert store.get_checkpoint("group_101", "2026-08-25", "topics") is None


def test_trace_context_spans_and_auto_persistence(temp_db: Path):
    store = TraceSQLiteStore(temp_db)
    TraceContext.set_global_store(store)

    ctx = TraceContext(
        trace_id="auto_save_001",
        group_id="88888",
        group_name="自动保存群",
        platform="telegram",
    )

    with ctx:
        with ctx.span("FETCH_STAGE", {"count": 100}):
            time.sleep(0.01)

        ctx.set_context_metrics(raw_message_count=500, cleaned_message_count=250)
        ctx.add_token_usage(
            prompt_tokens=1000, completion_tokens=200, analyzer_name="topics"
        )

    # 退出上下文后应自动调用 finish 并持久化入库
    saved = store.get_trace("auto_save_001")
    assert saved is not None
    assert saved["status"] == "succeeded"
    assert len(saved["spans"]) == 1
    assert saved["spans"][0]["stage_name"] == "FETCH_STAGE"
    assert saved["context_metrics"]["compression_ratio"] == 0.5
    assert saved["token_usage"]["total_tokens"] == 1200


@pytest.mark.asyncio
async def test_active_task_manager_and_reaper(temp_db: Path):
    store = TraceSQLiteStore(temp_db)
    manager = ActiveTaskManager(trace_store=store)

    # 1. 注册任务
    async def dummy_job():
        await asyncio.sleep(5)

    task_coro = asyncio.create_task(dummy_job())
    await manager.register_task(
        task_id="active_001",
        group_id="999",
        group_name="活跃群",
        current_stage="FETCH_MESSAGES",
        asyncio_task=task_coro,
    )

    active = manager.get_active_tasks()
    assert len(active) == 1
    assert active[0]["task_id"] == "active_001"
    assert active[0]["current_stage"] == "FETCH_MESSAGES"

    # 2. 更新进度
    await manager.update_stage("active_001", "LLM_ANALYSIS")
    active_updated = manager.get_active_tasks()
    assert active_updated[0]["current_stage"] == "LLM_ANALYSIS"

    # 3. 取消
    canceled = await manager.cancel_task("active_001")
    assert canceled is True
    assert len(manager.get_active_tasks()) == 0
    await asyncio.sleep(0.01)
    assert task_coro.cancelled()

    # 检查数据库状态被标记为 aborted
    aborted_trace = store.get_trace("active_001")
    assert aborted_trace is not None
    assert aborted_trace["status"] == "aborted"


@pytest.mark.asyncio
async def test_rerender_report_using_checkpoint(temp_db: Path, tmp_path: Path):
    from unittest.mock import AsyncMock, MagicMock
    from src.application.services.analysis_application_service import AnalysisApplicationService
    from src.domain.models.data_models import GroupStatistics, SummaryTopic, UserTitle, TokenUsage

    chk_store = CheckpointStore(temp_db)

    # 1. 模拟一个分析结果并存入 checkpoint
    stats = GroupStatistics(
        message_count=100,
        total_characters=500,
        participant_count=10,
        most_active_period="20:00",
        golden_quotes=[],
        emoji_count=5,
        token_usage=TokenUsage(total_tokens=500),
    )
    topics = [SummaryTopic(topic="测试话题A", contributors=["测试用户"], detail="话题详情")]
    user_titles = [UserTitle(name="测试用户", user_id="123", title="水群王", mbti="INTJ", reason="经常水群")]
    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "user_analysis": {"123": {"message_count": 50}},
        "chat_quality_review": None,
    }

    mock_report_gen = MagicMock()
    mock_report_gen.data_dir = tmp_path
    mock_report_gen.generate_image_report = AsyncMock(return_value=(str(tmp_path / "temp.jpg"), None))
    mock_report_gen.html_templates = MagicMock()
    mock_report_gen.html_templates.render_template = MagicMock(
        return_value="<html>测试报告</html>"
    )
    mock_report_gen.generate_html_report = AsyncMock(
        return_value=(str(tmp_path / "temp.html"), None)
    )
    (tmp_path / "temp.html").write_text("<html>测试报告</html>", encoding="utf-8")
    (tmp_path / "temp.jpg").write_bytes(b"image_content")

    mock_config = MagicMock()
    mock_config.get_data_dir = MagicMock(return_value=tmp_path)
    mock_config.get_llm_max_concurrent = MagicMock(return_value=1)
    mock_config.get_topic_analysis_enabled = MagicMock(return_value=True)
    mock_config.get_user_title_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_golden_quote_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_chat_quality_analysis_enabled = MagicMock(return_value=False)

    service = AnalysisApplicationService(
        config_manager=mock_config,
        bot_manager=MagicMock(),
        history_manager=MagicMock(),
        report_generator=mock_report_gen,
        llm_analyzer=MagicMock(),
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
        checkpoint_store=chk_store,
        html_render=AsyncMock(return_value=str(tmp_path / "temp.jpg")),
    )

    # 保存快照
    chk_store.save_checkpoint(
        group_id="12345",
        date_str="2026-08-26",
        stage_name="LLM_ANALYSIS",
        data=service._serialize_analysis_result(analysis_result),
    )

    # 2. 执行免 Token 重新渲染 (图片，传入 trace_id)
    img_res = await service.rerender_report(
        group_id="12345",
        date_str="2026-08-26",
        template_name="ATRI",
        render_format="image",
        trace_id="test_trace_rerender_001",
    )
    assert img_res["success"] is True
    assert img_res["from_checkpoint"] is True
    assert "test_trace_rerender_001" in img_res["filename"]
    assert "ATRI" in img_res["filename"]
    assert mock_report_gen.generate_image_report.called

    # 3. 执行免 Token 重新渲染 (HTML，传入 trace_id)
    html_res = await service.rerender_report(
        group_id="12345",
        date_str="2026-08-26",
        template_name="BlueArchive",
        render_format="html",
        trace_id="test_trace_rerender_001",
    )
    assert html_res["success"] is True
    assert html_res["is_html"] is True
    assert "test_trace_rerender_001" in html_res["filename"]
    assert "BlueArchive" in html_res["filename"]
    assert mock_report_gen.generate_html_report.called


@pytest.mark.asyncio
async def test_resume_analysis_using_checkpoint(temp_db: Path, tmp_path: Path):
    chk_store = CheckpointStore(temp_db)

    # 1. 保存前置清洗产物快照
    chk_store.save_checkpoint(
        group_id="88888",
        date_str="2026-08-26",
        stage_name="CLEAN_MESSAGES",
        data={
            "group_id": "88888",
            "date_str": "2026-08-26",
            "statistics": {
                "message_count": 100,
                "total_characters": 500,
                "participant_count": 10,
                "most_active_period": "20:00-21:00",
                "golden_quotes": [],
                "emoji_count": 5,
            },
            "user_activity": {},
            "top_users": [],
            "unified_messages": [],
        },
    )

    mock_llm = MagicMock()
    mock_llm.analyze_all_concurrent = AsyncMock(
        return_value=(
            [SummaryTopic(topic="断点续跑话题", detail="续跑测试", contributors=["用户A"])],
            [],
            [],
            TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
            None,
        )
    )

    mock_adapter = MagicMock()
    mock_bot_mgr = MagicMock()
    mock_bot_mgr.get_adapter = MagicMock(return_value=mock_adapter)

    mock_config = MagicMock()
    mock_config.get_llm_max_concurrent = MagicMock(return_value=1)
    mock_config.get_topic_analysis_enabled = MagicMock(return_value=True)
    mock_config.get_user_title_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_golden_quote_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_chat_quality_analysis_enabled = MagicMock(return_value=False)

    mock_history = MagicMock()
    mock_history.save_analysis = AsyncMock()

    service = AnalysisApplicationService(
        config_manager=mock_config,
        bot_manager=mock_bot_mgr,
        history_manager=mock_history,
        report_generator=MagicMock(),
        llm_analyzer=mock_llm,
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
        checkpoint_store=chk_store,
    )

    # 2. 执行断点续跑
    res = await service.resume_analysis(
        trace_id="trace_resume_test_001",
        group_id="88888",
        date_str="2026-08-26",
    )

    assert res["success"] is True
    assert res["resumed_from"] == "CLEAN_MESSAGES"
    assert len(res["analysis_result"]["topics"]) == 1
    assert res["analysis_result"]["topics"][0].topic == "断点续跑话题"
    assert mock_llm.analyze_all_concurrent.called


@pytest.mark.asyncio
async def test_resume_analysis_reuses_existing_subtasks(temp_db: Path, tmp_path: Path):
    """验证当已有部分成功子任务时，续跑自动复用已有产物且不重复请求大模型。"""
    chk_store = CheckpointStore(temp_db)

    # 1. 保存前置清洗产物
    chk_store.save_checkpoint(
        group_id="99999",
        date_str="2026-08-26",
        stage_name="CLEAN_MESSAGES",
        data={
            "group_id": "99999",
            "date_str": "2026-08-26",
            "statistics": {
                "message_count": 50,
                "total_characters": 200,
                "participant_count": 5,
                "most_active_period": "18:00-19:00",
                "golden_quotes": [],
                "emoji_count": 2,
            },
            "user_activity": {},
            "top_users": [],
            "unified_messages": [],
        },
    )

    # 2. 模拟话题已成功生成，但金句尚未生成的历史快照
    chk_store.save_checkpoint(
        group_id="99999",
        date_str="2026-08-26",
        stage_name="LLM_ANALYSIS",
        data={
            "topics": [
                {
                    "topic": "已复用的话题",
                    "detail": "无需重新请求LLM",
                    "contributors": ["用户B"],
                }
            ],
            "user_titles": [],
            "statistics": {
                "golden_quotes": [],
                "token_usage": {"total_tokens": 150},
            },
        },
    )

    mock_llm = MagicMock()
    # 模拟金句补充生成
    mock_llm.analyze_all_concurrent = AsyncMock(
        return_value=(
            [],
            [],
            [GoldenQuote(content="新增金句", sender="用户C", reason="语境")],
            TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
            None,
        )
    )

    mock_bot_mgr = MagicMock()
    mock_bot_mgr.get_adapter = MagicMock(return_value=MagicMock())

    mock_config = MagicMock()
    mock_config.get_llm_max_concurrent = MagicMock(return_value=1)
    mock_config.get_topic_analysis_enabled = MagicMock(return_value=True)
    mock_config.get_user_title_analysis_enabled = MagicMock(return_value=False)
    mock_config.get_golden_quote_analysis_enabled = MagicMock(return_value=True)
    mock_config.get_chat_quality_analysis_enabled = MagicMock(return_value=False)

    service = AnalysisApplicationService(
        config_manager=mock_config,
        bot_manager=mock_bot_mgr,
        history_manager=MagicMock(save_analysis=AsyncMock()),
        report_generator=MagicMock(),
        llm_analyzer=mock_llm,
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
        checkpoint_store=chk_store,
    )

    res = await service.resume_analysis(
        trace_id="trace_resume_partial_001",
        group_id="99999",
        date_str="2026-08-26",
    )

    assert res["success"] is True
    # 验证话题直接复用了历史快照
    assert len(res["analysis_result"]["topics"]) == 1
    assert res["analysis_result"]["topics"][0].topic == "已复用的话题"
    # 验证金句补充成功
    assert len(res["analysis_result"]["statistics"].golden_quotes) == 1
    assert res["analysis_result"]["statistics"].golden_quotes[0].content == "新增金句"

    # 关键断言：analyze_all_concurrent 传入的 topic_enabled 必须为 False（话题无需重跑）
    call_kwargs = mock_llm.analyze_all_concurrent.call_args.kwargs
    assert call_kwargs["topic_enabled"] is False
    assert call_kwargs["golden_quote_enabled"] is True


def test_activity_visualizer_and_checkpoint_deserialization_hourly_activity(temp_db: Path):
    """验证从 Checkpoint (JSON 字符串键) 恢复时，活跃度图表数据能够正确解析而不为空。"""
    from src.infrastructure.visualization.activity_charts import ActivityVisualizer
    from src.domain.models.data_models import ActivityVisualization, GroupStatistics

    viz = ActivityVisualizer()

    # 1. 模拟 JSON 序列化后的 string keys: {"0": 10, "1": 25, "12": 50}
    raw_hourly_str = {"0": 10, "1": 25, "12": 50}
    chart_data = viz.get_hourly_chart_data(raw_hourly_str)
    assert len(chart_data) == 24
    # 验证 0点，1点，12点 的活跃数据正确解析出非零数值
    assert chart_data[0]["count"] == 10
    assert chart_data[1]["count"] == 25
    assert chart_data[12]["count"] == 50
    assert chart_data[12]["percentage"] == 100.0
    assert chart_data[2]["count"] == 0

    # 2. 验证 ApplicationService 反序列化时自动将 hourly_activity key 还原为 int
    service = AnalysisApplicationService(
        config_manager=MagicMock(),
        bot_manager=MagicMock(),
        history_manager=MagicMock(),
        report_generator=MagicMock(),
        llm_analyzer=MagicMock(),
        statistics_service=MagicMock(),
        analysis_domain_service=MagicMock(),
        checkpoint_store=CheckpointStore(temp_db),
    )

    serialized_data = {
        "statistics": {
            "message_count": 85,
            "total_characters": 500,
            "participant_count": 5,
            "activity_visualization": {
                "hourly_activity": {"0": 10, "1": 25, "12": 50},
                "daily_activity": {},
            },
        },
        "topics": [],
        "user_titles": [],
    }

    deserialized = service._deserialize_analysis_result(serialized_data)
    stats: GroupStatistics = deserialized["statistics"]
    assert isinstance(stats.activity_visualization, ActivityVisualization)
    assert stats.activity_visualization.hourly_activity.get(12) == 50
    assert stats.activity_visualization.hourly_activity.get(0) == 10


@pytest.mark.asyncio
async def test_report_dispatcher_span_tracking():
    """验证 ReportDispatcher 分发时自动记录 DISPATCH_REPORT span 的丰富元数据。"""
    from src.infrastructure.reporting.dispatcher import ReportDispatcher

    trace = TraceContext.set(
        trace_id="test_dispatch_span_001",
        group_id="123456",
        trigger_type="manual",
    )

    mock_config = MagicMock()
    mock_config.get_output_format = MagicMock(return_value=["image"])
    mock_config.get_show_report_caption = MagicMock(return_value=True)

    mock_rep_gen = MagicMock()
    mock_rep_gen.data_dir = Path("./tmp")
    mock_rep_gen.generate_image_report = AsyncMock(return_value=("base64://dGVzdA==", "<html></html>"))

    mock_msg_sender = MagicMock()
    mock_msg_sender.bot_manager = MagicMock(get_adapter=MagicMock(return_value=None))
    mock_msg_sender.send_image_smart = AsyncMock(return_value=True)

    dispatcher = ReportDispatcher(
        config_manager=mock_config,
        report_generator=mock_rep_gen,
        message_sender=mock_msg_sender,
    )
    dispatcher._html_render_func = MagicMock()

    sent = await dispatcher.dispatch(
        group_id="123456",
        analysis_result={"statistics": MagicMock(), "topics": [], "user_titles": []},
        platform_id="qq",
    )

    assert sent is True
    # 验证 trace spans 中包含了 DISPATCH_REPORT 阶段且包含丰富 payload
    dispatch_spans = [s for s in trace._spans if s["stage_name"] == "DISPATCH_REPORT"]
    assert len(dispatch_spans) >= 1
    p = dispatch_spans[0].get("payload", {})
    assert p.get("platform") == "qq"
    assert p.get("success") is True
    assert p.get("image_sent") is True
    assert "image" in p.get("formats", [])


def test_get_available_templates_dynamic_discovery(tmp_path: Path):
    from unittest.mock import MagicMock
    from src.infrastructure.reporting.templates import HTMLTemplates

    # 1. 模拟自定义模板目录
    custom_root = tmp_path / "custom_t2i_templates" / "reporting_templates"
    custom_root.mkdir(parents=True, exist_ok=True)

    # 自定义模板1：带 theme.json 元数据
    theme1_dir = custom_root / "anime_pink"
    theme1_dir.mkdir()
    (theme1_dir / "image_template.html").write_text("<div>Anime</div>", encoding="utf-8")
    (theme1_dir / "theme.json").write_text('{"name": "动漫粉萌 (Anime Pink)"}', encoding="utf-8")

    # 自定义模板2：无元数据的第三方未知模板
    theme2_dir = custom_root / "third_party_cyber"
    theme2_dir.mkdir()
    (theme2_dir / "html_template.html").write_text("<div>Cyber</div>", encoding="utf-8")

    mock_config = MagicMock()
    mock_config.get_report_template = MagicMock(return_value="scrapbook")
    mock_config.get_custom_report_template_dir = MagicMock(
        side_effect=lambda name: (custom_root / name) if name else custom_root
    )

    templates_mgr = HTMLTemplates(mock_config)
    templates = templates_mgr.get_available_templates()

    # 验证内置模板被正确识别
    template_ids = [t["id"] for t in templates]
    assert "scrapbook" in template_ids
    assert "ATRI" in template_ids
    assert "HatsuneMiku" in template_ids
    assert "spring_festival" in template_ids

    # 验证自定义模板被正确识别并优雅处理名称
    assert "anime_pink" in template_ids
    assert "third_party_cyber" in template_ids

    anime_meta = next(t for t in templates if t["id"] == "anime_pink")
    assert anime_meta["is_custom"] is True
    assert anime_meta["label"] == "动漫粉萌 (Anime Pink)"

    cyber_meta = next(t for t in templates if t["id"] == "third_party_cyber")
    assert cyber_meta["is_custom"] is True
    assert "third_party_cyber" in cyber_meta["label"]
    assert "自定义" in cyber_meta["label"]




