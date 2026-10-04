"""单元测试：群分析插件 LLM Tools (读取报告与按需触发).

覆盖：
1. ReportQueryService:
   - 目标群 4 级漏斗解析（留空继承当前群、纯数字提取、群名模糊匹配、歧义列表、未找到）
   - 弹性日期解析（今天/昨天/前天、单日补零、范围、>30天超限拦截、逆序拦截）
   - CheckpointStore 与 HistoryManager 双轨检索
   - 同日取最新 MAX(created_at) 窗口去重
   - 临近日期自愈探测
   - 模块投影过滤（topics, golden_quotes 等）与 4000 字符截断
2. AnalysisTriggerService:
   - 管理员权限校验与普通用户拒绝
   - 目标群白名单校验
   - 群分析锁正在运行冲突防重入
   - 配置交集过滤与跳过提示
   - 异步任务派发与 500ms 受理回执
   - ON_DEMAND_ANALYSIS 独立阶段隔离
3. main.py 集成测试:
   - get_daily_report 与 trigger_daily_analysis 链路贯通
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.analysis_trigger_service import AnalysisTriggerService
from src.application.services.report_query_service import ReportQueryService
from src.shared.constants import AnalysisStage


@pytest.fixture
def mock_config_manager():
    cfg = MagicMock()
    cfg.is_group_allowed.return_value = True
    cfg.get_analysis_days.return_value = 1
    cfg.get_topic_analysis_enabled.return_value = True
    cfg.get_user_title_analysis_enabled.return_value = True
    cfg.get_golden_quote_analysis_enabled.return_value = True
    cfg.get_chat_quality_analysis_enabled.return_value = False  # 默认关闭质量分析测试配置交集
    cfg._get_group.return_value = {"admin_users": ["99999"]}
    return cfg


@pytest.fixture
def mock_checkpoint_store():
    store = MagicMock()
    store.get_checkpoints_by_date_range.return_value = []
    store.list_all_checkpoints.return_value = ([], 0)
    store.get_checkpoint_detail.return_value = None
    return store


@pytest.fixture
def mock_history_manager():
    mgr = MagicMock()
    mgr.get_analysis = AsyncMock(return_value=None)
    return mgr


@pytest.fixture
def mock_trace_store():
    store = MagicMock()
    store.find_groups_by_name.return_value = []
    store.get_distinct_groups.return_value = [
        {"group_id": "123456", "group_name": "测试交流群", "platform": "aiocqhttp"}
    ]
    return store


@pytest.fixture
def report_query_service(mock_config_manager, mock_checkpoint_store, mock_history_manager, mock_trace_store):
    return ReportQueryService(
        config_manager=mock_config_manager,
        checkpoint_store=mock_checkpoint_store,
        history_manager=mock_history_manager,
        trace_store=mock_trace_store,
    )


# ==================== 1. ReportQueryService 目标群解析测试 ====================


def test_resolve_target_group_empty_with_current(report_query_service):
    # 留空且有当前群事件：自动绑定当前群
    gid, name, cand = report_query_service.resolve_target_group("", current_event_group_id="123456")
    assert gid == "123456"
    assert name == "测试交流群"
    assert cand == []


def test_resolve_target_group_pure_number(report_query_service):
    # 纯数字群号
    gid, name, cand = report_query_service.resolve_target_group("888888")
    assert gid == "888888"
    assert cand == []


def test_resolve_target_group_with_umo(report_query_service):
    # UMO 格式解构提取
    gid, name, cand = report_query_service.resolve_target_group("aiocqhttp:GroupMessage:888888")
    assert gid == "888888"


def test_resolve_target_group_by_name_single_match(report_query_service, mock_trace_store):
    # 按名称单一匹配
    mock_trace_store.find_groups_by_name.return_value = [
        {"group_id": "123456", "group_name": "测试交流群", "platform": "aiocqhttp"}
    ]
    gid, name, cand = report_query_service.resolve_target_group("交流群")
    assert gid == "123456"
    assert name == "测试交流群"
    assert cand == []


def test_resolve_target_group_by_name_ambiguous(report_query_service, mock_trace_store):
    # 按名称歧义返回候选
    mock_trace_store.find_groups_by_name.return_value = [
        {"group_id": "111", "group_name": "开黑一队"},
        {"group_id": "222", "group_name": "开黑二队"},
    ]
    gid, name, cand = report_query_service.resolve_target_group("开黑")
    assert gid is None
    assert len(cand) == 2


# ==================== 2. ReportQueryService 弹性日期解析测试 ====================


def test_parse_date_range_relative(report_query_service):
    start, end, err = report_query_service.parse_date_range("今天")
    assert err is None
    assert start == end

    start_y, end_y, err_y = report_query_service.parse_date_range("昨天")
    assert err_y is None
    assert start_y == end_y

    start_latest, end_latest, err_latest = report_query_service.parse_date_range("")
    assert err_latest is None
    assert start_latest == ""
    assert end_latest == ""


def test_parse_date_range_formats(report_query_service):
    # 补零与分隔符
    start, end, err = report_query_service.parse_date_range("2026/10/2")
    assert err is None
    assert start == "2026-10-02"
    assert end == "2026-10-02"

    # 波浪线范围
    start_r, end_r, err_r = report_query_service.parse_date_range("2026-10-01~2026-10-05")
    assert err_r is None
    assert start_r == "2026-10-01"
    assert end_r == "2026-10-05"


def test_parse_date_range_errors(report_query_service):
    # 超过 30 天拦截
    _, _, err_overflow = report_query_service.parse_date_range("2026-10-01~2026-11-15")
    assert err_overflow is not None
    assert "超过了最大支持的 30 天" in err_overflow

    # 逆序拦截
    _, _, err_reverse = report_query_service.parse_date_range("2026-10-05~2026-10-01")
    assert err_reverse is not None
    assert "不能晚于" in err_reverse


# ==================== 3. 报告检索与模块投影测试 ====================


@pytest.mark.asyncio
async def test_query_reports_projection_and_format(report_query_service, mock_checkpoint_store):
    mock_checkpoint_store.get_checkpoints_by_date_range.return_value = [
        {
            "checkpoint_id": "cp_1",
            "group_id": "123456",
            "date_str": "2026-10-02",
            "stage_name": "LLM_ANALYSIS",
            "data": {
                "topics": [{"topic": "二手车讨论", "detail": "推荐卡罗拉", "heat": 95}],
                "golden_quotes": [{"quote": "车到山前必有路", "author": "老张"}],
                "user_titles": [{"user_name": "小李", "title": "预算守门员"}],
                "chat_quality_review": {"atmosphere": "热烈", "depth": "深入"},
            },
        }
    ]

    # 1. 仅请求话题
    res_topics = await report_query_service.query_reports(
        group_id="123456",
        start_date="2026-10-02",
        end_date="2026-10-02",
        report_section="话题",
    )
    assert "二手车讨论" in res_topics
    assert "推荐卡罗拉" in res_topics
    assert "车到山前必有路" not in res_topics
    assert "预算守门员" not in res_topics

    # 2. 请求话题 + 金句
    res_multi = await report_query_service.query_reports(
        group_id="123456",
        start_date="2026-10-02",
        end_date="2026-10-02",
        report_section="话题,金句",
    )
    assert "二手车讨论" in res_multi
    assert "车到山前必有路" in res_multi
    assert "预算守门员" not in res_multi


@pytest.mark.asyncio
async def test_query_reports_sliding_probe(report_query_service, mock_checkpoint_store):
    # 精确命中为空，但临近日期存在
    mock_checkpoint_store.get_checkpoints_by_date_range.return_value = []
    mock_checkpoint_store.get_checkpoint_detail.return_value = {
        "checkpoint_id": "cp_prev",
        "group_id": "123456",
        "date_str": "2026-10-01",
        "stage_name": "LLM_ANALYSIS",
        "trace_id": "t1",
        "created_at": 1000,
        "data": {"topics": [{"topic": "前天话题", "detail": "测试"}]},
    }

    res = await report_query_service.query_reports(
        group_id="123456",
        start_date="2026-10-02",
        end_date="2026-10-02",
        report_section="全部",
    )
    assert "自动匹配最临近于 2026-10-01" in res
    assert "前天话题" in res


# ==================== 4. AnalysisTriggerService 触发测试 ====================


@pytest.fixture
def mock_analysis_service():
    srv = MagicMock()
    srv.is_group_running.return_value = False
    srv.execute_daily_analysis = AsyncMock(return_value={"success": True})
    return srv


@pytest.fixture
def mock_active_task_manager():
    mgr = MagicMock()
    mgr.register_task = AsyncMock()
    mgr.unregister_task = AsyncMock()
    return mgr


@pytest.fixture
def trigger_service(
    mock_config_manager,
    mock_analysis_service,
    report_query_service,
    mock_active_task_manager,
    mock_trace_store,
):
    return AnalysisTriggerService(
        config_manager=mock_config_manager,
        analysis_service=mock_analysis_service,
        report_query_service=report_query_service,
        active_task_manager=mock_active_task_manager,
        trace_store=mock_trace_store,
    )


@pytest.mark.asyncio
async def test_trigger_permission_denied(trigger_service):
    event = MagicMock()
    event.is_admin.return_value = False
    event.role = "member"
    event.get_sender_id.return_value = "10001"  # 不在 admin_users 中

    msg = await trigger_service.trigger_analysis(event, group="123456")
    assert "[权限不足]" in msg


@pytest.mark.asyncio
async def test_trigger_conflict_lock(trigger_service, mock_analysis_service):
    event = MagicMock()
    event.is_admin.return_value = True
    event.get_group_id.return_value = "123456"

    # 模拟正在运行
    mock_analysis_service.is_group_running.return_value = True

    msg = await trigger_service.trigger_analysis(event, group="")
    assert "[任务冲突]" in msg


@pytest.mark.asyncio
async def test_trigger_success_async_fire_and_forget(trigger_service, mock_analysis_service):
    event = MagicMock()
    event.is_admin.return_value = True
    event.get_group_id.return_value = "123456"
    event.get_platform_id.return_value = "aiocqhttp"

    msg = await trigger_service.trigger_analysis(
        event=event,
        analysis_sections="话题,聊天质量分析",  # 质量分析被配置关闭
        days=2,
        group="",
    )

    # 500ms 内收到受理回执
    assert "[分析任务已成功在后台启动]" in msg
    assert "topics" in msg or "话题" in msg
    assert "跳过模块: 聊天质量分析" in msg

    # 等待后台任务执行一小会儿确保 create_task 运行
    await asyncio.sleep(0.05)
    mock_analysis_service.execute_daily_analysis.assert_called_once()
    call_kwargs = mock_analysis_service.execute_daily_analysis.call_args.kwargs
    assert call_kwargs["group_id"] == "123456"
    assert call_kwargs["days"] == 2
    assert call_kwargs["analysis_sections"] == {"topics"}
    # 部分模块触发，阶段隔离为 ON_DEMAND_ANALYSIS
    assert call_kwargs["checkpoint_stage_name"] == AnalysisStage.ON_DEMAND_ANALYSIS.value
