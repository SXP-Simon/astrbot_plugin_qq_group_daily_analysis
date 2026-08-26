import ast
import asyncio
import hashlib
import json
import mimetypes
import os
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any
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
    from src.shared.trace_context import TraceContext

    namespace = {
        "AsyncGenerator": object,
        "AstrMessageEvent": object,
        "DuplicateGroupTaskError": RuntimeError,
        "asyncio": asyncio,
        "logger": Mock(),
        "os": os,
        "PLUGIN_NAME": "test_plugin",
        "StarTools": SimpleNamespace(get_data_dir=Mock()),
        "TraceContext": TraceContext,
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
    from contextlib import nullcontext
    from src.shared.trace_context import TraceContext

    namespace = {
        "Path": Path,
        "mimetypes": mimetypes,
        "logger": Mock(),
        "Any": Any,
        "TraceContext": TraceContext,
        "nullcontext": nullcontext,
    }
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
        "_migrate_daily_comic_character_prompts",
        "_protect_upgrade_data",
        "_protect_custom_t2i_templates",
        "_read_upgrade_protection_state",
        "_save_upgrade_protection_state",
        "_write_upgrade_config_backup",
        "_write_comic_config_backup",
        "_copy_legacy_comic_reference_images",
        "get_use_plugin_specific_persona",
        "get_plugin_specific_persona_id",
        "_is_group_match",
        "get_group_list_mode",
        "get_group_list",
        "is_group_allowed",
        "is_auto_analysis_enabled",
        "get_scheduled_group_list_mode",
        "get_scheduled_group_list",
        "is_scheduled_group_allowed",
        "is_group_in_filtered_list",
        "get_incremental_enabled",
        "get_incremental_group_list_mode",
        "get_incremental_group_list",
        "is_incremental_group_allowed",
        "get_enable_daily_comic",
        "get_enable_auto_daily_comic",
        "get_comic_group_list_mode",
        "get_comic_group_list",
        "is_comic_group_allowed",
        "get_drawing_provider_configs",
        "get_drawing_proxy",
        "get_drawing_reference_image",
        "get_drawing_reference_images",
        "get_custom_report_template_dir",
        "get_t2i_rendering_strategies",
        "get_comic_storyboard_prompt",
        "get_selected_comic_character",
        "get_comic_character_persona_id",
        "get_comic_character_storyboard_prompt",
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


def test_existing_comic_character_inherits_global_storyboard_prompt(tmp_path: Path):
    """升级时既有角色应保留当时的全局分镜提示词。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config = Config(
        daily_comic={"comic_characters": [{"name": "角色甲", "reference_images": []}]},
        prompts={"comic_analysis_prompts": {"comic_storyboard_prompt": "旧版全局模板"}},
    )
    config_manager = config_manager_class(config)

    character = config["daily_comic"]["comic_characters"][0]
    assert character["storyboard_prompt"] == "旧版全局模板"
    assert (
        config_manager.get_comic_character_storyboard_prompt(character)
        == "旧版全局模板"
    )
    config.save_config.assert_called_once()


def test_comic_character_empty_storyboard_prompt_falls_back_to_global(tmp_path: Path):
    """新角色留空专属模板时应使用全局默认模板。"""
    config_manager_class = load_config_manager_class(tmp_path)
    config_manager = object.__new__(config_manager_class)
    config_manager.config = {
        "prompts": {
            "comic_analysis_prompts": {"comic_storyboard_prompt": "全局默认模板"}
        }
    }

    assert (
        config_manager.get_comic_character_storyboard_prompt({"storyboard_prompt": ""})
        == "全局默认模板"
    )


def test_comic_generation_passes_character_storyboard_prompt():
    """漫画生成应把选中角色的专属模板传给分镜分析器。"""
    generate_comic = load_comic_service_method("generate_comic")
    topics = [{"topic": "话题", "detail": "详情"}]
    character = {"name": "角色甲", "storyboard_prompt": "角色模板"}
    llm_analyzer = SimpleNamespace(
        analyze_comic_storyboards=AsyncMock(return_value=([], object()))
    )
    config_manager = SimpleNamespace(
        get_enable_daily_comic=Mock(return_value=True),
        get_selected_comic_character=Mock(return_value=character),
        get_comic_character_persona_id=Mock(return_value="persona-a"),
        get_comic_character_storyboard_prompt=Mock(return_value="角色模板"),
    )
    service = SimpleNamespace(
        config_manager=config_manager,
        llm_analyzer=llm_analyzer,
    )

    asyncio.run(generate_comic(service, topics, "123456", "umo"))

    llm_analyzer.analyze_comic_storyboards.assert_awaited_once_with(
        topics,
        "umo",
        persona_id="persona-a",
        prompt_template="角色模板",
    )


def test_comic_character_schema_has_storyboard_prompt_default():
    """新建角色方案时应自带可编辑的默认分镜提示词。"""
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    character_prompt = schema["daily_comic"]["items"]["comic_characters"]["templates"][
        "character"
    ]["items"]["storyboard_prompt"]["default"]
    global_prompt = schema["prompts"]["items"]["comic_analysis_prompts"]["items"][
        "comic_storyboard_prompt"
    ]["default"]

    assert schema["daily_comic"]["items"]["comic_characters"]["default"] == []
    assert character_prompt.strip()
    assert character_prompt == global_prompt


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


def test_comic_generation_observes_comic_group_filter():
    """漫画名单拒绝当前群时不应创建漫画任务。"""
    trigger_comic = load_main_method("_try_trigger_comic_generation")
    plugin = SimpleNamespace(
        _terminating=False,
        config_manager=SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            is_comic_group_allowed=Mock(return_value=False),
        ),
        _comic_group_tasks={},
        _background_tasks=set(),
        _trigger_comic_generation=AsyncMock(),
    )

    status = trigger_comic(
        plugin,
        "123456",
        "onebot-main",
        {"topics": [{"topic": "测试话题", "detail": "详情"}]},
    )

    assert status == "blocked"
    plugin.config_manager.is_comic_group_allowed.assert_called_once_with(
        "onebot-main:GroupMessage:123456", True
    )
    plugin._trigger_comic_generation.assert_not_called()
    assert plugin._comic_group_tasks == {}
    assert plugin._background_tasks == set()


def test_auto_comic_switch_skips_report_trigger():
    """关闭自动联动时，报告入口不应创建漫画任务。"""
    trigger_comic = load_main_method("_try_trigger_comic_generation")
    plugin = SimpleNamespace(
        _terminating=False,
        config_manager=SimpleNamespace(
            get_enable_daily_comic=Mock(return_value=True),
            get_enable_auto_daily_comic=Mock(return_value=False),
            is_comic_group_allowed=Mock(return_value=True),
        ),
        _comic_group_tasks={},
        _background_tasks=set(),
        _trigger_comic_generation=AsyncMock(),
    )

    status = trigger_comic(
        plugin,
        "123456",
        "onebot-main",
        {"topics": [{"topic": "测试话题", "detail": "详情"}]},
    )

    assert status == "auto_disabled"
    plugin.config_manager.is_comic_group_allowed.assert_not_called()
    plugin._trigger_comic_generation.assert_not_called()


def test_standalone_comic_command_is_decoupled_from_analysis_permission():
    """手动漫画命令不应直接检查分析名单，避免只开漫画时被分析权限拦住。"""
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
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "generate_group_comic"
    )
    attribute_names = {
        node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute)
    }

    assert "is_group_allowed" not in attribute_names
    assert "get_enable_daily_comic" in attribute_names
    assert "is_comic_group_allowed" in attribute_names
    assert "execute_comic_topic_analysis" in attribute_names


def test_comic_group_filter_defaults_to_inherit_basic_permission(tmp_path: Path):
    """默认漫画名单应继承基础群权限，避免重复填写名单。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config_manager = config_manager_class(
        Config(
            basic={
                "group_list_mode": "whitelist",
                "group_list": ["onebot-main:GroupMessage:123456"],
            },
            daily_comic={},
        )
    )

    assert config_manager.get_comic_group_list_mode() == "inherit"
    assert config_manager.get_comic_group_list() == []
    assert config_manager.is_comic_group_allowed("onebot-main:GroupMessage:123456")
    assert not config_manager.is_comic_group_allowed("onebot-main:GroupMessage:654321")


def test_comic_group_filter_can_override_basic_permission(tmp_path: Path):
    """只开放漫画时，漫画名单可独立放行未启用分析的群。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config_manager = config_manager_class(
        Config(
            basic={"group_list_mode": "whitelist", "group_list": []},
            daily_comic={"comic_group_list_mode": "blacklist", "comic_group_list": []},
        )
    )

    assert not config_manager.is_group_allowed("onebot-main:GroupMessage:123456")
    assert config_manager.is_comic_group_allowed("onebot-main:GroupMessage:123456")


def test_comic_group_filter_supports_whitelist_and_blacklist(tmp_path: Path):
    """漫画名单应复用 UMO 与纯群号兼容匹配。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    whitelist_manager = config_manager_class(
        Config(
            daily_comic={
                "comic_group_list_mode": "whitelist",
                "comic_group_list": ["onebot-main:GroupMessage:123456"],
            }
        )
    )
    assert whitelist_manager.is_comic_group_allowed("onebot-main:GroupMessage:123456")
    assert not whitelist_manager.is_comic_group_allowed("telegram:GroupMessage:123456")

    blacklist_manager = config_manager_class(
        Config(
            daily_comic={
                "comic_group_list_mode": "blacklist",
                "comic_group_list": ["123456"],
            }
        )
    )
    assert not blacklist_manager.is_comic_group_allowed(
        "onebot-main:GroupMessage:123456"
    )
    assert blacklist_manager.is_comic_group_allowed("onebot-main:GroupMessage:654321")


def test_scheduled_and_incremental_inherit_chain(tmp_path: Path):
    """定时继承基础、增量继承定时，且 inherit 忽略自身列表。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config_manager = config_manager_class(
        Config(
            basic={
                "group_list_mode": "whitelist",
                "group_list": ["onebot-main:GroupMessage:123456"],
            },
            auto_analysis={
                "scheduled_group_list_mode": "inherit",
                "scheduled_group_list": ["onebot-main:GroupMessage:654321"],
            },
            incremental={
                "incremental_group_list_mode": "inherit",
                "incremental_group_list": ["onebot-main:GroupMessage:654321"],
            },
        )
    )

    allowed_group = "onebot-main:GroupMessage:123456"
    blocked_group = "onebot-main:GroupMessage:654321"
    assert config_manager.is_auto_analysis_enabled()
    assert config_manager.is_scheduled_group_allowed(allowed_group)
    assert not config_manager.is_scheduled_group_allowed(blocked_group)
    assert config_manager.get_incremental_enabled()
    assert config_manager.is_incremental_group_allowed(allowed_group)
    assert not config_manager.is_incremental_group_allowed(blocked_group)


def test_inherited_incremental_uses_scheduled_final_result(tmp_path: Path):
    """增量 inherit 必须继承定时名单的最终结果，而不是直接继承基础名单。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config_manager = config_manager_class(
        Config(
            basic={"group_list_mode": "none", "group_list": []},
            auto_analysis={
                "scheduled_group_list_mode": "whitelist",
                "scheduled_group_list": ["onebot-main:GroupMessage:123456"],
            },
            incremental={"incremental_group_list_mode": "inherit"},
        )
    )

    assert config_manager.is_incremental_group_allowed(
        "onebot-main:GroupMessage:123456"
    )
    assert not config_manager.is_incremental_group_allowed(
        "onebot-main:GroupMessage:654321"
    )


def test_inherit_modes_do_not_change_default_disabled_behavior(tmp_path: Path):
    """未显式选择 inherit 时，空白名单仍不会意外开启自动或增量任务。"""
    config_manager_class = load_config_manager_class(tmp_path)

    class Config(dict):
        save_config = Mock()

    config_manager = config_manager_class(
        Config(
            basic={"group_list_mode": "none", "group_list": []},
            auto_analysis={},
            incremental={},
        )
    )

    assert not config_manager.is_auto_analysis_enabled()
    assert not config_manager.get_incremental_enabled()


def test_comic_schema_exposes_group_filter():
    """配置面板应公开漫画专用名单，不复用分析报告名单。"""
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    comic_items = schema["daily_comic"]["items"]

    assert comic_items["comic_group_list_mode"]["default"] == "inherit"
    assert comic_items["comic_group_list_mode"]["options"] == [
        "inherit",
        "whitelist",
        "blacklist",
    ]
    assert comic_items["comic_group_list"]["type"] == "list"
    assert comic_items["enable_auto_daily_comic"]["default"] is True


def test_analysis_schema_exposes_inherit_modes():
    """定时和增量名单配置应公开 inherit 模式。"""
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )

    assert (
        "inherit"
        in schema["auto_analysis"]["items"]["scheduled_group_list_mode"]["options"]
    )
    assert (
        "inherit"
        in schema["incremental"]["items"]["incremental_group_list_mode"]["options"]
    )


