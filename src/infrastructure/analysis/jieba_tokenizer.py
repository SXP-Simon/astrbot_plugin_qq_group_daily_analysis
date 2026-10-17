"""使用独立词典实例的本地中文分词适配器。"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jieba import Tokenizer


@lru_cache(maxsize=8)
def _dictionary(keep_words: tuple[str, ...]) -> Tokenizer:
    """缓存有限数量的词典，避免群级自定义词污染其他群。

    Args:
        keep_words: 当前群配置的完整自定义词。

    Returns:
        已初始化且只读使用的分词器。
    """
    from jieba import Tokenizer

    tokenizer = Tokenizer()
    tokenizer.initialize()
    for word in keep_words:
        tokenizer.add_word(word, freq=10000000)
    return tokenizer


class JiebaWordTokenizer:
    """提供可在线程中运行的 Jieba 精确分词。"""

    def tokenize(self, text: str, keep_words: tuple[str, ...]) -> tuple[str, ...]:
        """用当前词典对正文分词。

        Args:
            text: 已规范化的纯文本。
            keep_words: 应保持完整的自定义词。

        Returns:
            精确模式分词结果。
        """
        return tuple(_dictionary(keep_words).cut(text, HMM=True))
