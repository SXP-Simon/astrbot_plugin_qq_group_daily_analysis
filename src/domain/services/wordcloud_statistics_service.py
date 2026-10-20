"""词云统计领域服务：消息去重、纯文本过滤与全量词频累加。"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING, Protocol

from ..value_objects.unified_message import MessageContentType, UnifiedMessage
from ..value_objects.wordcloud import WordCloudData, WordCloudOptions, WordFrequency

if TYPE_CHECKING:
    from collections.abc import Iterable

_NOISE = re.compile(
    r"\[CQ:[^\]]*\]|https?://\S+|www\.\S+|<@!?\d+>|<a?:[^:>]+:\d+>"
    r"|\[(?:图片|表情|语音|视频|文件|回复|转发|image|emoji|at)(?::[^\]]*)?\]",
    re.IGNORECASE,
)
_STOPWORDS = frozenset(
    [
        "的",
        "了",
        "是",
        "在",
        "和",
        "与",
        "也",
        "就",
        "都",
        "而",
        "及",
        "着",
        "啊",
        "呢",
        "吧",
        "哦",
        "嗯",
        "这个",
        "那个",
        "一个",
        "一些",
        "一下",
        "我们",
        "你们",
        "他们",
        "她们",
        "自己",
        "什么",
        "怎么",
        "为什么",
        "可以",
        "不是",
        "没有",
        "还是",
        "但是",
        "然后",
        "因为",
        "所以",
        "如果",
        "已经",
        "现在",
        "这样",
        "那样",
        "时候",
        "觉得",
        "真的",
        "还有",
        "这里",
        "那里",
        "我们的",
        "你们的",
        "他们的",
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "is",
        "are",
        "was",
        "were",
        "it",
        "this",
        "that",
        "with",
        "for",
        "you",
        "i",
        "we",
        "they",
    ]
)


class WordTokenizer(Protocol):
    """本地分词器的纯领域接口。"""

    def tokenize(self, text: str, keep_words: tuple[str, ...]) -> Iterable[str]:
        """分词并保留配置的完整自定义词。"""
        ...


class WordCloudStatisticsService:
    """统计所有有效词语，显示数量和频率门槛留给渲染阶段处理。"""

    def __init__(self, tokenizer: WordTokenizer) -> None:
        self.tokenizer = tokenizer

    def collect(
        self,
        messages: list[UnifiedMessage],
        options: WordCloudOptions,
        group_id: str = "",
        platform_id: str = "",
        date_str: str = "",
    ) -> WordCloudData:
        """按消息去重并同时记录出现次数与包含该词的消息数。

        Args:
            messages: 与群分析共享的已清洗消息。
            options: 本次统计设置。
            group_id: 群组标识。
            platform_id: 平台实例标识。
            date_str: 展示日期范围。

        Returns:
            保留所有词频的统计快照，不提前截断 Top N。
        """
        occurrences: Counter[str] = Counter()
        message_counts: Counter[str] = Counter()
        keep_words = tuple(
            unicodedata.normalize("NFKC", word).casefold()
            for word in options.keep_words
        )
        seen: set[tuple[str, str, str]] = set()
        timestamps: list[int] = []
        for message in messages:
            identity = (
                message.message_id
                or f"{message.timestamp}:{message.sender_id}:{message.text_content}"
            )
            key = (message.platform, message.group_id, identity)
            if key in seen:
                continue
            seen.add(key)
            timestamps.append(message.timestamp)
            # 结构化消息只提取正文，图片描述、@ 与转发占位符不进入统计。
            text = " ".join(
                content.text
                for content in message.contents
                if content.type == MessageContentType.TEXT
            )
            if not message.contents:
                text = message.text_content
            text = unicodedata.normalize("NFKC", _NOISE.sub(" ", text)).casefold()
            words = [
                word.strip()
                for word in self.tokenizer.tokenize(text, keep_words)
                if word.strip()
                and any(character.isalpha() for character in word)
                and (word in keep_words or word not in _STOPWORDS)
            ]
            occurrences.update(words)
            message_counts.update(set(words))
        return WordCloudData(
            frequencies=tuple(
                WordFrequency(word, count, message_counts[word])
                for word, count in sorted(occurrences.items())
            ),
            message_count=len(seen),
            group_id=group_id,
            platform_id=platform_id,
            date_str=date_str,
            start_timestamp=min(timestamps, default=0),
            end_timestamp=max(timestamps, default=0),
        )

    @staticmethod
    def merge(data: Iterable[WordCloudData]) -> WordCloudData:
        """合并互不重叠的增量批次，在合并完成后再由渲染器选词。

        Args:
            data: 已通过批次标识去重的统计快照。

        Returns:
            全量合并的词频快照。
        """
        snapshots = list(data)
        if not snapshots:
            return WordCloudData()
        occurrences: Counter[str] = Counter()
        messages: Counter[str] = Counter()
        for snapshot in snapshots:
            for entry in snapshot.frequencies:
                occurrences[entry.text] += entry.occurrence_count
                messages[entry.text] += entry.message_count
        starts = [item.start_timestamp for item in snapshots if item.start_timestamp]
        return WordCloudData(
            frequencies=tuple(
                WordFrequency(word, count, messages[word])
                for word, count in sorted(occurrences.items())
            ),
            message_count=sum(item.message_count for item in snapshots),
            group_id=snapshots[0].group_id,
            platform_id=snapshots[0].platform_id,
            date_str=snapshots[-1].date_str,
            start_timestamp=min(starts, default=0),
            end_timestamp=max(item.end_timestamp for item in snapshots),
        )