def _comic_config_manager(**overrides):
    """构造 generate_comic 所需的配置替身。"""
    defaults = {
        "get_enable_daily_comic": Mock(return_value=True),
        "get_selected_comic_character": Mock(return_value=None),
        "get_comic_character_persona_id": Mock(return_value=""),
        "get_comic_character_storyboard_prompt": Mock(return_value=""),
        "get_drawing_reference_images": Mock(return_value=[]),
        "get_drawing_backend": Mock(return_value="big_banana"),
        "get_drawing_external_fallback": Mock(return_value=True),
        "get_drawing_provider_configs": Mock(return_value=[{"name": "x"}]),
        "get_drawing_output_exception_retry_keywords": Mock(return_value=[]),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _comic_service(config_manager, drawing_client, **methods):
    """构造 generate_comic 所需的漫画服务替身。"""
    service = {
        "config_manager": config_manager,
        "llm_analyzer": SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(
                return_value=([{"scene": "comic scene prompt"}], None)
            )
        ),
        "drawing_client": drawing_client,
        "_fetch_reference_image": AsyncMock(),
        "_generate_via_big_banana": AsyncMock(return_value=None),
        "_generate_via_general_plugin": AsyncMock(return_value=None),
    }
    service.update(methods)
    return SimpleNamespace(**service)


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

    class FakeImageResource:
        """模拟大香蕉解析参考图后使用的最小图片资源对象。"""

        @staticmethod
        def from_bytes(data_bytes: bytes) -> SimpleNamespace:
            return SimpleNamespace(bytes=data_bytes, mime="image/png")

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
            _import_big_banana_image_resource=Mock(return_value=FakeImageResource),
        )

        result = await generate(
            service,
            "prompt",
            [(b"\x89PNG\r\n\x1a\nimage", "image/png")],
        )

        assert result == b"comic-img"
        pipeline.run.assert_awaited_once()
        params, image_list = pipeline.run.call_args[0]
        assert params["aspect_ratio"] == "16:9"
        assert len(image_list) == 1

    asyncio.run(scenario())


