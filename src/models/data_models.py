"""
数据模型定义
包含所有分析相关的数据结构
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SummaryTopic:
    """话题总结数据结构"""
    topic: str
    contributors: List[str]
    detail: str


@dataclass
class UserTitle:
    """用户称号数据结构"""
    name: str
    qq: int
    title: str
    mbti: str
    reason: str


@dataclass
class GoldenQuote:
    """群聊金句数据结构"""
    content: str
    sender: str
    reason: str


@dataclass
class TokenUsage:
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class GroupStatistics:
    """群聊统计数据结构"""
    message_count: int
    total_characters: int
    participant_count: int
    most_active_period: str
    golden_quotes: List[GoldenQuote]
    emoji_count: int
    token_usage: TokenUsage = field(default_factory=TokenUsage)