"""增量批次持久化必须先于游标更新，检查点失败允许继续。"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.incremental_analysis_service import IncrementalAnalysisService
from src.application.services.pipeline_context import PipelineContext
from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.value_objects import UnifiedMessage


@pytest.mark.asyncio
async def test_failed_batch_does_not_save_checkpoint_or_advance_cursor():
    service = object.__new__(IncrementalAnalysisService)
    service.incremental_store = Mock(save_batch=AsyncMock(return_value=False), update_last_analyzed_cursor=AsyncMock())
    service.checkpoint_store = Mock()
    pipeline = PipelineContext(None, service.checkpoint_store, "123", "2026-10-01")
    assert await service._persist_incremental_batch(pipeline, IncrementalBatch(group_id="123"), [], 0, set()) is None
    service.checkpoint_store.save_checkpoint.assert_not_called()
    service.incremental_store.update_last_analyzed_cursor.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("checkpoint_fails", [True, False])
async def test_cursor_advances_after_batch_and_checkpoint_attempt(checkpoint_fails):
    service = object.__new__(IncrementalAnalysisService)
    order = []

    async def save_batch(_batch):
        order.append("batch")
        return True

    def checkpoint(**_kwargs):
        order.append("checkpoint")
        if checkpoint_fails:
            raise OSError("模拟检查点不可写")

    async def cursor(*_args):
        order.append("cursor")

    service.incremental_store = Mock(save_batch=AsyncMock(side_effect=save_batch), update_last_analyzed_cursor=AsyncMock(side_effect=cursor))
    service.checkpoint_store = Mock(save_checkpoint=Mock(side_effect=checkpoint))
    pipeline = PipelineContext(None, service.checkpoint_store, "123", "2026-10-01")
    batch = IncrementalBatch(group_id="123", batch_id="batch", last_message_timestamp=100)
    message = UnifiedMessage(message_id="new", sender_id="u", sender_name="成员", group_id="123", text_content="消息", timestamp=100)
    assert await service._persist_incremental_batch(pipeline, batch, [message], 100, {"old"}) == 100
    assert order == ["batch", "checkpoint", "cursor"]
    assert service.checkpoint_store.save_checkpoint.call_args.kwargs["date_str"] == "2026-10-01"
    service.incremental_store.update_last_analyzed_cursor.assert_awaited_once_with("123", 100, {"old", "new"})