def test_big_banana_backend_returns_none_on_provider_error():
    """大香蕉提供商返回错误消息时应回退（返回 None）。"""
    generate = load_comic_service_method("_generate_via_big_banana")

    class FakeImageResource:
        """模拟大香蕉图片资源类型，避免污染解释器模块缓存。"""

        @staticmethod
        def from_bytes(data_bytes: bytes) -> SimpleNamespace:
            return SimpleNamespace(bytes=data_bytes, mime="image/png")

    async def scenario():
        pipeline = SimpleNamespace(
            run=AsyncMock(
                return_value=SimpleNamespace(images=[], error_message="provider boom")
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
            _import_big_banana_image_resource=Mock(return_value=FakeImageResource),
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
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="big_banana")
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = _comic_service(
            config_manager,
            drawing_client,
            _generate_via_big_banana=AsyncMock(return_value=b"comic-bytes"),
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


def test_generate_comic_prefers_general_plugin_backend():
    """配置 general_plugin 后端时优先走通用生图插件。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="general_plugin")
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = _comic_service(
            config_manager,
            drawing_client,
            _generate_via_general_plugin=AsyncMock(return_value=b"comic-bytes"),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes == b"comic-bytes"
        assert fallback_url is None
        service._generate_via_general_plugin.assert_awaited_once()
        service._generate_via_big_banana.assert_not_called()
        drawing_client.generate_image.assert_not_called()

    asyncio.run(scenario())


def test_generate_comic_falls_back_to_builtin_when_big_banana_empty():
    """大香蕉后端无结果时应回退内置绘图客户端。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_external_fallback=Mock(return_value=True),
            get_drawing_provider_configs=Mock(return_value=[{"name": "x"}]),
        )
        drawing_client = SimpleNamespace(
            generate_image=AsyncMock(return_value=(b"builtin-bytes", None))
        )
        service = _comic_service(config_manager, drawing_client)

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
    """关闭回退开关时，外部后端失败应直接取消漫画。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_external_fallback=Mock(return_value=False),
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = _comic_service(config_manager, drawing_client)

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
    """外部后端失败且内置后端未配置供应商时，应直接取消漫画。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="big_banana"),
            get_drawing_external_fallback=Mock(return_value=True),
            get_drawing_provider_configs=Mock(return_value=[]),
        )
        drawing_client = SimpleNamespace(generate_image=AsyncMock())
        service = _comic_service(config_manager, drawing_client)

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


