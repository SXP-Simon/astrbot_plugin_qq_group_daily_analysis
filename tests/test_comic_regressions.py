import ast
import asyncio
import hashlib
import json
import mimetypes
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfoNotFoundError

from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.templates import HTMLTemplates


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
        "_get_plugin_root",
        "_get_plugin_version",
        "_get_schema_fingerprint",
        "_migrate_daily_comic_characters",
        "_protect_upgrade_data",
        "_protect_custom_t2i_templates",
        "_read_upgrade_protection_state",
        "_save_upgrade_protection_state",
        "_write_upgrade_config_backup",
        "_write_comic_config_backup",
        "_copy_legacy_comic_reference_images",
        "get_use_plugin_specific_persona",
        "get_plugin_specific_persona_id",
        "get_drawing_reference_image",
        "get_custom_report_template_dir",
        "get_t2i_rendering_strategies",
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
        "__file__": str(config_path),
        "Path": Path,
        "hashlib": hashlib,
        "os": __import__("os"),
        "datetime": __import__("datetime").datetime,
        "ZoneInfo": __import__("zoneinfo").ZoneInfo,
        "ZoneInfoNotFoundError": ZoneInfoNotFoundError,
        "json": json,
        "random": __import__("random"),
        "re": re,
        "shutil": shutil,
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


def test_daily_random_character_uses_tz_environment_variable(
    tmp_path: Path, monkeypatch
):
    """每日随机角色的日期边界应优先使用 TZ 环境变量。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config = Config(
        daily_comic={
            "random_daily_comic_character": True,
            "comic_characters": [{"name": "角色甲", "enable": True}],
        }
    )
    config_manager = config_manager_class(config)
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")

    original_datetime = config_manager_class.get_selected_comic_character.__globals__[
        "datetime"
    ]
    observed_timezones = []

    class FixedDateTime:
        @classmethod
        def now(cls, timezone=None):
            observed_timezones.append(timezone)
            return original_datetime(2026, 8, 12, 0, 30, tzinfo=timezone)

    config_manager_class.get_selected_comic_character.__globals__["datetime"] = (
        FixedDateTime
    )
    try:
        config_manager.get_selected_comic_character()
    finally:
        config_manager_class.get_selected_comic_character.__globals__["datetime"] = (
            original_datetime
        )

    assert observed_timezones[0].key == "Pacific/Kiritimati"


def test_reference_image_migration_keeps_old_config_when_backup_fails(tmp_path: Path):
    """备份失败时不得清空旧参考图配置。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config = Config(daily_comic={})
    config_manager = config_manager_class(config)
    config["daily_comic"]["drawing_reference_image"] = "https://example.com/a.png"
    config_manager._write_comic_config_backup = Mock(return_value=False)

    config_manager._migrate_daily_comic_characters()

    assert (
        config["daily_comic"]["drawing_reference_image"] == "https://example.com/a.png"
    )
    config.save_config.assert_not_called()


