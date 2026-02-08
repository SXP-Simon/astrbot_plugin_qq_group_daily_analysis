"""
Topic Value Object - Platform-agnostic topic representation

This value object represents a discussion topic extracted from group chat messages.
It is immutable and contains no platform-specific logic.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Topic:
    """
    Topic value object for group chat analysis.

    Represents a discussion topic with contributors and details.
    Immutable by design (frozen=True).

    Attributes:
        name: Topic title/name
        contributors: List of usernames who participated in this topic
        detail: Detailed description or summary of the topic discussion
    """

    name: str
    contributors: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""

    def __post_init__(self):
        """Validate topic data after initialization."""
        if not self.name or not self.name.strip():
            object.__setattr__(self, "name", "Unknown Topic")

        # Ensure contributors is a tuple for immutability
        if isinstance(self.contributors, list):
            object.__setattr__(self, "contributors", tuple(self.contributors))

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        """
        Create Topic from dictionary data.

        Args:
            data: Dictionary with topic data

        Returns:
            Topic instance
        """
        contributors = data.get("contributors", [])
        if isinstance(contributors, list):
            contributors = tuple(contributors)

        return cls(
            name=data.get("topic", data.get("name", "")).strip(),
            contributors=contributors,
            detail=data.get("detail", "").strip(),
        )

    def to_dict(self) -> dict:
        """
        Convert Topic to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "topic": self.name,
            "contributors": list(self.contributors),
            "detail": self.detail,
        }

    @property
    def contributor_count(self) -> int:
        """Get the number of contributors."""
        return len(self.contributors)

    @property
    def is_valid(self) -> bool:
        """Check if topic has valid data."""
        return bool(self.name and self.name.strip() and self.detail and self.detail.strip())


@dataclass
class TopicCollection:
    """
    Collection of topics with utility methods.

    This is mutable to allow building up a collection of topics.
    """

    topics: List[Topic] = field(default_factory=list)

    def add(self, topic: Topic) -> None:
        """Add a topic to the collection."""
        if topic.is_valid:
            self.topics.append(topic)

    def add_from_dict(self, data: dict) -> None:
        """Add a topic from dictionary data."""
        topic = Topic.from_dict(data)
        self.add(topic)

    def to_list(self) -> List[dict]:
        """Convert all topics to list of dictionaries."""
        return [t.to_dict() for t in self.topics]

    def __len__(self) -> int:
        return len(self.topics)

    def __iter__(self):
        return iter(self.topics)
