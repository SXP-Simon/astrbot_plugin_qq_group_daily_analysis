"""
单元测试：AnalysisResultSerializer 领域模型序列化与反序列化器
"""

from src.application.services.analysis_serializer import AnalysisResultSerializer
from src.domain.models.data_models import (
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)


def test_to_json_friendly_primitives_and_dataclass():
    """测试基本类型与 dataclass 的 JSON 友好转换。"""
    quote = GoldenQuote(content="测试金句", sender="Alice", reason="幽默", user_id="1001")
    serialized = AnalysisResultSerializer.to_json_friendly(quote)
    assert isinstance(serialized, dict)
    assert serialized["content"] == "测试金句"
    assert serialized["sender"] == "Alice"
    assert serialized["user_id"] == "1001"


def test_serialize_and_deserialize_roundtrip():
    """测试分析结果的完整往返序列化与反序列化。"""
    stats = GroupStatistics(
        message_count=100,
        total_characters=2500,
        participant_count=10,
        most_active_period="20:00-21:00",
        golden_quotes=[
            GoldenQuote(
                content="金句内容", sender="Bob", reason="精彩", user_id="1002"
            )
        ],
        emoji_count=5,
        emoji_statistics=EmojiStatistics(face_count=3, other_emoji_count=2),
        activity_visualization=ActivityVisualization(
            hourly_activity={20: 50, 21: 50}, peak_hours=[20, 21]
        ),
        token_usage=TokenUsage(prompt_tokens=150, completion_tokens=80, total_tokens=230),
        chat_quality_review=QualityReview(
            title="群聊质量锐评",
            subtitle="高活跃群组",
            dimensions=[
                QualityDimension(
                    name="技术交流", percentage=60.0, comment="浓厚", color="#00ff00"
                ),
                QualityDimension(
                    name="生活闲聊", percentage=40.0, comment="活跃", color="#0000ff"
                ),
            ],
            summary="综合质量高",
        ),
    )

    topics = [
        SummaryTopic(
            topic="DDD重构讨论",
            contributors=["Alice", "Bob"],
            detail="讨论关于分层架构的设计",
            contributor_ids=["1001", "1002"],
        )
    ]
    user_titles = [
        UserTitle(
            name="Alice",
            user_id="1001",
            title="架构师",
            mbti="INTJ",
            reason="提出了清晰的重构方案",
        )
    ]

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "user_analysis": {"1001": {"score": 99}},
        "chat_quality_review": stats.chat_quality_review,
    }

    # 1. 序列化
    serialized = AnalysisResultSerializer.serialize(analysis_result)
    assert isinstance(serialized, dict)
    assert isinstance(serialized["statistics"], dict)
    assert serialized["statistics"]["message_count"] == 100
    assert len(serialized["topics"]) == 1
    assert serialized["topics"][0]["topic"] == "DDD重构讨论"

    # 2. 反序列化
    deserialized = AnalysisResultSerializer.deserialize(serialized)
    assert isinstance(deserialized["statistics"], GroupStatistics)
    assert deserialized["statistics"].message_count == 100
    assert len(deserialized["topics"]) == 1
    assert isinstance(deserialized["topics"][0], SummaryTopic)
    assert deserialized["topics"][0].topic == "DDD重构讨论"
    assert len(deserialized["user_titles"]) == 1
    assert isinstance(deserialized["user_titles"][0], UserTitle)
    assert deserialized["user_titles"][0].title == "架构师"
    assert isinstance(deserialized["chat_quality_review"], QualityReview)
    assert deserialized["chat_quality_review"].title == "群聊质量锐评"
    assert len(deserialized["chat_quality_review"].dimensions) == 2
