"""
WebUI 路由子模块导出 (WebUI Routes Package)
"""

from .config_routes import ConfigRoutes
from .data_management_routes import DataManagementRoutes
from .log_routes import LogRoutes
from .report_routes import ReportRoutes
from .task_routes import TaskRoutes
from .template_routes import TemplateRoutes
from .trace_routes import TraceRoutes

__all__ = [
    "ConfigRoutes",
    "DataManagementRoutes",
    "LogRoutes",
    "ReportRoutes",
    "TaskRoutes",
    "TemplateRoutes",
    "TraceRoutes",
]
