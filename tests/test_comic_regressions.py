import ast
import asyncio
import mimetypes
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock


def load_main_method(name: str):
    """从主入口加载单个方法，避免测试依赖 AstrBot 运行时。

    Args:
        name: 目标异步方法名称。

    Returns:
        可直接绑定到测试替身对象的方法。
    """
    main_path = Path(__file__).parents[1] / "main.py"
    module = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    plugin_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "GroupDailyAnalysis"
    )
    method = next(
        node
        for node in plugin_class.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == name
    )
    method.decorator_list = []
    isolated_class = ast.ClassDef(
        name="MainMethodHarness",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[isolated_class], type_ignores=[])
    )
    namespace = {
        "AsyncGenerator": object,
        "AstrMessageEvent": object,
        "DuplicateGroupTaskError": RuntimeError,
        "asyncio": asyncio,
        "logger": Mock(),
    }
    exec(compile(isolated_module, str(main_path), "exec"), namespace)
    return getattr(namespace["MainMethodHarness"], name)


def load_comic_service_method(name: str):
    """从漫画服务加载单个方法，避免测试依赖 AstrBot 运行时。

    Args:
        name: 目标异步方法名称。

    Returns:
        可直接绑定到测试替身对象的方法。
    """
    service_path = (
        Path(__file__).parents[1]
        / "src"
        / "application"
        / "services"
        / "comic_application_service.py"
    )
    module = ast.parse(
        service_path.read_text(encoding="utf-8"), filename=str(service_path)
    )
    service_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "ComicApplicationService"
    )
    method = next(
        node
        for node in service_class.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name == name
    )
    isolated_class = ast.ClassDef(
        name="ComicServiceHarness",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[isolated_class], type_ignores=[])
    )
    namespace = {"Path": Path, "mimetypes": mimetypes, "logger": Mock(), "Any": Any}
    exec(compile(isolated_module, str(service_path), "exec"), namespace)
    return getattr(namespace["ComicServiceHarness"], name)


def load_config_manager_class():
    """加载漫画参考图相关配置方法，避免测试依赖 AstrBot 运行时。"""
    config_path = (
        Path(__file__).parents[1]
        / "src"
        / "infrastructure"
        / "config"
        / "config_manager.py"
    )
    module = ast.parse(
        config_path.read_text(encoding="utf-8"), filename=str(config_path)
    )
    config_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "ConfigManager"
    )
    required_names = {"__init__", "_get_group", "get_drawing_reference_image"}
    methods = [
        node
        for node in config_class.body
        if isinstance(node, ast.FunctionDef) and node.name in required_names
    ]
    isolated_class = ast.ClassDef(
        name="ConfigManagerHarness",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[isolated_class], type_ignores=[])
    )
    namespace = {"AstrBotConfig": object, "logger": Mock()}
    exec(compile(isolated_module, str(config_path), "exec"), namespace)
    return namespace["ConfigManagerHarness"]


def test_analysis_settings_returns_after_non_status_action():
    """非状态命令不应继续渲染只在 status 分支赋值的变量。"""
    analysis_settings = load_main_method("analysis_settings")

    async def scenario():
        config_manager = SimpleNamespace(
            get_filter_bot_messages=Mock(return_value=True),
            set_filter_bot_messages=Mock(),
        )
        plugin = SimpleNamespace(
            config_manager=config_manager,
            _get_group_id_from_event=Mock(return_value="123456"),
        )
        event = SimpleNamespace(
            should_call_llm=Mock(),
            plain_result=lambda content: content,
        )

        results = [
            result async for result in analysis_settings(plugin, event, "filter_bot")
        ]

        assert results == ["✅ 过滤机器人消息: 已禁用"]
        config_manager.set_filter_bot_messages.assert_called_once_with(False)

    asyncio.run(scenario())


def test_qq_official_webhook_uses_official_report_capabilities():
    """QQ 官方 Webhook 与普通官方适配器使用相同的报告能力。"""
    send_analysis_report = load_main_method("_send_analysis_report")

    async def scenario():
        adapter = SimpleNamespace(
            get_platform_name=Mock(return_value="qq_official_webhook")
        )
        plugin = SimpleNamespace(
            _terminating=False,
            config_manager=SimpleNamespace(
                get_output_format=Mock(return_value=["text"])
            ),
            _send_text_reports=AsyncMock(return_value=True),
            _try_trigger_comic_generation=Mock(),
        )
        result = {
            "group_id": "123456",
            "platform_id": "qq-official-main",
            "analysis_result": {},
            "adapter": adapter,
        }

        async for _ in send_analysis_report(plugin, SimpleNamespace(), result):
            pass

        assert plugin._send_text_reports.await_args.args[2] is True
        plugin._try_trigger_comic_generation.assert_called_once_with(
            "123456", "qq-official-main", {}
        )

    asyncio.run(scenario())