def test_generate_comic_rejects_builtin_response_identical_to_reference_image():
    """内建绘图原样回传参考图时不应将其作为漫画发送。"""
    generate_comic = load_comic_service_method("generate_comic")

    async def scenario():
        reference = b"reference-image"
        config_manager = _comic_config_manager(
            get_drawing_backend=Mock(return_value="builtin"),
            get_drawing_reference_images=Mock(return_value=["reference.png"]),
        )
        drawing_client = SimpleNamespace(
            generate_image=AsyncMock(return_value=(reference, None))
        )
        service = _comic_service(
            config_manager,
            drawing_client,
            _fetch_reference_image=AsyncMock(return_value=(reference, "image/png")),
        )

        comic_bytes, fallback_url = await generate_comic(
            service,
            [{"topic": "t1", "detail": "d1"}],
            "123456",
            "umo",
        )

        assert comic_bytes is None
        assert fallback_url is None

    asyncio.run(scenario())


def test_detect_image_ext_sniffs_bytes():
    """应从图片字节嗅探扩展名，无法识别时回退 .png。"""
    detect = load_main_method("_detect_image_ext")
    assert detect(b"\x89PNG\r\n\x1a\nrest") == ".png"
    assert detect(b"\xff\xd8\xffjpeg") == ".jpg"
    assert detect(b"RIFF....WEBP") == ".webp"
    assert detect(b"GIF87a....") == ".gif"
    assert detect(b"GIF89a....") == ".gif"
    assert detect(b"\x00\x00\x00\x18ftypavif....") == ".avif"
    assert detect(b"\x00\x00\x00\x18ftypavis....") == ".avif"
    assert detect(b"unknown-bytes") == ".png"


