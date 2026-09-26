"""Backward compatibility re-export for MarkdownReportGenerator."""

from .markdown_report_generator import (
    MENTION_STYLE_NAME,
    MENTION_STYLE_QQ,
    MarkdownReportGenerator,
    QQOfficialMarkdownReportGenerator,
)

__all__ = [
    "MENTION_STYLE_NAME",
    "MENTION_STYLE_QQ",
    "MarkdownReportGenerator",
    "QQOfficialMarkdownReportGenerator",
]
