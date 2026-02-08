"""
UserTitle Value Object - Platform-agnostic user title representation

This value object represents a user's title/badge assigned based on their
chat behavior analysis. It is immutable and contains no platform-specific logic.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class UserTitle:
    """
    UserTitle value object for group chat analysis.

    Represents a title/badge assigned to a user based on their behavior.
    Immutable by design (frozen=True).

    Attributes:
        name: User's display name
        user_id: Platform-agnostic user identifier (stored as string)
        title: The title/badge assigned to the user
        mbti: MBTI personality type assessment
        reason: Explanation for why this title was assigned
    """

    name: str
    user_id: str
    title: str
    mbti: str = ""
    reason: str = ""

    def __post_init__(self):
        """Validate and normalize user title data after initialization."""
        # Ensure user_id is always a string
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "UserTitle":
        """
        Create UserTitle from dictionary data.

        Args:
            data: Dictionary with user title data

        Returns:
            UserTitle instance
        """
        # Handle both 'qq' and 'user_id' keys for backward compatibility
        user_id = data.get("user_id", data.get("qq", ""))

        return cls(
            name=data.get("name", "").strip(),
            user_id=str(user_id),
            title=data.get("title", "").strip(),
            mbti=data.get("mbti", "").strip().upper(),
            reason=data.get("reason", "").strip(),
        )

    def to_dict(self) -> dict:
        """
        Convert UserTitle to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "user_id": self.user_id,
            "qq": int(self.user_id) if self.user_id.isdigit() else 0,  # Backward compat
            "title": self.title,
            "mbti": self.mbti,
            "reason": self.reason,
        }

    @property
    def is_valid(self) -> bool:
        """Check if user title has valid data."""
        return bool(
            self.name
            and self.name.strip()
            and self.title
            and self.title.strip()
            and self.user_id
        )

    @property
    def qq(self) -> int:
        """Get QQ number for backward compatibility."""
        try:
            return int(self.user_id)
        except (ValueError, TypeError):
            return 0


@dataclass
class UserTitleCollection:
    """
    Collection of user titles with utility methods.

    This is mutable to allow building up a collection of titles.
    """

    titles: List[UserTitle] = field(default_factory=list)

    def add(self, title: UserTitle) -> None:
        """Add a user title to the collection."""
        if title.is_valid:
            self.titles.append(title)

    def add_from_dict(self, data: dict) -> None:
        """Add a user title from dictionary data."""
        title = UserTitle.from_dict(data)
        self.add(title)

    def get_by_user_id(self, user_id: str) -> UserTitle | None:
        """Get title by user ID."""
        user_id_str = str(user_id)
        for title in self.titles:
            if title.user_id == user_id_str:
                return title
        return None

    def to_list(self) -> List[dict]:
        """Convert all titles to list of dictionaries."""
        return [t.to_dict() for t in self.titles]

    def __len__(self) -> int:
        return len(self.titles)

    def __iter__(self):
        return iter(self.titles)