def test_uploaded_reference_image_is_loaded_from_plugin_data_dir(tmp_path: Path):
    """已选参考图只允许从插件数据目录读取。"""
    fetch_reference_image = load_comic_service_method("_fetch_reference_image")
    image_path = tmp_path / "files" / "daily_comic" / "drawing_reference_image"
    image_path.mkdir(parents=True)
    (image_path / "reference.png").write_bytes(b"\x89PNG\r\n\x1a\nimage")
    service = SimpleNamespace(
        plugin_data_dir=tmp_path,
    )

    result = asyncio.run(
        fetch_reference_image(
            service,
            "files/daily_comic/drawing_reference_image/reference.png",
        )
    )

    assert result == (b"\x89PNG\r\n\x1a\nimage", "image/png")


def test_reference_image_migrates_old_config_and_uses_last_selected_file():
    """旧字符串配置应迁移为空，原生文件列表取最后一次选择。"""
    config_manager_class = load_config_manager_class()

    class Config(dict):
        save_config = Mock()

    config = Config(
        daily_comic={"drawing_reference_image": "https://example.com/a.png"}
    )
    config_manager = config_manager_class(config)

    assert config["daily_comic"]["drawing_reference_image"] == []
    config.save_config.assert_called_once()

    config["daily_comic"]["drawing_reference_image"] = [
        "files/daily_comic/drawing_reference_image/first.png",
        "files/daily_comic/drawing_reference_image/selected.webp",
    ]
    assert (
        config_manager.get_drawing_reference_image()
        == "files/daily_comic/drawing_reference_image/selected.webp"
    )


def test_comic_is_skipped_without_valid_topics():
    """话题功能未产出有效标题时不应创建漫画任务。"""
    trigger_comic = load_main_method("_try_trigger_comic_generation")
    plugin = SimpleNamespace(
        _terminating=False,
        config_manager=SimpleNamespace(get_enable_daily_comic=Mock(return_value=True)),
        _comic_group_tasks={},
        _background_tasks=set(),
        _trigger_comic_generation=AsyncMock(),
    )

    trigger_comic(plugin, "123456", "onebot-main", {"topics": [{"topic": ""}]})

    plugin._trigger_comic_generation.assert_not_called()
    assert plugin._comic_group_tasks == {}
    assert plugin._background_tasks == set()


def _install_fake_big_banana_image_resource():
    """向 sys.modules 注入假的大香蕉 ImageResource，供懒加载导入使用。

    Returns:
        假 ImageResource 类型，可用于断言。
    """
    import sys
    from types import ModuleType

    fake_image_resource = type(
        "ImageResource",
        (),
        {
            "from_bytes": staticmethod(
                lambda data_bytes, url=None: SimpleNamespace(
                    bytes=data_bytes, mime="image/png"
                )
            )
        },
    )

    schemas = ModuleType("astrbot_plugin_big_banana.core.schemas")
    schemas.ImageResource = fake_image_resource
    core = ModuleType("astrbot_plugin_big_banana.core")
    core.schemas = schemas
    pkg = ModuleType("astrbot_plugin_big_banana")
    pkg.core = core
    sys.modules["astrbot_plugin_big_banana"] = pkg
    sys.modules["astrbot_plugin_big_banana.core"] = core
    sys.modules["astrbot_plugin_big_banana.core.schemas"] = schemas
    return fake_image_resource


def test_map_comic_image_size_aliases():
    """大香蕉后端的尺寸别名映射。"""
    mapping = load_comic_service_method("_map_comic_image_size")
    assert mapping("1024x1024") == "1K"
    assert mapping("1K") == "1K"
    assert mapping("2k") == "2K"
    assert mapping("2048x2048") == "2K"
    assert mapping("4K") == "4K"
    assert mapping("4096x4096") == "4K"
    assert mapping("auto") == "1K"
    assert mapping("") == "1K"


