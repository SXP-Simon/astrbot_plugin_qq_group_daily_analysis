"""
报告生成模块
包含HTML、PDF、文本报告生成功能
"""

from .generators import ReportGenerator
from .templates import HTMLTemplates

__all__ = ["ReportGenerator", "HTMLTemplates"]
