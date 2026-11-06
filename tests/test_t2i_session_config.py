"""验证报告渲染按群选择宿主配置，并兼容旧版渲染接口。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler
from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.domain.value_objects import GroupStatistics
from src.infrastructure.reporting import html_renderer
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.infrastructure.reporting.html_renderer import (
    bind_group_html_renderer,
    describe_html_renderer,
)


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("http://t2i:8999/text2img", "http://t2i:8999/text2img"),
        (
            "https://user:password@render.example:8443/api?token=secret#private",
            "https://render.example:8443/api",
        ),
        ("http://[::1]:8999/text2img", "http://[::1]:8999/text2img"),
        ("", "使用宿主默认地址池"),
        ("not-a-url", "配置地址格式异常"),
        ("http://host:invalid", "无法读取配置地址（ValueError）"),
        (123, "配置地址不是字符串"),
    ],
)
def test_render_diagnostics_reads_bound_config_without_changing_it(endpoint, expected):
    """诊断按原会话查询地址，保留主机端口并隐藏 URL 中的认证信息。"""
    config = {"t2i_endpoint": endpoint, "t2i": False}

    class Host:
        context = SimpleNamespace(get_config=MagicMock(return_value=config))

        async def html_render(
            self, tmpl, data, return_url=True, options=None, umo=None
        ):
            raise AssertionError("读取诊断信息不应调用渲染服务")

    host = Host()
    callback = bind_group_html_renderer(host.html_render, "123", "bot-a")
    info = describe_html_renderer(callback)
    host.context.get_config.assert_called_once_with("bot-a:GroupMessage:123")
    assert expected in info["configured_endpoint"]
    assert "按群聊会话查询" in info["config_lookup"]
    assert all(secret not in str(info) for secret in ("password", "secret", "private"))
    assert config == {"t2i_endpoint": endpoint, "t2i": False}


def test_render_diagnostics_distinguishes_default_and_unavailable_context():
    """默认配置查询与未知回调分开说明，不冒充已知的实际请求地址。"""

    class Host:
        context = SimpleNamespace(get_config=MagicMock(return_value={}))

        async def html_render(self, tmpl, data, umo=None):
            return None

    host = Host()
    info = describe_html_renderer(host.html_render)
    assert info["config_lookup"] == "默认配置"
    assert "实际请求地址由宿主选择" in info["configured_endpoint"]
    host.context.get_config.assert_called_once_with(None)
    host.context.get_config.side_effect = RuntimeError("private config")
    info = describe_html_renderer(host.html_render)
    assert "RuntimeError" in info["configured_endpoint"]
    assert "private config" not in str(info)
    assert "未知" in describe_html_renderer(AsyncMock())["configured_endpoint"]


def test_render_diagnostics_does_not_guess_legacy_endpoint():
    """旧版回调不按会话读配置时，诊断也不能假装读取了绑定地址。"""

    class Host:
        context = SimpleNamespace(get_config=MagicMock())

        async def html_render(self, tmpl, data, return_url=True, options=None):
            return None

    host = Host()
    info = describe_html_renderer(host.html_render)
    assert "旧版" in info["config_lookup"]
    host.context.get_config.assert_not_called()


@pytest.mark.asyncio
async def test_bound_profiles_are_isolated_and_default_is_preserved():
    """关闭自动转图仍使用绑定配置，不同平台和群的并发渲染互不污染。"""
    default = {"t2i": False, "t2i_endpoint": "http://default:8999"}
    profiles = {
        "bot-a:GroupMessage:123": {"t2i": False, "t2i_endpoint": "http://a:8999"},
        "bot-b:GroupMessage:123": {"t2i": False, "t2i_endpoint": "http://b:8999"},
        "bot-a:GroupMessage:456": {"t2i": False, "t2i_endpoint": "http://c:8999"},
    }

    class Host:
        async def html_render(
            self, tmpl, data, return_url=True, options=None, umo=None
        ):
            config = profiles.get(umo, default)
            await asyncio.sleep(0)
            return config["t2i_endpoint"]

    host = Host()
    targets = [("123", "bot-a"), ("123", "bot-b"), ("456", "bot-a"), ("789", "bot-a")]
    callbacks = [
        bind_group_html_renderer(host.html_render, group, bot) for group, bot in targets
    ]
    assert await asyncio.gather(
        *(callback("html", {}, False, {}) for callback in callbacks)
    ) == ["http://a:8999", "http://b:8999", "http://c:8999", "http://default:8999"]
    assert await host.html_render("html", {}) == "http://default:8999"
    assert not default["t2i"] and all(not config["t2i"] for config in profiles.values())


@pytest.mark.asyncio
async def test_legacy_callback_receives_original_arguments():
    """旧接口不接受 umo 时保留原回调和四个渲染参数。"""
    calls = []

    async def legacy(tmpl, data, return_url=True, options=None):
        calls.append((tmpl, data, return_url, options))
        return b"image"

    callback = bind_group_html_renderer(legacy, "123", "bot-a")
    assert callback is legacy
    assert await callback("html", {"x": 1}, False, {"type": "png"}) == b"image"
    assert calls == [("html", {"x": 1}, False, {"type": "png"})]


@pytest.mark.parametrize("group,platform", [("123", None), ("123", ""), ("", "bot-a")])
def test_missing_session_preserves_default(group, platform):
    """无法确定会话时沿用默认配置，不拼出无效 UMO。"""
    callback = AsyncMock()
    assert bind_group_html_renderer(callback, group, platform) is callback
    assert bind_group_html_renderer(None, group, platform) is None


@pytest.mark.asyncio
async def test_keyword_wrapper_accepts_session():
    """接受关键字透传的宿主包装器也能收到会话。"""
    callback = AsyncMock(return_value="image")
    bound = bind_group_html_renderer(callback, "123", "bot-a")
    assert await bound("html", {}, False, {}) == "image"
    callback.assert_awaited_once_with(
        "html", {}, False, {}, umo="bot-a:GroupMessage:123"
    )


@pytest.mark.parametrize("error", [TypeError, ValueError])
def test_uninspectable_callback_uses_legacy_call(monkeypatch, error):
    """不能读取签名的第三方回调保留旧调用方式。"""
    callback = AsyncMock()
    monkeypatch.setattr(html_renderer, "signature", MagicMock(side_effect=error))
    assert bind_group_html_renderer(callback, "123", "bot-a") is callback


@pytest.mark.asyncio
async def test_render_type_error_is_not_retried_without_session():
    """渲染内部 TypeError 必须原样抛出，不能改用默认配置重新请求。"""
    calls = []

    async def render(tmpl, data, return_url=True, options=None, *, umo=None):
        calls.append(umo)
        raise TypeError("渲染内部错误")

    callback = bind_group_html_renderer(render, "123", "bot-a")
    with pytest.raises(TypeError, match="渲染内部错误"):
        await callback("html", {}, False, {})
    assert calls == ["bot-a:GroupMessage:123"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry", ["manual", "scheduled", "rerender", "manual_summary", "scheduled_summary"]
)
async def test_report_entry_points_forward_bound_renderer(entry, monkeypatch, tmp_path):
    """各报告入口都传递绑定后的回调，覆盖定时报告、重绘和 QQ 图片摘要。"""
    callback = AsyncMock(return_value="image")
    config = MagicMock()
    config.get_output_format.return_value = ["image"]
    config.get_report_template.return_value = "scrapbook"
    generator = MagicMock()
    generator.generate_image_report = AsyncMock(return_value=(None, None))
    generator.generate_markdown_report = AsyncMock(return_value=("report", "fallback"))
    adapter = MagicMock()
    adapter.platform_id = "bot-a"
    adapter.get_platform_name.return_value = "qq_official"
    adapter.send_text_report = AsyncMock(return_value=True)
    manager = MagicMock()
    manager.get_adapter.return_value = adapter

    if entry in ("manual", "manual_summary"):
        handler = AnalysisCommandHandler(
            config, manager, MagicMock(), generator, callback
        )
        if entry == "manual":
            handler.send_text_reports = AsyncMock()
            result = {
                "group_id": "123",
                "platform_id": "bot-a",
                "analysis_result": {},
                "adapter": adapter,
            }
            async for _ in handler.send_analysis_report(SimpleNamespace(), result):
                pass
            bound = generator.generate_image_report.call_args.args[2]
        else:
            await handler.send_text_reports("123", {}, True, adapter)
            bound = generator.generate_markdown_report.call_args.args[1]
        assert handler.html_render is callback
    elif entry in ("scheduled", "scheduled_summary"):
        sender = SimpleNamespace(bot_manager=manager)
        dispatcher = ReportDispatcher(config, generator, sender)
        dispatcher.set_html_render(callback)
        if entry == "scheduled":
            dispatcher._dispatch_text = AsyncMock(return_value=True)
            await dispatcher.dispatch("123", {}, "bot-a")
            bound = generator.generate_image_report.call_args.args[2]
        else:
            assert await dispatcher._dispatch_text("123", {}, "bot-a")
            bound = generator.generate_markdown_report.call_args.args[1]
        assert dispatcher._html_render_func is callback
    else:
        monkeypatch.setattr(
            "src.application.services.analysis_recovery_service.StarTools.get_data_dir",
            lambda _: tmp_path,
        )
        history = SimpleNamespace(
            get_analysis=AsyncMock(
                return_value={
                    "statistics": GroupStatistics(
                        message_count=1,
                        total_characters=1,
                        participant_count=1,
                        most_active_period="00:00",
                        golden_quotes=[],
                        emoji_count=0,
                    )
                }
            )
        )
        service = AnalysisRecoveryService(
            config,
            manager,
            history,
            generator,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            html_render=callback,
        )
        await service.rerender_report(
            "123", "2026-10-22", "scrapbook", platform_id="bot-a"
        )
        bound = generator.generate_image_report.call_args.kwargs["html_render_func"]
        assert service.html_render is callback

    assert await bound("html", {}, False, {"type": "png"}) == "image"
    callback.assert_awaited_once_with(
        "html", {}, False, {"type": "png"}, umo="bot-a:GroupMessage:123"
    )