def test_upgrade_config_backup_requires_schema_change(tmp_path: Path):
    """仅配置结构变更才备份，版本只作为旧快照的标识。"""
    config_manager_class = load_config_manager_class(tmp_path)
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    metadata_path = plugin_root / "metadata.yaml"
    schema_path = plugin_root / "_conf_schema.json"
    metadata_path.write_text("version: v1.0.0\n", encoding="utf-8")
    schema_path.write_text(
        json.dumps(
            {
                "basic": {
                    "type": "object",
                    "items": {"old": {"type": "int", "default": 1}},
                }
            }
        ),
        encoding="utf-8",
    )
    config_manager_class._get_plugin_root = staticmethod(lambda: plugin_root)

    class Config(dict):
        save_config = Mock()

    config_manager_class(Config(basic={"old": 7}))
    metadata_path.write_text("version: v1.0.1\n", encoding="utf-8")
    config_manager_class(Config(basic={"old": 7}))
    backup_dir = tmp_path / "config_backups"
    assert not list(backup_dir.glob("plugin_config_*.json"))

    schema_path.write_text(
        json.dumps(
            {
                "basic": {
                    "type": "object",
                    "items": {"new": {"type": "int", "default": 2}},
                }
            }
        ),
        encoding="utf-8",
    )
    config_manager_class(Config(basic={"new": 2}))

    backups = list(backup_dir.glob("plugin_config_v1.0.1_*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["config"] == {
        "basic": {"old": 7}
    }


def test_upgrade_config_backups_keep_only_twenty_newest(tmp_path: Path):
    """插件配置备份超过二十份时应清理最早文件。"""
    config_manager_class = load_config_manager_class(tmp_path)
    backup_dir = tmp_path / "config_backups"
    backup_dir.mkdir()
    for index in range(20):
        backup_path = backup_dir / f"plugin_config_v1.0.0_20260812_00000{index}.json"
        backup_path.write_text("{}", encoding="utf-8")

    config_manager = object.__new__(config_manager_class)
    assert config_manager._write_upgrade_config_backup({"basic": {}}, "v1.0.1")

    backups = sorted(backup_dir.glob("plugin_config_*.json"))
    assert len(backups) == 20
    assert not (backup_dir / "plugin_config_v1.0.0_20260812_000000.json").exists()


def test_t2i_rendering_strategies_explicitly_set_desktop_viewport(tmp_path: Path):
    """图片报告应显式传入视口，避免依赖 T2I 服务的默认尺寸。"""
    config_manager_class = load_config_manager_class(tmp_path)
    config_manager = object.__new__(config_manager_class)
    config_manager.config = {
        "t2i_rendering": {
            "t2i_viewport_width": 1360,
            "t2i_viewport_height": 900,
        }
    }

    strategies = config_manager.get_t2i_rendering_strategies()

    assert len(strategies) == 2
    assert all(strategy["viewport_width"] == 1360 for strategy in strategies)
    assert all(strategy["viewport_height"] == 900 for strategy in strategies)


def test_t2i_viewport_fallback_respects_numeric_template_meta():
    """固定数字 meta 应优先于插件兜底视口。"""
    options, description = ReportGenerator._resolve_t2i_viewport_options(
        '<meta name="viewport" content="width=980, height=590">',
        {"viewport_width": 1440, "viewport_height": 900},
    )

    assert "viewport_width" not in options
    assert "viewport_height" not in options
    assert description == "模板width=980，模板height=590"


def test_t2i_viewport_fallback_only_fills_missing_meta_dimension():
    """模板只指定宽度时，插件只补充高度兜底。"""
    options, description = ReportGenerator._resolve_t2i_viewport_options(
        '<meta name="viewport" content="width=980, initial-scale=1">',
        {"viewport_width": 1440, "viewport_height": 900},
    )

    assert "viewport_width" not in options
    assert options["viewport_height"] == 900
    assert description == "模板width=980，兜底height=900"


def test_custom_t2i_template_is_copied_after_user_edit(tmp_path: Path):
    """模板哈希变化时应保留用户修改的副本。"""
    config_manager_class = load_config_manager_class(tmp_path)
    plugin_root = tmp_path / "plugin"
    template_path = (
        plugin_root
        / "src"
        / "infrastructure"
        / "reporting"
        / "templates"
        / "simple"
        / "image_template.html"
    )
    template_path.parent.mkdir(parents=True)
    template_path.write_text("官方模板", encoding="utf-8")
    (plugin_root / "metadata.yaml").write_text("version: v1.0.0\n", encoding="utf-8")
    (plugin_root / "_conf_schema.json").write_text("{}", encoding="utf-8")
    config_manager_class._get_plugin_root = staticmethod(lambda: plugin_root)

    class Config(dict):
        save_config = Mock()

    config_manager_class(Config())
    template_path.write_text("用户修改模板", encoding="utf-8")
    config_manager_class(Config())

    protected_template = (
        tmp_path
        / "custom_t2i_templates"
        / "reporting_templates"
        / "simple"
        / "image_template.html"
    )
    assert protected_template.read_text(encoding="utf-8") == "用户修改模板"


def test_standalone_t2i_template_is_copied_on_first_start(tmp_path: Path):
    """插件目录中的独立 T2I 模板首次启动即应归档。"""
    config_manager_class = load_config_manager_class(tmp_path)
    plugin_root = tmp_path / "plugin"
    standalone_template = plugin_root / "data" / "t2i_templates" / "custom.html"
    standalone_template.parent.mkdir(parents=True)
    standalone_template.write_text("独立自定义模板", encoding="utf-8")
    (plugin_root / "metadata.yaml").write_text("version: v1.0.0\n", encoding="utf-8")
    (plugin_root / "_conf_schema.json").write_text("{}", encoding="utf-8")
    config_manager_class._get_plugin_root = staticmethod(lambda: plugin_root)

    class Config(dict):
        save_config = Mock()

    config_manager_class(Config())

    protected_template = (
        tmp_path / "custom_t2i_templates" / "standalone_templates" / "custom.html"
    )
    assert protected_template.read_text(encoding="utf-8") == "独立自定义模板"


def test_custom_report_template_overrides_only_matching_file(tmp_path: Path):
    """用户模板副本应优先加载，缺失文件仍回退到内置模板。"""
    builtin_template_dir = tmp_path / "builtin" / "simple"
    custom_template_dir = tmp_path / "custom" / "simple"
    builtin_template_dir.mkdir(parents=True)
    custom_template_dir.mkdir(parents=True)
    (builtin_template_dir / "image_template.html").write_text(
        "内置图片模板", encoding="utf-8"
    )
    (builtin_template_dir / "topic_item.html").write_text(
        "内置话题模板", encoding="utf-8"
    )
    (custom_template_dir / "image_template.html").write_text(
        "用户图片模板", encoding="utf-8"
    )
    templates = HTMLTemplates(
        SimpleNamespace(
            get_report_template=Mock(return_value="simple"),
            get_custom_report_template_dir=Mock(return_value=custom_template_dir),
        )
    )
    templates.base_dir = str(tmp_path / "builtin")
    environment = templates._get_env_sync()

    assert environment.get_template("image_template.html").render() == "用户图片模板"
    assert environment.get_template("topic_item.html").render() == "内置话题模板"


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
