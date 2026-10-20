"""词云配置、完整词频与渲染数据契约。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class WordCloudOptions:
    """与模板无关的词云设置。"""

    enabled: bool = True
    send_with_report: bool = True
    template: str = "ATRI"
    font: str = "wenkai"
    min_font_size: int = 34
    max_font_size: int = 90
    max_words: int = 80
    word_spacing: int = 10
    width: int = 1200
    height: int = 900
    rotation: str = "horizontal"
    palette: tuple[str, ...] = ()
    weight_mode: str = "message_count"
    stopwords: tuple[str, ...] = ()
    keep_words: tuple[str, ...] = ()
    min_word_length: int = 2
    min_frequency: int = 2

    def to_dict(self) -> dict[str, object]:
        """返回可传输的配置字典。"""
        result = asdict(self)
        for name in ("palette", "stopwords", "keep_words"):
            result[name] = list(result[name])
        return result

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> WordCloudOptions:
        """验证合并后的设置，拒绝无效预览和配置输入。

        Args:
            data: 由模板、全局与群配置合并得到的设置。

        Returns:
            验证后的不可变配置。

        Raises:
            ValueError: 字段类型、取值范围或字体标识无效。
        """
        values = cls().to_dict()
        values.update({key: value for key, value in data.items() if key in values})
        for name in ("enabled", "send_with_report"):
            if not isinstance(values[name], bool):
                raise ValueError(f"词云 {name} 必须是布尔值")
        ranges = {
            "min_font_size": (12, 160),
            "max_font_size": (12, 160),
            "max_words": (1, 200),
            "word_spacing": (0, 40),
            "width": (800, 2400),
            "height": (600, 1800),
            "min_word_length": (1, 20),
            "min_frequency": (1, 10000),
        }
        integers: dict[str, int] = {}
        for name, (low, high) in ranges.items():
            value = values[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not low <= value <= high
            ):
                raise ValueError(f"词云 {name} 必须是 {low}～{high} 的整数")
            integers[name] = value
        if integers["min_font_size"] > integers["max_font_size"]:
            raise ValueError("词云最小字号不能大于最大字号")
        strings: dict[str, str] = {}
        for name in ("template", "font", "rotation", "weight_mode"):
            value = values[name]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"词云 {name} 必须是非空字符串")
            strings[name] = value.strip()
        if not re.fullmatch(r"[\w-]+", strings["template"]):
            raise ValueError("词云模板名称无效")
        if strings["font"] not in {"wenkai", "sans", "serif"} and not re.fullmatch(
            r"uploaded:[a-f0-9]{64}\.(?:woff2?|ttf|otf)", strings["font"]
        ):
            raise ValueError("词云字体必须是内置字体或已上传的字体")
        if strings["rotation"] not in {"horizontal", "mixed"}:
            raise ValueError("词云方向必须是 horizontal 或 mixed")
        if strings["weight_mode"] not in {"message_count", "occurrence_count"}:
            raise ValueError("词云权重必须是 message_count 或 occurrence_count")
        sequences: dict[str, tuple[str, ...]] = {}
        for name in ("palette", "stopwords", "keep_words"):
            sequence = values[name]
            if not isinstance(sequence, (list, tuple)) or not all(
                isinstance(item, str) for item in sequence
            ):
                raise ValueError(f"词云 {name} 必须是字符串列表")
            sequences[name] = tuple(
                dict.fromkeys(
                    item.strip()
                    for item in sequence
                    if isinstance(item, str) and item.strip()
                )
            )
            if len(sequences[name]) > (16 if name == "palette" else 2000):
                raise ValueError(f"词云 {name} 的条目过多")
        if any(
            not re.fullmatch(r"#[a-fA-F0-9]{3}(?:[a-fA-F0-9]{3})?", color)
            for color in sequences["palette"]
        ):
            raise ValueError("词云配色必须使用 #RGB 或 #RRGGBB 格式")
        return cls(
            enabled=bool(values["enabled"]),
            send_with_report=bool(values["send_with_report"]),
            template=strings["template"],
            font=strings["font"],
            min_font_size=integers["min_font_size"],
            max_font_size=integers["max_font_size"],
            max_words=integers["max_words"],
            word_spacing=integers["word_spacing"],
            width=integers["width"],
            height=integers["height"],
            rotation=strings["rotation"],
            palette=sequences["palette"],
            weight_mode=strings["weight_mode"],
            stopwords=sequences["stopwords"],
            keep_words=sequences["keep_words"],
            min_word_length=integers["min_word_length"],
            min_frequency=integers["min_frequency"],
        )


@dataclass(frozen=True)
class WordFrequency:
    """一个词的总出现次数和包含它的消息数。"""

    text: str
    occurrence_count: int = 0
    message_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """返回可持久化的词频。"""
        return asdict(self)


@dataclass(frozen=True)
class WordCloudData:
    """不受外观和 Top N 影响的完整统计快照。"""

    frequencies: tuple[WordFrequency, ...] = ()
    message_count: int = 0
    group_id: str = ""
    platform_id: str = ""
    date_str: str = ""
    start_timestamp: int = 0
    end_timestamp: int = 0

    def to_dict(self) -> dict[str, object]:
        """返回可持久化的统计快照。"""
        return {
            "frequencies": [entry.to_dict() for entry in self.frequencies],
            "message_count": self.message_count,
            "group_id": self.group_id,
            "platform_id": self.platform_id,
            "date_str": self.date_str,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> WordCloudData:
        """从持久化快照恢复完整词频，兼容缺少新字段的旧数据。

        Args:
            data: JSON 词频快照。

        Returns:
            恢复的统计快照。
        """
        entries: list[WordFrequency] = []
        raw_entries = data.get("frequencies", [])
        if isinstance(raw_entries, (list, tuple)):
            for raw in raw_entries:
                if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
                    continue
                occurrence = raw.get("occurrence_count", 0)
                messages = raw.get("message_count", 0)
                if isinstance(occurrence, int) and isinstance(messages, int):
                    entries.append(
                        WordFrequency(raw["text"], max(0, occurrence), max(0, messages))
                    )
        integers = {
            name: value if isinstance(value := data.get(name), int) else 0
            for name in ("message_count", "start_timestamp", "end_timestamp")
        }
        return cls(
            frequencies=tuple(entries),
            message_count=integers["message_count"],
            group_id=str(data.get("group_id", "")),
            platform_id=str(data.get("platform_id", "")),
            date_str=str(data.get("date_str", "")),
            start_timestamp=integers["start_timestamp"],
            end_timestamp=integers["end_timestamp"],
        )

    def top_words(self, options: WordCloudOptions) -> tuple[WordFrequency, ...]:
        """在完整词频上应用显示门槛和数量上限。

        Args:
            options: 当前渲染配置。

        Returns:
            按所选权重降序排列的词语。
        """

        def weight(entry: WordFrequency) -> int:
            return (
                entry.occurrence_count
                if options.weight_mode == "occurrence_count"
                else entry.message_count
            )

        stopwords = {word.casefold() for word in options.stopwords}
        keep_words = {word.casefold() for word in options.keep_words}
        words = [
            entry
            for entry in self.frequencies
            if weight(entry) >= options.min_frequency
            and (
                entry.text.casefold() in keep_words
                or (
                    entry.text.casefold() not in stopwords
                    and len(entry.text) >= options.min_word_length
                )
            )
        ]
        return tuple(
            sorted(
                words,
                key=lambda entry: (-weight(entry), -entry.occurrence_count, entry.text),
            )[: options.max_words]
        )