def test_comic_delivery_sniffs_cached_file_extension_after_generation(tmp_path):
    """漫画生成成功后应按真实图片字节缓存，不能读取已删除的全局输出格式。

    外部绘图后端可以返回与内置供应商配置不同的编码格式。此处覆盖从生成结果到
    发送、相册上传的完整路径，确保 JPEG 不会因旧的 ``get_drawing_output_format``
    回退逻辑触发 AttributeError 或被错误保存为 PNG。
    """
    trigger_comic = load_main_method("_trigger_comic_generation")
    detect_image_ext = load_main_method("_detect_image_ext")
    trigger_comic.__globals__["StarTools"] = SimpleNamespace(
        get_data_dir=Mock(return_value=tmp_path)
    )
    adapter = SimpleNamespace(send_image=AsyncMock())
    comic_bytes = b"\xff\xd8\xffjpeg-payload"
    plugin = SimpleNamespace(
        _comic_semaphore=asyncio.Semaphore(1),
        _terminating=False,
        _detect_image_ext=detect_image_ext,
        comic_service=SimpleNamespace(
            generate_comic=AsyncMock(return_value=(comic_bytes, None))
        ),
        bot_manager=SimpleNamespace(get_adapter=Mock(return_value=adapter)),
        _try_upload_image=AsyncMock(),
    )

    asyncio.run(trigger_comic(plugin, [{"topic": "测试"}], "123456", "onebot", "umo"))

    sent_path = adapter.send_image.await_args.args[1]
    assert sent_path.endswith(".jpg")
    assert not Path(sent_path).exists()
    plugin._try_upload_image.assert_awaited_once_with(
        "123456", sent_path, "onebot", is_comic=True
    )


def test_comic_album_upload_sniffs_local_cached_image_extension(tmp_path):
    """漫画相册上传应从本地缓存内容识别格式，而不是默认标记为 PNG。"""
    upload_image = load_main_method("_try_upload_image")
    detect_image_ext = load_main_method("_detect_image_ext")
    image_path = tmp_path / "comic_cache" / "comic.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"\xff\xd8\xffjpeg-payload")
    adapter = SimpleNamespace(
        get_group_info=AsyncMock(return_value=None),
        upload_group_album=AsyncMock(),
    )
    plugin = SimpleNamespace(
        config_manager=SimpleNamespace(
            get_enable_comic_album_upload=Mock(return_value=True),
            get_comic_album_name=Mock(return_value="comic"),
            get_group_album_strict_mode=Mock(return_value=False),
        ),
        bot_manager=SimpleNamespace(get_adapter=Mock(return_value=adapter)),
        _detect_image_ext=detect_image_ext,
    )

    asyncio.run(upload_image(plugin, "123456", str(image_path), "onebot", True))

    adapter.upload_group_album.assert_awaited_once_with(
        "123456",
        str(image_path.resolve()),
        album_id=None,
        album_name="comic",
        strict_mode=False,
    )
