"""
增量分析状态实体

存储单个群聊在一天内累积的增量分析数据。
每次增量分析产生一个批次(batch)，批次结果合并到此状态中。
最终报告时从此状态中提取完整的统计数据和分析内容。
"""

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BatchRecord:
    """单次增量分析批次记录"""

    batch_id: int = 0
    timestamp: float = 0.0
    message_count: int = 0
    new_topics_count: int = 0
    new_quotes_count: int = 0
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "message_count": self.message_count,
            "new_topics_count": self.new_topics_count,
            "new_quotes_count": self.new_quotes_count,
            "token_usage": self.token_usage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BatchRecord":
        """从字典反序列化"""
        return cls(
            batch_id=data.get("batch_id", 0),
            timestamp=data.get("timestamp", 0.0),
            message_count=data.get("message_count", 0),
            new_topics_count=data.get("new_topics_count", 0),
            new_quotes_count=data.get("new_quotes_count", 0),
            token_usage=data.get("token_usage", {}),
        )


@dataclass
class IncrementalState:
    """
    增量分析状态聚合实体

    该实体代表一个群聊在一天内的增量分析累积状态。
    随着当天多次增量分析的执行，话题、金句、统计数据会不断合并更新。

    Attributes:
        group_id: 群组 ID
        date_str: 日期字符串 (YYYY-MM-DD)
        topics: 累积的话题列表（每个元素为 dict，包含 topic/contributors/detail）
        golden_quotes: 累积的金句列表（每个元素为 dict，包含 content/sender/reason）
        hourly_message_counts: 每小时消息计数 {hour_int: count}
        hourly_character_counts: 每小时字符计数 {hour_int: count}
        user_activities: 用户活跃数据 {user_id: {name, message_count, char_count, ...}}
        emoji_counts: 表情统计 {emoji_type: count}
        batch_records: 已完成的增量分析批次记录
        total_message_count: 当天总消息数
        total_character_count: 当天总字符数
        total_analysis_count: 当天已执行的增量分析次数
        total_token_usage: 累计 token 消耗
        last_analyzed_message_timestamp: 上次分析的最后一条消息时间戳（用于去重）
        all_participant_ids: 所有参与者 ID 集合
        created_at: 状态创建时间
        updated_at: 状态最后更新时间
    """

    # 标识信息
    group_id: str = ""
    date_str: str = ""

    # 累积的 LLM 分析结果
    topics: list[dict] = field(default_factory=list)
    golden_quotes: list[dict] = field(default_factory=list)

    # 累积的统计数据（按小时）
    hourly_message_counts: dict[str, int] = field(default_factory=dict)
    hourly_character_counts: dict[str, int] = field(default_factory=dict)

    # 用户活跃数据
    user_activities: dict[str, dict] = field(default_factory=dict)

    # 表情统计
    emoji_counts: dict[str, int] = field(default_factory=dict)

    # 批次记录
    batch_records: list[BatchRecord] = field(default_factory=list)

    # 汇总统计
    total_message_count: int = 0
    total_character_count: int = 0
    total_analysis_count: int = 0
    total_token_usage: dict = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })

    # 增量跟踪
    last_analyzed_message_timestamp: int = 0
    all_participant_ids: set[str] = field(default_factory=set)

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def merge_batch(
        self,
        messages_count: int,
        characters_count: int,
        hourly_msg_counts: dict[int, int],
        hourly_char_counts: dict[int, int],
        user_stats: dict[str, dict],
        emoji_stats: dict[str, int],
        new_topics: list[dict],
        new_quotes: list[dict],
        token_usage: dict,
        last_message_timestamp: int,
        participant_ids: set[str],
    ) -> "BatchRecord":
        """
        合并一次增量分析的结果到当前状态中。

        Args:
            messages_count: 本批次分析的消息数量
            characters_count: 本批次的总字符数
            hourly_msg_counts: 本批次按小时的消息计数 {hour: count}
            hourly_char_counts: 本批次按小时的字符计数 {hour: count}
            user_stats: 本批次用户统计 {user_id: {name, message_count, char_count, ...}}
            emoji_stats: 本批次表情统计 {emoji_type: count}
            new_topics: 本批次提取的新话题
            new_quotes: 本批次提取的新金句
            token_usage: 本批次 token 消耗 {prompt_tokens, completion_tokens, total_tokens}
            last_message_timestamp: 本批次最后一条消息的时间戳
            participant_ids: 本批次参与者 ID 集合

        Returns:
            BatchRecord: 本次批次的记录
        """
        # 更新统计汇总
        self.total_message_count += messages_count
        self.total_character_count += characters_count
        self.total_analysis_count += 1

        # 合并小时统计
        for hour, count in hourly_msg_counts.items():
            hour_key = str(hour)
            self.hourly_message_counts[hour_key] = (
                self.hourly_message_counts.get(hour_key, 0) + count
            )
        for hour, count in hourly_char_counts.items():
            hour_key = str(hour)
            self.hourly_character_counts[hour_key] = (
                self.hourly_character_counts.get(hour_key, 0) + count
            )

        # 合并用户活跃数据
        for user_id, stats in user_stats.items():
            if user_id in self.user_activities:
                existing = self.user_activities[user_id]
                existing["message_count"] = (
                    existing.get("message_count", 0) + stats.get("message_count", 0)
                )
                existing["char_count"] = (
                    existing.get("char_count", 0) + stats.get("char_count", 0)
                )
                existing["emoji_count"] = (
                    existing.get("emoji_count", 0) + stats.get("emoji_count", 0)
                )
                # 合并活跃小时集合
                existing_hours = set(existing.get("active_hours", []))
                new_hours = set(stats.get("active_hours", []))
                existing["active_hours"] = list(existing_hours | new_hours)
                # 更新最后发言时间
                if stats.get("last_message_time", 0) > existing.get("last_message_time", 0):
                    existing["last_message_time"] = stats["last_message_time"]
            else:
                self.user_activities[user_id] = dict(stats)

        # 合并表情统计
        for emoji_type, count in emoji_stats.items():
            self.emoji_counts[emoji_type] = (
                self.emoji_counts.get(emoji_type, 0) + count
            )

        # 合并话题（带去重）
        for new_topic in new_topics:
            if not self._is_duplicate_topic(new_topic):
                self.topics.append(new_topic)

        # 合并金句（带去重）
        for new_quote in new_quotes:
            if not self._is_duplicate_quote(new_quote):
                self.golden_quotes.append(new_quote)

        # 更新 token 消耗
        self.total_token_usage["prompt_tokens"] = (
            self.total_token_usage.get("prompt_tokens", 0)
            + token_usage.get("prompt_tokens", 0)
        )
        self.total_token_usage["completion_tokens"] = (
            self.total_token_usage.get("completion_tokens", 0)
            + token_usage.get("completion_tokens", 0)
        )
        self.total_token_usage["total_tokens"] = (
            self.total_token_usage.get("total_tokens", 0)
            + token_usage.get("total_tokens", 0)
        )

        # 更新增量追踪
        if last_message_timestamp > self.last_analyzed_message_timestamp:
            self.last_analyzed_message_timestamp = last_message_timestamp
        self.all_participant_ids.update(participant_ids)

        # 更新时间戳
        self.updated_at = time.time()

        # 创建批次记录
        batch = BatchRecord(
            batch_id=self.total_analysis_count,
            timestamp=time.time(),
            message_count=messages_count,
            new_topics_count=len(new_topics),
            new_quotes_count=len(new_quotes),
            token_usage=dict(token_usage),
        )
        self.batch_records.append(batch)

        return batch

    def _is_duplicate_topic(self, new_topic: dict, threshold: float = 0.6) -> bool:
        """
        检测话题是否与已有话题重复。

        使用简单的字符重叠相似度判断。
        当新话题的名称与已有话题名称相似度超过阈值时，认为是重复话题。

        Args:
            new_topic: 待检测的新话题
            threshold: 相似度阈值（0-1），默认 0.6

        Returns:
            bool: 是否重复
        """
        new_name = new_topic.get("topic", "")
        if not new_name:
            return False

        for existing in self.topics:
            existing_name = existing.get("topic", "")
            if not existing_name:
                continue
            similarity = self._char_overlap_similarity(new_name, existing_name)
            if similarity >= threshold:
                return True
        return False

    def _is_duplicate_quote(self, new_quote: dict, threshold: float = 0.7) -> bool:
        """
        检测金句是否与已有金句重复。

        Args:
            new_quote: 待检测的新金句
            threshold: 相似度阈值（0-1），默认 0.7

        Returns:
            bool: 是否重复
        """
        new_content = new_quote.get("content", "")
        if not new_content:
            return False

        for existing in self.golden_quotes:
            existing_content = existing.get("content", "")
            if not existing_content:
                continue
            similarity = self._char_overlap_similarity(new_content, existing_content)
            if similarity >= threshold:
                return True
        return False

    @staticmethod
    def _char_overlap_similarity(s1: str, s2: str) -> float:
        """
        计算两个字符串的字符重叠相似度。

        使用 Jaccard 相似系数：交集大小 / 并集大小。

        Args:
            s1: 第一个字符串
            s2: 第二个字符串

        Returns:
            float: 相似度值（0-1）
        """
        if not s1 or not s2:
            return 0.0
        set1 = set(s1)
        set2 = set(s2)
        intersection = set1 & set2
        union = set1 | set2
        if not union:
            return 0.0
        return len(intersection) / len(union)

    def get_peak_hours(self, top_n: int = 3) -> list[int]:
        """
        获取消息最活跃的时段。

        Args:
            top_n: 返回前 N 个最活跃的小时

        Returns:
            list[int]: 活跃小时列表，按消息量降序
        """
        if not self.hourly_message_counts:
            return []
        sorted_hours = sorted(
            self.hourly_message_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [int(h) for h, _ in sorted_hours[:top_n]]

    def get_most_active_period(self) -> str:
        """
        获取最活跃时段的描述字符串。

        Returns:
            str: 如 "20:00-21:00"
        """
        peak = self.get_peak_hours(1)
        if not peak:
            return "未知"
        hour = peak[0]
        return f"{hour:02d}:00-{hour + 1:02d}:00"

    def get_user_activity_ranking(self, top_n: int = 10) -> list[dict]:
        """
        获取用户活跃度排名。

        Args:
            top_n: 返回前 N 名

        Returns:
            list[dict]: 按消息数降序排列的用户列表
        """
        users = []
        for user_id, data in self.user_activities.items():
            users.append({
                "user_id": user_id,
                "name": data.get("name", user_id),
                "message_count": data.get("message_count", 0),
                "char_count": data.get("char_count", 0),
            })
        users.sort(key=lambda x: x["message_count"], reverse=True)
        return users[:top_n]

    def to_dict(self) -> dict:
        """
        序列化为字典，用于 KV 存储持久化。

        Returns:
            dict: 可 JSON 序列化的字典
        """
        return {
            "group_id": self.group_id,
            "date_str": self.date_str,
            "topics": self.topics,
            "golden_quotes": self.golden_quotes,
            "hourly_message_counts": self.hourly_message_counts,
            "hourly_character_counts": self.hourly_character_counts,
            "user_activities": self.user_activities,
            "emoji_counts": self.emoji_counts,
            "batch_records": [b.to_dict() for b in self.batch_records],
            "total_message_count": self.total_message_count,
            "total_character_count": self.total_character_count,
            "total_analysis_count": self.total_analysis_count,
            "total_token_usage": self.total_token_usage,
            "last_analyzed_message_timestamp": self.last_analyzed_message_timestamp,
            "all_participant_ids": list(self.all_participant_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IncrementalState":
        """
        从字典反序列化。

        Args:
            data: 从 KV 存储读取的字典数据

        Returns:
            IncrementalState: 重建的状态实例
        """
        state = cls(
            group_id=data.get("group_id", ""),
            date_str=data.get("date_str", ""),
            topics=data.get("topics", []),
            golden_quotes=data.get("golden_quotes", []),
            hourly_message_counts=data.get("hourly_message_counts", {}),
            hourly_character_counts=data.get("hourly_character_counts", {}),
            user_activities=data.get("user_activities", {}),
            emoji_counts=data.get("emoji_counts", {}),
            batch_records=[
                BatchRecord.from_dict(b)
                for b in data.get("batch_records", [])
            ],
            total_message_count=data.get("total_message_count", 0),
            total_character_count=data.get("total_character_count", 0),
            total_analysis_count=data.get("total_analysis_count", 0),
            total_token_usage=data.get("total_token_usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }),
            last_analyzed_message_timestamp=data.get("last_analyzed_message_timestamp", 0),
            all_participant_ids=set(data.get("all_participant_ids", [])),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
        return state

    def get_summary(self) -> dict:
        """
        获取当前增量状态的摘要信息，用于状态查询命令。

        Returns:
            dict: 包含关键统计信息的摘要
        """
        return {
            "group_id": self.group_id,
            "date": self.date_str,
            "total_messages": self.total_message_count,
            "total_characters": self.total_character_count,
            "total_analyses": self.total_analysis_count,
            "topics_count": len(self.topics),
            "quotes_count": len(self.golden_quotes),
            "participants": len(self.all_participant_ids),
            "total_tokens": self.total_token_usage.get("total_tokens", 0),
            "last_analysis_time": (
                datetime.fromtimestamp(self.updated_at).strftime("%H:%M:%S")
                if self.updated_at
                else "无"
            ),
            "peak_hours": self.get_peak_hours(3),
        }
