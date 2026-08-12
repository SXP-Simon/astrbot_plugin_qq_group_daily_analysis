import ast
import asyncio
import json
import mimetypes
from pathlib import Path
from types import SimpleNamespace
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
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
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
    namespace = {"Path": Path, "mimetypes": mimetypes, "logger": Mock()}
    exec(compile(isolated_module, str(service_path), "exec"), namespace)
    return getattr(namespace["ComicServiceHarness"], name)


def load_config_manager_class(plugin_data_dir: Path):
    """加载漫画配置相关方法，避免测试依赖 AstrBot 运行时。

    Args:
        plugin_data_dir: 用于模拟插件数据目录的临时路径。

    Returns:
        仅包含漫画配置逻辑的 ConfigManager 测试替身类。
    """
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
    required_names = {
        "__init__",
        "_get_group",
        "_migrate_daily_comic_characters",
        "_write_comic_config_backup",
        "_copy_legacy_comic_reference_images",
        "get_use_plugin_specific_persona",
        "get_plugin_specific_persona_id",
        "get_drawing_reference_image",
        "get_selected_comic_character",
        "get_comic_character_persona_id",
        "_get_comic_character_state_path",
        "_read_comic_character_state",
        "_save_comic_character_state",
    }
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
    namespace = {
        "AstrBotConfig": object,
        "StarTools": SimpleNamespace(get_data_dir=Mock(return_value=plugin_data_dir)),
        "PLUGIN_NAME": "test_plugin",
        "Path": Path,
        "datetime": __import__("datetime").datetime,
        "ZoneInfo": __import__("zoneinfo").ZoneInfo,
        "json": json,
        "random": __import__("random"),
        "shutil": __import__("shutil"),
        "logger": Mock(),
    }
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


def test_reference_image_migrates_old_config_and_uses_last_selected_file(
    tmp_path: Path,
):
    """旧参考图应迁移到默认角色方案，并使用最后一次选择的文件。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config = Config(
        daily_comic={"drawing_reference_image": "https://example.com/a.png"}
    )
    config_manager = config_manager_class(config)

    assert config["daily_comic"]["drawing_reference_image"] == []
    config.save_config.assert_called_once()
    assert list((tmp_path / "config_backups").glob("*.json"))

    legacy_directory = tmp_path / "files" / "daily_comic" / "drawing_reference_image"
    legacy_directory.mkdir(parents=True)
    (legacy_directory / "first.png").write_bytes(b"first")
    (legacy_directory / "selected.webp").write_bytes(b"selected")
    config["daily_comic"]["drawing_reference_image"] = [
        "files/daily_comic/drawing_reference_image/first.png",
        "files/daily_comic/drawing_reference_image/selected.webp",
    ]
    config["daily_comic"]["comic_characters"] = []
    config_manager._migrate_daily_comic_characters()

    character = config["daily_comic"]["comic_characters"][0]
    assert character["name"] == "默认角色方案"
    assert character["reference_images"][-1].endswith("selected.webp")
    assert config["daily_comic"]["drawing_reference_image"] == []
    assert (tmp_path / character["reference_images"][-1]).read_bytes() == b"selected"
    assert config_manager.get_drawing_reference_image().endswith("selected.webp")


def test_daily_random_character_is_stable_and_recovers_from_disabled_choice(
    tmp_path: Path,
):
    """每日随机角色应在当天保持不变，禁用后自动选择可用方案。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    first = {
        "__template_key": "character",
        "name": "角色甲",
        "enable": True,
        "persona_id": "persona-a",
        "reference_images": [],
    }
    second = {
        "__template_key": "character",
        "name": "角色乙",
        "enable": True,
        "persona_id": "persona-b",
        "reference_images": [],
    }
    config = Config(
        daily_comic={
            "random_daily_comic_character": True,
            "comic_characters": [first, second],
        }
    )
    config_manager = config_manager_class(config)

    selected = config_manager.get_selected_comic_character()
    assert selected in (first, second)
    assert config_manager.get_selected_comic_character() == selected
    assert config_manager.get_comic_character_persona_id(selected) in {
        "persona-a",
        "persona-b",
    }

    selected["enable"] = False
    assert config_manager.get_selected_comic_character() != selected


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
