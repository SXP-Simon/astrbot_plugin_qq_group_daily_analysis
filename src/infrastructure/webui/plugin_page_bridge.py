"""
AstrBot 插件 Pages 后端 Web API 桥接服务
为 React + Ant Design 5 控制台提供 REST 与 SSE 接口。
作为路由装配网桥，统一调度并挂载各领域路由子模块。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...shared.constants import PLUGIN_NAME
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from ..persistence.trace_sqlite_store import TraceSQLiteStore
from .active_task_manager import ActiveTaskManager
from .routes import (
    ConfigRoutes,
    DataManagementRoutes,
    LogRoutes,
    ReportRoutes,
    TaskRoutes,
    TemplateRoutes,
    TraceRoutes,
)
from .routes.config_routes import _config_key_to_folder, _sanitize_path_segment
from .web_compat import (
    Context,
    error_response,
    json_response,
    request,
    stream_response,
)

__all__ = [
    "Context",
    "PluginPageWebUIBridge",
    "_config_key_to_folder",
    "_sanitize_path_segment",
    "error_response",
    "json_response",
    "request",
    "stream_response",
]


class PluginPageWebUIBridge:
    """WebUI 面板 API 桥接适配器（聚合路由与装配中枢）。"""

    def __init__(
        self,
        context: Context,
        trace_store: TraceSQLiteStore,
        active_task_manager: ActiveTaskManager,
        analysis_service: Any,
        report_dispatcher: Any = None,
        report_output_dir: Path | None = None,
    ):
        self.context = context
        self.trace_store = trace_store
        self.active_task_manager = active_task_manager
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.report_output_dir = report_output_dir
        TraceContext.set_active_task_manager(self.active_task_manager)

        # 实例化各领域路由子模块
        self.task_routes = TaskRoutes(
            trace_store=self.trace_store,
            active_task_manager=self.active_task_manager,
            analysis_service=self.analysis_service,
            report_dispatcher=self.report_dispatcher,
        )
        self.trace_routes = TraceRoutes(
            context=self.context,
            trace_store=self.trace_store,
            active_task_manager=self.active_task_manager,
            analysis_service=self.analysis_service,
        )
        self.report_routes = ReportRoutes(
            trace_store=self.trace_store,
            analysis_service=self.analysis_service,
            report_dispatcher=self.report_dispatcher,
            report_output_dir=self.report_output_dir,
        )
        self.template_routes = TemplateRoutes(
            analysis_service=self.analysis_service,
            report_dispatcher=self.report_dispatcher,
        )
        self.log_routes = LogRoutes(
            active_task_manager=self.active_task_manager,
        )
        self.config_routes = ConfigRoutes(
            analysis_service=self.analysis_service,
            report_dispatcher=self.report_dispatcher,
        )
        self.data_management_routes = DataManagementRoutes(
            trace_store=self.trace_store,
            analysis_service=self.analysis_service,
            report_output_dir=self.report_output_dir,
        )

    def register_routes(self) -> None:
        """向 AstrBot 注册所有 Web API 端点"""
        routes = [
            # 1. 活跃任务与控制
            (
                f"/{PLUGIN_NAME}/tasks/active",
                self.task_routes.api_get_active_tasks,
                ["GET"],
                "Get active running analysis tasks",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/cancel",
                self.task_routes.api_cancel_task,
                ["POST"],
                "Cancel an active analysis task",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/trigger",
                self.task_routes.api_trigger_task,
                ["POST"],
                "Trigger an analysis task manually",
            ),
            (
                f"/{PLUGIN_NAME}/tasks/<trace_id>/resume",
                self.task_routes.api_resume_task,
                ["POST"],
                "Resume an analysis task from checkpoint",
            ),
            # 2. 链路追溯与指标
            (
                f"/{PLUGIN_NAME}/traces",
                self.trace_routes.api_list_traces,
                ["GET"],
                "List execution traces with filters",
            ),
            (
                f"/{PLUGIN_NAME}/traces/<trace_id>",
                self.trace_routes.api_get_trace_detail,
                ["GET"],
                "Get full trace details with spans and metrics",
            ),
            (
                f"/{PLUGIN_NAME}/metrics/summary",
                self.trace_routes.api_get_metrics_summary,
                ["GET"],
                "Get KPI and token metrics summary",
            ),
            (
                f"/{PLUGIN_NAME}/metrics/trends",
                self.trace_routes.api_get_analytics_trends,
                ["GET"],
                "Get time-series trends with hour/day granularity and provider breakdowns",
            ),
            (
                f"/{PLUGIN_NAME}/groups",
                self.trace_routes.api_get_distinct_groups,
                ["GET"],
                "Get distinct groups list for filtering",
            ),
            (
                f"/{PLUGIN_NAME}/platforms",
                self.trace_routes.api_get_platforms,
                ["GET"],
                "Get active connected bot platforms list",
            ),
            (
                f"/{PLUGIN_NAME}/providers",
                self.trace_routes.api_get_providers,
                ["GET"],
                "Get available LLM providers list",
            ),
            (
                f"/{PLUGIN_NAME}/personas",
                self.trace_routes.api_get_personas,
                ["GET"],
                "Get available AstrBot personas list",
            ),
            # 3. 历史产物与模板
            (
                f"/{PLUGIN_NAME}/reports/history",
                self.report_routes.api_get_report_history,
                ["GET"],
                "Get generated report image list",
            ),
            (
                f"/{PLUGIN_NAME}/reports/content",
                self.report_routes.api_get_report_content,
                ["GET"],
                "Get generated report image base64 content",
            ),
            (
                f"/{PLUGIN_NAME}/reports/rerender",
                self.report_routes.api_rerender_report,
                ["POST"],
                "Re-render report with a new theme template using cached checkpoint without LLM tokens",
            ),
            (
                f"/{PLUGIN_NAME}/reports/templates",
                self.template_routes.api_get_report_templates,
                ["GET"],
                "Get available built-in and custom report visual templates",
            ),
            (
                f"/{PLUGIN_NAME}/templates/preview",
                self.template_routes.api_get_template_preview,
                ["GET"],
                "Get preview image of a custom report template as base64 data URL",
            ),
            (
                f"/{PLUGIN_NAME}/templates/install_from_url",
                self.template_routes.api_install_template_from_url,
                ["POST"],
                "Install a custom report template from a GitHub repository URL",
            ),
            (
                f"/{PLUGIN_NAME}/templates/install_from_file",
                self.template_routes.api_install_template_from_file,
                ["POST"],
                "Install a custom report template from an uploaded zip archive",
            ),
            (
                f"/{PLUGIN_NAME}/templates/uninstall",
                self.template_routes.api_uninstall_template,
                ["POST"],
                "Uninstall a custom report template installed via the installer",
            ),
            # 4. SSE 实时事件流与日志
            (
                f"/{PLUGIN_NAME}/events/stream",
                self.log_routes.api_stream_events,
                ["GET"],
                "SSE stream for real-time task progress events",
            ),
            (
                f"/{PLUGIN_NAME}/logs",
                self.log_routes.api_get_plugin_logs,
                ["GET"],
                "Get plugin live logs with filters",
            ),
            (
                f"/{PLUGIN_NAME}/traces/<trace_id>/logs",
                self.log_routes.api_get_trace_logs,
                ["GET"],
                "Get execution logs for a specific trace",
            ),
            (
                f"/{PLUGIN_NAME}/logs/clear",
                self.log_routes.api_clear_plugin_logs,
                ["POST"],
                "Clear in-memory plugin log buffer",
            ),
            # 5. 插件配置中心
            (
                f"/{PLUGIN_NAME}/config",
                self.config_routes.api_get_config,
                ["GET"],
                "Get current plugin configuration and schema definition",
            ),
            (
                f"/{PLUGIN_NAME}/config",
                self.config_routes.api_save_config,
                ["POST"],
                "Save and persist updated plugin configuration",
            ),
            (
                f"/{PLUGIN_NAME}/config/upload_file",
                self.config_routes.api_upload_config_file,
                ["POST"],
                "Upload a config reference image/file and store to files/ folder",
            ),
            (
                f"/{PLUGIN_NAME}/config/file/content",
                self.config_routes.api_get_config_file_content,
                ["GET"],
                "Get thumbnail or content of a config file path",
            ),
            # 6. 插件数据管理（存储分区清理）
            (
                f"/{PLUGIN_NAME}/plugin-data/overview",
                self.data_management_routes.api_get_plugin_data_overview,
                ["GET"],
                "Get size and file count overview for each plugin data section",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/avatars/clear",
                self.data_management_routes.api_clear_avatar_cache,
                ["POST"],
                "Clear avatar image cache",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/reports/clear",
                self.data_management_routes.api_clear_reports,
                ["POST"],
                "Clear all generated report files",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/temp/clear",
                self.data_management_routes.api_clear_temp_files,
                ["POST"],
                "Clear temporary generated files",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/custom-templates/clear",
                self.data_management_routes.api_clear_custom_templates,
                ["POST"],
                "Clear user-customized T2I template backups",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/config-files/clear",
                self.data_management_routes.api_clear_config_files,
                ["POST"],
                "Clear uploaded config reference files",
            ),
            (
                f"/{PLUGIN_NAME}/plugin-data/config-backups/clear",
                self.data_management_routes.api_clear_config_backups,
                ["POST"],
                "Clear historical automatic configuration backup files",
            ),
            # 7. 增量批次与 Checkpoint 观测及 CRUD 管理
            (
                f"/{PLUGIN_NAME}/data/incremental/groups",
                self.data_management_routes.api_get_incremental_groups,
                ["GET"],
                "Get groups list with incremental batches or cursors",
            ),
            (
                f"/{PLUGIN_NAME}/data/incremental/batches",
                self.data_management_routes.api_get_incremental_batches,
                ["GET"],
                "Get incremental batches list and cursor status for a group",
            ),
            (
                f"/{PLUGIN_NAME}/data/incremental/batch/detail",
                self.data_management_routes.api_get_incremental_batch_detail,
                ["GET"],
                "Get full detail of a single incremental batch",
            ),
            (
                f"/{PLUGIN_NAME}/data/incremental/batch",
                self.data_management_routes.api_delete_incremental_batch,
                ["DELETE", "POST"],
                "Delete a specific incremental batch",
            ),
            (
                f"/{PLUGIN_NAME}/data/incremental/reset",
                self.data_management_routes.api_reset_incremental_group,
                ["POST"],
                "Reset all incremental batches and cursor for a group",
            ),
            (
                f"/{PLUGIN_NAME}/data/checkpoints",
                self.data_management_routes.api_list_checkpoints,
                ["GET"],
                "List and filter stage checkpoints",
            ),
            (
                f"/{PLUGIN_NAME}/data/checkpoints/groups",
                self.data_management_routes.api_get_checkpoint_groups,
                ["GET"],
                "Get distinct groups list with valid checkpoints",
            ),
            (
                f"/{PLUGIN_NAME}/data/checkpoint/detail",
                self.data_management_routes.api_get_checkpoint_detail,
                ["GET"],
                "Get full JSON content and metadata of a specific checkpoint",
            ),
            (
                f"/{PLUGIN_NAME}/data/checkpoint",
                self.data_management_routes.api_delete_checkpoint,
                ["DELETE", "POST"],
                "Delete a specific stage checkpoint or all checkpoints for group and date",
            ),
        ]

        for path, handler, methods, desc in routes:
            try:
                self.context.register_web_api(path, handler, methods, desc)  # type: ignore
            except Exception as e:
                logger.error(f"注册 Web API 路由 {path} 失败: {e}")

        # 挂载日志流至 SSE 广播通道
        try:
            from ..logging.plugin_log_buffer import global_log_buffer

            global_log_buffer.register_listener(
                lambda record: self.active_task_manager.publish_log_sync(
                    trace_id=record.get("trace_id", ""),
                    stage=record.get("stage", ""),
                    message=record.get("message", ""),
                    level=record.get("level", "INFO"),
                )
            )
        except Exception as e:
            logger.warning(f"挂载日志推送监听器失败: {e}")

    # ================================================================
    # 兼容性直接代理转发 (Backward Compatibility Forwarders)
    # ================================================================

    async def api_get_active_tasks(self) -> Any:
        return await self.task_routes.api_get_active_tasks()

    async def api_cancel_task(self) -> Any:
        return await self.task_routes.api_cancel_task()

    async def api_trigger_task(self) -> Any:
        return await self.task_routes.api_trigger_task()

    async def api_resume_task(self, trace_id: str) -> Any:
        return await self.task_routes.api_resume_task(trace_id)

    async def api_list_traces(self) -> Any:
        return await self.trace_routes.api_list_traces()

    async def api_get_distinct_groups(self) -> Any:
        return await self.trace_routes.api_get_distinct_groups()

    async def api_get_platforms(self) -> Any:
        return await self.trace_routes.api_get_platforms()

    async def api_get_providers(self) -> Any:
        return await self.trace_routes.api_get_providers()

    async def api_get_personas(self) -> Any:
        return await self.trace_routes.api_get_personas()

    async def api_get_trace_detail(self, trace_id: str) -> Any:
        return await self.trace_routes.api_get_trace_detail(trace_id)

    async def api_get_metrics_summary(self) -> Any:
        return await self.trace_routes.api_get_metrics_summary()

    async def api_get_analytics_trends(self) -> Any:
        return await self.trace_routes.api_get_analytics_trends()

    async def api_get_report_history(self) -> Any:
        return await self.report_routes.api_get_report_history()

    async def api_get_report_content(self) -> Any:
        return await self.report_routes.api_get_report_content()

    async def api_rerender_report(self) -> Any:
        return await self.report_routes.api_rerender_report()

    async def api_get_report_templates(self) -> Any:
        return await self.template_routes.api_get_report_templates()

    async def api_get_template_preview(self) -> Any:
        return await self.template_routes.api_get_template_preview()

    async def api_install_template_from_url(self) -> Any:
        return await self.template_routes.api_install_template_from_url()

    async def api_install_template_from_file(self) -> Any:
        return await self.template_routes.api_install_template_from_file()

    async def api_uninstall_template(self) -> Any:
        return await self.template_routes.api_uninstall_template()

    async def api_stream_events(self) -> Any:
        return await self.log_routes.api_stream_events()

    async def api_get_plugin_logs(self) -> Any:
        return await self.log_routes.api_get_plugin_logs()

    async def api_get_trace_logs(self, trace_id: str) -> Any:
        return await self.log_routes.api_get_trace_logs(trace_id)

    async def api_clear_plugin_logs(self) -> Any:
        return await self.log_routes.api_clear_plugin_logs()

    async def api_get_config(self) -> Any:
        return await self.config_routes.api_get_config()

    async def api_save_config(self) -> Any:
        return await self.config_routes.api_save_config()

    async def api_upload_config_file(self) -> Any:
        return await self.config_routes.api_upload_config_file()

    async def api_get_config_file_content(self) -> Any:
        return await self.config_routes.api_get_config_file_content()

    async def api_get_plugin_data_overview(self) -> Any:
        return await self.data_management_routes.api_get_plugin_data_overview()

    async def api_clear_avatar_cache(self) -> Any:
        return await self.data_management_routes.api_clear_avatar_cache()

    async def api_clear_reports(self) -> Any:
        return await self.data_management_routes.api_clear_reports()

    async def api_clear_temp_files(self) -> Any:
        return await self.data_management_routes.api_clear_temp_files()

    async def api_clear_custom_templates(self) -> Any:
        return await self.data_management_routes.api_clear_custom_templates()

    async def api_clear_config_files(self) -> Any:
        return await self.data_management_routes.api_clear_config_files()

    async def api_clear_config_backups(self) -> Any:
        return await self.data_management_routes.api_clear_config_backups()

    async def api_get_incremental_groups(self) -> Any:
        return await self.data_management_routes.api_get_incremental_groups()

    async def api_get_incremental_batches(self) -> Any:
        return await self.data_management_routes.api_get_incremental_batches()

    async def api_get_incremental_batch_detail(self) -> Any:
        return await self.data_management_routes.api_get_incremental_batch_detail()

    async def api_delete_incremental_batch(self) -> Any:
        return await self.data_management_routes.api_delete_incremental_batch()

    async def api_reset_incremental_group(self) -> Any:
        return await self.data_management_routes.api_reset_incremental_group()

    async def api_list_checkpoints(self) -> Any:
        return await self.data_management_routes.api_list_checkpoints()

    async def api_get_checkpoint_groups(self) -> Any:
        return await self.data_management_routes.api_get_checkpoint_groups()

    async def api_get_checkpoint_detail(self) -> Any:
        return await self.data_management_routes.api_get_checkpoint_detail()

    async def api_delete_checkpoint(self) -> Any:
        return await self.data_management_routes.api_delete_checkpoint()
