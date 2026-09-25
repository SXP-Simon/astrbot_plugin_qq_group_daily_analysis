"""
插件宿主行为协议与抽象仓储 (Plugin Host Protocol)

明确约束 AstrBot 插件主类 (Star) 所暴露的服务组件契约，
彻底替代反射和动态 getattr 脆弱调用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from astrbot.api.star import Context

    from ...application.handlers.analysis_command_handler import (
        AnalysisCommandHandler,
    )
    from ...application.handlers.comic_command_handler import ComicCommandHandler
    from ...application.handlers.settings_command_handler import (
        SettingsCommandHandler,
    )
    from ...application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...application.services.comic_application_service import (
        ComicApplicationService,
    )
    from ...application.services.template_command_service import (
        TemplateCommandService,
    )
    from ...domain.services.incremental_merge_service import (
        IncrementalMergeService,
    )
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.checkpoint_store import CheckpointStore
    from ...infrastructure.persistence.history_manager import HistoryManager
    from ...infrastructure.persistence.incremental_store import IncrementalStore
    from ...infrastructure.persistence.platform_group_registry import (
        PlatformGroupRegistry,
    )
    from ...infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from ...infrastructure.platform.bot_manager import BotManager
    from ...infrastructure.platform.template_preview import TemplatePreviewRouter
    from ...infrastructure.reporting.generators import ReportGenerator
    from ...infrastructure.scheduler.auto_scheduler import AutoScheduler
    from ...infrastructure.webui.active_task_manager import ActiveTaskManager


@runtime_checkable
class PluginHostProtocol(Protocol):
    """插件主宿主实例协议契约。
    使用属性 getter 声明只读协变接口，避免具体类因可变类型不变量 (invariance) 导致的子类型检查失败。
    """

    @property
    def context(self) -> Context: ...

    @property
    def config_manager(self) -> ConfigManager: ...

    @property
    def bot_manager(self) -> BotManager: ...

    @property
    def analysis_service(self) -> AnalysisApplicationService: ...

    @property
    def report_generator(self) -> ReportGenerator: ...

    @property
    def auto_scheduler(self) -> AutoScheduler: ...

    @property
    def template_command_service(self) -> TemplateCommandService: ...

    @property
    def template_preview_router(self) -> TemplatePreviewRouter: ...

    @property
    def plugin_data_dir(self) -> Path: ...

    @property
    def history_manager(self) -> HistoryManager | None: ...

    @property
    def platform_group_registry(self) -> PlatformGroupRegistry | None: ...

    @property
    def checkpoint_store(self) -> CheckpointStore | None: ...

    @property
    def active_task_manager(self) -> ActiveTaskManager | None: ...

    @property
    def trace_store(self) -> TraceSQLiteStore | None: ...

    @property
    def incremental_store(self) -> IncrementalStore | None: ...

    @property
    def incremental_merge_service(self) -> IncrementalMergeService | None: ...

    @property
    def comic_service(self) -> ComicApplicationService | None: ...

    @property
    def settings_command_handler(self) -> SettingsCommandHandler: ...

    @property
    def comic_command_handler(self) -> ComicCommandHandler: ...

    @property
    def analysis_command_handler(self) -> AnalysisCommandHandler: ...

    async def get_seen_group_ids(
        self, platform_id: str | None = None
    ) -> list[str]: ...
