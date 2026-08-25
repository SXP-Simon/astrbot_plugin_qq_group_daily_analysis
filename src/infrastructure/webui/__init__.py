"""
WebUI 基础设施层 - 任务管理器与 Web API 桥接
"""

from .active_task_manager import ActiveTaskManager
from .plugin_page_bridge import PluginPageWebUIBridge

__all__ = ["ActiveTaskManager", "PluginPageWebUIBridge"]
