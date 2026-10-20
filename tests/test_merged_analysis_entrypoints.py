"""手动分析与词云指令的合并分发入口契约。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler
from src.application.handlers.wordcloud_command_handler import WordCloudCommandHandler
from src.domain.value_objects.wordcloud import (
    WordCloudData,
    WordCloudOptions,
    WordFrequency,
)


def group_event() -> SimpleNamespace:
    """不包含平台网络操作的真实指令形状。"""
    return SimpleNamespace(
        get_group_id=Mock(return_value="123456"),
        get_platform_id=Mock(return_value="onebot-main"),
        unified_msg_origin="onebot-main:GroupMessage:123456",
        message_obj=SimpleNamespace(message_id=None),
        should_call_llm=Mock(),
        plain_result=Mock(side_effect=lambda text: text),
        stop_event=Mock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("enable_reply", [True, False], ids=["text", "reaction"])
@pytest.mark.parametrize(
    "merge_report", [True, False], ids=["merge-report", "normal-report"]
)
async def test_manual_analysis_merged_entrypoint_dispatches_without_normal_sends(
    tmp_path,
    enable_reply,
    merge_report,
):
    """只合并日报产物；启动提示仍服从原有文本与表情回应配置。"""
    event = group_event()
    event.message_obj.message_id = "msg_001"
    analysis = {"topics": [{"topic": "高性能", "detail": "完成分析"}]}
    adapter = SimpleNamespace(
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name="测试群")),
        get_platform_name=Mock(return_value="onebot"),
        set_reaction=AsyncMock(),
        send_image=AsyncMock(),
        send_text=AsyncMock(),
        send_file=AsyncMock(),
    )
    manager = SimpleNamespace(
        is_group_allowed=Mock(return_value=True),
        get_enable_analysis_reply=Mock(return_value=enable_reply),
        get_output_format=Mock(return_value=["image", "html", "text"]),
    )
    bots = SimpleNamespace(
        update_from_event=Mock(), get_adapter=Mock(return_value=adapter)
    )
    result = {
        "success": True,
        "group_id": "123456",
        "platform_id": "onebot-main",
        "adapter": adapter,
        "analysis_result": analysis,
    }
    service = SimpleNamespace(
        is_group_running=Mock(return_value=False),
        execute_daily_analysis=AsyncMock(return_value=result),
    )
    dispatcher = SimpleNamespace(
        merged_delivery=SimpleNamespace(
            enabled_for=Mock(
                side_effect=lambda _platform, kind=None: (
                    kind != "report" or merge_report
                )
            )
        ),
        dispatch=AsyncMock(return_value=True),
    )
    comic = SimpleNamespace(try_trigger_comic_generation=Mock())
    cloud = SimpleNamespace(send_with_report=AsyncMock())
    sender = SimpleNamespace(send_image_smart=AsyncMock(), send_text=AsyncMock())
    handler = AnalysisCommandHandler(
        manager,
        bots,
        service,
        SimpleNamespace(),
        AsyncMock(),
        message_sender=sender,
        comic_handler=comic,
        plugin_data_dir=tmp_path,
        wordcloud_delivery=cloud,
        report_dispatcher=dispatcher,
    )

    command = handler.handle_daily_analysis(event)
    responses = []
    if enable_reply:
        responses.append(await anext(command))
        assert responses == ["🔍 正在启动分析引擎，正在拉取最近消息..."]
        service.execute_daily_analysis.assert_not_awaited()
        dispatcher.dispatch.assert_not_awaited()
    responses.extend([response async for response in command])

    if enable_reply:
        assert responses == ["🔍 正在启动分析引擎，正在拉取最近消息..."]
        event.plain_result.assert_called_once_with(responses[0])
        adapter.set_reaction.assert_not_awaited()
    else:
        assert responses == []
        event.plain_result.assert_not_called()
        assert adapter.set_reaction.await_args_list == [
            call("123456", "msg_001", "analysis_started"),
            call("123456", "msg_001", "analysis_done"),
        ]
    service.execute_daily_analysis.assert_awaited_once_with(
        group_id="123456", platform_id="onebot-main", manual=True, days=None
    )
    if merge_report:
        dispatcher.dispatch.assert_awaited_once_with("123456", analysis, "onebot-main")
    else:
        dispatcher.dispatch.assert_awaited_once_with(
            "123456", analysis, "onebot-main", output_formats=["image"]
        )
    comic.try_trigger_comic_generation.assert_not_called()
    cloud.send_with_report.assert_not_awaited()
    adapter.send_image.assert_not_awaited()
    adapter.send_text.assert_not_awaited()
    adapter.send_file.assert_not_awaited()
    sender.send_image_smart.assert_not_awaited()
    sender.send_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retry", [False, True], ids=["new-wordcloud", "resend-wordcloud"]
)
@pytest.mark.parametrize("merged", [False, True], ids=["normal", "merged"])
async def test_wordcloud_success_stops_event_only_for_direct_merged_send(retry, merged):
    """词云进度保持普通回复；合并成功仍结束事件，重发沿用无进度行为。"""
    event = group_event()
    data = WordCloudData((WordFrequency("高性能", 8, 3),), message_count=3)
    manager = SimpleNamespace(
        is_group_allowed=Mock(return_value=True),
        get_wordcloud_options=Mock(return_value=WordCloudOptions()),
        get_analysis_days=Mock(return_value=1),
    )
    delivery = SimpleNamespace(
        config_manager=manager,
        store=SimpleNamespace(latest=Mock(return_value=data)),
        send=AsyncMock(return_value=True),
        merged_delivery=SimpleNamespace(enabled_for=Mock(return_value=merged)),
    )
    service = SimpleNamespace(
        bot_manager=SimpleNamespace(update_from_event=Mock()),
        collect_wordcloud=AsyncMock(return_value=data),
    )
    handler = WordCloudCommandHandler(service, delivery)

    responses = [response async for response in handler.handle(event, retry=retry)]

    delivery.send.assert_awaited_once_with(
        data,
        "123456",
        "onebot-main",
        force=True,
        umo="onebot-main:GroupMessage:123456",
    )
    event.should_call_llm.assert_called_once_with(False)
    delivery.merged_delivery.enabled_for.assert_called_once_with(
        "onebot-main", "wordcloud"
    )
    if retry:
        service.collect_wordcloud.assert_not_awaited()
    else:
        service.collect_wordcloud.assert_awaited_once_with(
            "123456", "onebot-main", days=1
        )
    if merged:
        event.stop_event.assert_called_once_with()
    else:
        event.stop_event.assert_not_called()
    assert responses == ([] if retry else ["正在提取群聊词频并生成词云……"])
    assert event.plain_result.call_args_list == [call(text) for text in responses]


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True], ids=["new-wordcloud", "resend"])
async def test_wordcloud_merged_failure_keeps_visible_error_response(retry):
    """失败提示独立回复，普通词云仍有前置进度，重发不新增进度消息。"""
    event = group_event()
    data = WordCloudData((WordFrequency("高性能", 8, 3),), message_count=3)
    manager = SimpleNamespace(
        is_group_allowed=Mock(return_value=True),
        get_wordcloud_options=Mock(return_value=WordCloudOptions()),
        get_analysis_days=Mock(return_value=1),
    )
    delivery = SimpleNamespace(
        config_manager=manager,
        store=SimpleNamespace(latest=Mock(return_value=data)),
        send=AsyncMock(return_value=False),
        merged_delivery=SimpleNamespace(enabled_for=Mock(return_value=True)),
    )
    service = SimpleNamespace(
        bot_manager=SimpleNamespace(update_from_event=Mock()),
        collect_wordcloud=AsyncMock(return_value=data),
    )

    responses = [
        response
        async for response in WordCloudCommandHandler(service, delivery).handle(
            event, retry=retry
        )
    ]

    expected_error = (
        "词云出图或发送失败，词频已保存。可使用 /重发词云 再试，或查看插件日志。"
    )
    assert responses == (
        [expected_error] if retry else ["正在提取群聊词频并生成词云……", expected_error]
    )
    assert event.plain_result.call_args_list == [call(text) for text in responses]
    event.stop_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("enable_reply", [True, False], ids=["text", "reaction"])
async def test_manual_analysis_merged_failure_remains_plain_response(
    tmp_path, enable_reply
):
    """报告合并开关不吞掉分析失败提示，也不改写原来的启动反馈配置。"""
    event = group_event()
    event.message_obj.message_id = "msg_002"
    adapter = SimpleNamespace(
        get_group_info=AsyncMock(return_value=None),
        get_platform_name=Mock(return_value="onebot"),
        set_reaction=AsyncMock(),
    )
    dispatcher = SimpleNamespace(
        merged_delivery=SimpleNamespace(enabled_for=Mock(return_value=True)),
        dispatch=AsyncMock(),
    )
    handler = AnalysisCommandHandler(
        config_manager=SimpleNamespace(
            is_group_allowed=Mock(return_value=True),
            get_enable_analysis_reply=Mock(return_value=enable_reply),
        ),
        bot_manager=SimpleNamespace(
            update_from_event=Mock(), get_adapter=Mock(return_value=adapter)
        ),
        analysis_service=SimpleNamespace(
            is_group_running=Mock(return_value=False),
            execute_daily_analysis=AsyncMock(
                return_value={"success": False, "reason": "no_messages"}
            ),
        ),
        report_generator=SimpleNamespace(),
        html_render=AsyncMock(),
        plugin_data_dir=tmp_path,
        report_dispatcher=dispatcher,
    )

    responses = [response async for response in handler.handle_daily_analysis(event)]

    assert responses == (
        ["🔍 正在启动分析引擎，正在拉取最近消息...", "❌ 未找到足够的群聊记录"]
        if enable_reply
        else ["❌ 未找到足够的群聊记录"]
    )
    assert event.plain_result.call_args_list == [call(text) for text in responses]
    dispatcher.dispatch.assert_not_awaited()
    if enable_reply:
        adapter.set_reaction.assert_not_awaited()
    else:
        adapter.set_reaction.assert_awaited_once_with(
            "123456", "msg_002", "analysis_started"
        )