def test_big_banana_backend_returns_none_when_plugin_missing():
    """大香蕉插件未注册时应回退（返回 None）。"""
    generate = load_comic_service_method("_generate_via_big_banana")
    context = SimpleNamespace(get_registered_star=Mock(return_value=None))
    service = SimpleNamespace(context=context)

    result = asyncio.run(generate(service, "prompt", None))

    assert result is None


def test_big_banana_backend_returns_bytes_on_success():
    """大香蕉绘图管线成功时应返回图片字节并带上参考图。"""
    generate = load_comic_service_method("_generate_via_big_banana")
    fake_image_resource = _install_fake_big_banana_image_resource()

    async def scenario():
        pipeline = SimpleNamespace(
            run=AsyncMock(
                return_value=SimpleNamespace(
                    images=[SimpleNamespace(bytes=b"comic-img")],
                    error_message=None,
                )
            )
        )
        plugin = SimpleNamespace(drawing_pipeline=pipeline)
        context = SimpleNamespace(
            get_registered_star=Mock(
                return_value=SimpleNamespace(star_cls=plugin, activated=True)
            )
        )
        service = SimpleNamespace(
            context=context,
            config_manager=SimpleNamespace(
                get_drawing_aspect_ratio=Mock(return_value="16:9"),
                get_drawing_image_size=Mock(return_value="2K"),
            ),
            _map_comic_image_size=Mock(return_value="2K"),
            _import_big_banana_image_resource=Mock(return_value=fake_image_resource),
        )

        result = await generate(
            service,
            "prompt",
            [(b"\x89PNG\r\n\x1a\nimage", "image/png")],
        )

        assert result == b"comic-img"
        pipeline.run.assert_awaited_once()
        call_args = pipeline.run.call_args[0]
        params, image_list = call_args
        assert params["aspect_ratio"] == "16:9"
        assert params["image_size"] == "2K"
        assert len(image_list) == 1
        assert fake_image_resource.from_bytes is not None

    asyncio.run(scenario())


def test_big_banana_backend_returns_none_on_provider_error():
    """大香蕉提供商返回错误消息时应回退（返回 None）。"""
    generate = load_comic_service_method("_generate_via_big_banana")
    fake_image_resource = _install_fake_big_banana_image_resource()

    async def scenario():
        pipeline = SimpleNamespace(
            run=AsyncMock(
                return_value=SimpleNamespace(
                    images=[], error_message="provider boom"
                )
            )
        )
        plugin = SimpleNamespace(drawing_pipeline=pipeline)
        context = SimpleNamespace(
            get_registered_star=Mock(
                return_value=SimpleNamespace(star_cls=plugin, activated=True)
            )
        )
        service = SimpleNamespace(
            context=context,
            config_manager=SimpleNamespace(
                get_drawing_aspect_ratio=Mock(return_value="16:9"),
                get_drawing_image_size=Mock(return_value="1K"),
            ),
            _map_comic_image_size=Mock(return_value="1K"),
            _import_big_banana_image_resource=Mock(return_value=fake_image_resource),
        )

        result = await generate(service, "prompt", None)

        assert result is None

    asyncio.run(scenario())


def test_import_big_banana_image_resource_derives_package_from_module():
    """应从插件类模块路径推导包名导入 ImageResource。"""
    import sys
    from types import ModuleType

    loader = load_comic_service_method("_import_big_banana_image_resource")

    fake_image_resource = type("ImageResource", (), {})
    schemas = ModuleType("data.plugins.astrbot_plugin_big_banana.core.schemas")
    schemas.ImageResource = fake_image_resource
    core = ModuleType("data.plugins.astrbot_plugin_big_banana.core")
    core.schemas = schemas
    pkg = ModuleType("data.plugins.astrbot_plugin_big_banana")
    pkg.core = core
    sys.modules["data.plugins.astrbot_plugin_big_banana"] = pkg
    sys.modules["data.plugins.astrbot_plugin_big_banana.core"] = core
    sys.modules["data.plugins.astrbot_plugin_big_banana.core.schemas"] = schemas

    class FakePlugin:
        pass

    FakePlugin.__module__ = "data.plugins.astrbot_plugin_big_banana.main"
    try:
        assert loader(FakePlugin()) is fake_image_resource
    finally:
        for name in list(sys.modules):
            if name.startswith("data.plugins.astrbot_plugin_big_banana"):
                del sys.modules[name]


