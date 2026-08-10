import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


def load_initialization_method():
    """从 main.py 加载真实的初始化方法，避免测试替代实现。

    Returns:
        GroupDailyAnalysis._run_initialization 的可执行函数。
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
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_initialization"
    )
    isolated_class = ast.ClassDef(
        name="InitializationHarness",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[isolated_class], type_ignores=[])
    )

    class TraceLogFilter(logging.Filter):
        pass

    namespace = {
        "TraceLogFilter": TraceLogFilter,
        "astrbot_logger": logging.getLogger("startup-initialization-test"),
        "logger": Mock(),
    }
    exec(compile(isolated_module, str(main_path), "exec"), namespace)
    return namespace["InitializationHarness"]._run_initialization


def load_plugin_initialize_method():
    """从 main.py 加载真实的插件生命周期初始化方法。

    Returns:
        GroupDailyAnalysis.initialize 的可执行函数。
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
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "initialize"
    )
    isolated_class = ast.ClassDef(
        name="InitializationHarness",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[isolated_class], type_ignores=[])
    )
    namespace = {"asyncio": asyncio, "logger": Mock()}
    exec(compile(isolated_module, str(main_path), "exec"), namespace)
    return namespace["InitializationHarness"].initialize


def test_initialization_has_no_fixed_delay_and_preserves_platform_refresh():
    initialization_method = load_initialization_method()
    plugin = SimpleNamespace(
        _init_lock=asyncio.Lock(),
        _terminating=False,
        _initialized=False,
        _discovery_run=False,
        bot_manager=SimpleNamespace(initialize_from_config=AsyncMock()),
        config_manager=SimpleNamespace(
            upgrade_prompt_templates=Mock(),
            migrate_legacy_configs=Mock(),
        ),
        template_preview_router=SimpleNamespace(ensure_handlers_registered=AsyncMock()),
        auto_scheduler=SimpleNamespace(
            schedule_jobs=Mock(),
            start_incremental_trigger=AsyncMock(),
        ),
        context=object(),
    )

    async def run_initializations():
        await initialization_method(plugin, "Plugin Reload/Init")
        await initialization_method(plugin, "Platform Loaded: NapCat")
        await initialization_method(plugin, "Platform Loaded: LLBot")

    # 远低于旧版每次固定等待 5 秒，用超时断言防止慢启动逻辑回归。
    asyncio.run(asyncio.wait_for(run_initializations(), timeout=0.5))

    assert plugin.bot_manager.initialize_from_config.await_count == 3
    assert plugin.template_preview_router.ensure_handlers_registered.await_count == 3
    plugin.config_manager.upgrade_prompt_templates.assert_called_once_with()
    plugin.config_manager.migrate_legacy_configs.assert_called_once_with()
    plugin.auto_scheduler.schedule_jobs.assert_called_once_with(plugin.context)
    plugin.auto_scheduler.start_incremental_trigger.assert_awaited_once_with()
    assert plugin._initialized is True
    assert plugin._discovery_run is True


def test_plugin_lifecycle_waits_for_initialization_task():
    initialize = load_plugin_initialize_method()

    async def run_test():
        initialization_task = asyncio.create_task(asyncio.sleep(0))
        plugin = SimpleNamespace(
            _init_task=initialization_task,
            _terminating=False,
            _initialized=True,
            _run_initialization=AsyncMock(),
        )

        await initialize(plugin)

        plugin._run_initialization.assert_not_awaited()

    asyncio.run(run_test())
