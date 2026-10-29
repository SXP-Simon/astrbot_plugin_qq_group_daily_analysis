"""恢复快照加载优先级和同源历史回退的回归。"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.domain.value_objects import GroupStatistics


@pytest.mark.asyncio
async def test_task_checkpoint_precedes_history_and_restores_domain_models():
    service = object.__new__(AnalysisRecoveryService)
    service.checkpoint_store = Mock()
    service.checkpoint_store.get_checkpoint.return_value = {"statistics": {"message_count": 7}}
    service.history_manager = Mock(get_analysis=AsyncMock())
    result = await service._load_analysis_checkpoint("123", "2026-10-01", "source")
    service.checkpoint_store.get_checkpoint.assert_called_once_with(
        "123", "2026-10-01", "LLM_ANALYSIS", trace_id="source"
    )
    service.history_manager.get_analysis.assert_not_awaited()
    assert isinstance(result["statistics"], GroupStatistics)
    assert result["statistics"].message_count == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("history_trace_id", ["source", "another"])
async def test_missing_checkpoint_only_loads_matching_task_history(history_trace_id):
    service = object.__new__(AnalysisRecoveryService)
    service.checkpoint_store = Mock()
    service.checkpoint_store.get_checkpoint.return_value = None
    service.history_manager = Mock(
        get_analysis=AsyncMock(
            return_value={"trace_id": history_trace_id, "statistics": {"message_count": 9}}
        )
    )
    result = await service._load_analysis_checkpoint("123", "2026-10-01", "source")
    if history_trace_id == "source":
        assert result["statistics"].message_count == 9
    else:
        assert result is None