def test_import_big_banana_image_resource_returns_none_when_unavailable():
    """无法推导包名且直接导入失败时返回 None。"""
    import sys

    for name in [
        n
        for n in sys.modules
        if n == "astrbot_plugin_big_banana"
        or n.startswith("astrbot_plugin_big_banana.")
    ]:
        del sys.modules[name]

    loader = load_comic_service_method("_import_big_banana_image_resource")
    assert loader(SimpleNamespace()) is None


def test_generate_comic_prefers_big_banana_backend():
    """配置 big_banana 后端时优先走大香蕉，不调用内置绘图客户端。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_reference_image=Mock(return_value=""),
        )
        llm_analyzer = SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(
                return_value=([{"scene": "comic scene prompt"}], None)
            )
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = SimpleNamespace(
            config_manager=config_manager,
            llm_analyzer=llm_analyzer,
            drawing_client=drawing_client,
            _fetch_reference_image=AsyncMock(),
            _generate_via_big_banana=AsyncMock(return_value=b"comic-bytes"),
            _generate_via_general_plugin=AsyncMock(),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes == b"comic-bytes"
        assert fallback_url is None
        service._generate_via_big_banana.assert_awaited_once()
        service._generate_via_general_plugin.assert_not_called()
        drawing_client.generate_image.assert_not_called()

    asyncio.run(scenario())


def test_generate_comic_falls_back_to_builtin_when_big_banana_empty():
    """大香蕉后端无结果时应回退内置绘图客户端。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_reference_image=Mock(return_value=""),
            get_drawing_output_exception_retry_keywords=Mock(return_value=[]),
            get_drawing_external_fallback=Mock(return_value=True),
            get_drawing_api_url=Mock(return_value="https://api.openai.com/v1"),
            get_drawing_api_key=Mock(return_value="sk-test"),
        )
        llm_analyzer = SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(
                return_value=([{"scene": "comic scene prompt"}], None)
            )
        )
        drawing_client = SimpleNamespace(
            generate_image=AsyncMock(return_value=(b"builtin-bytes", None))
        )
        service = SimpleNamespace(
            config_manager=config_manager,
            llm_analyzer=llm_analyzer,
            drawing_client=drawing_client,
            _fetch_reference_image=AsyncMock(),
            _generate_via_big_banana=AsyncMock(return_value=None),
            _generate_via_general_plugin=AsyncMock(),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes == b"builtin-bytes"
        assert fallback_url is None
        drawing_client.generate_image.assert_awaited_once()

    asyncio.run(scenario())


def test_generate_comic_skips_builtin_when_external_fallback_disabled():
    """关闭回退开关时，外部后端失败应直接取消漫画，不调用内置客户端。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_reference_image=Mock(return_value=""),
            get_drawing_external_fallback=Mock(return_value=False),
        )
        llm_analyzer = SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(
                return_value=([{"scene": "comic scene prompt"}], None)
            )
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = SimpleNamespace(
            config_manager=config_manager,
            llm_analyzer=llm_analyzer,
            drawing_client=drawing_client,
            _fetch_reference_image=AsyncMock(),
            _generate_via_big_banana=AsyncMock(return_value=None),
            _generate_via_general_plugin=AsyncMock(),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes is None
        assert fallback_url is None
        drawing_client.generate_image.assert_not_called()

    asyncio.run(scenario())


def test_generate_comic_skips_unconfigured_builtin_backend():
    """外部后端失败且内置后端未配置时，应直接取消漫画，不向默认地址发空请求。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_reference_image=Mock(return_value=""),
            get_drawing_external_fallback=Mock(return_value=True),
            get_drawing_api_url=Mock(return_value=""),
            get_drawing_api_key=Mock(return_value=""),
        )
        llm_analyzer = SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(
                return_value=([{"scene": "comic scene prompt"}], None)
            )
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = SimpleNamespace(
            config_manager=config_manager,
            llm_analyzer=llm_analyzer,
            drawing_client=drawing_client,
            _fetch_reference_image=AsyncMock(),
            _generate_via_big_banana=AsyncMock(return_value=None),
            _generate_via_general_plugin=AsyncMock(),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes is None
        assert fallback_url is None
        drawing_client.generate_image.assert_not_called()

    asyncio.run(scenario())
