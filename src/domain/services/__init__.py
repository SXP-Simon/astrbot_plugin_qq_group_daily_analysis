"""
领域服务 - 分析业务逻辑服务

该模块导出所有封装核心业务逻辑的领域服务，
用于分析群聊数据。这些服务是平台无关的。
"""

from .incremental_merge_service import IncrementalMergeService

__all__ = [
    "IncrementalMergeService",
]
