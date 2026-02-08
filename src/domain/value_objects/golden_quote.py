"""
GoldenQuote Value Object - Platform-agnostic golden quote representation

This value object represents a memorable quote extracted from group chat messages.
It is immutable and contains no platform-specific logic.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class GoldenQuote:
    """
    GoldenQuote value object for group chat analysis.

    Represents a memorable/interesting quote from the chat.
    Immutable by design (frozen=True).

    Attributes:
        content: The actual quote content
        sender: Display name of the person who said it
        reason: Why this quote was selected as golden
        user_id: Platform-agnostic user identifier (stored as string)
    """

    content: str
    sender: str
    reason: str = ""
    user_id: str = ""

    def __post_init__(self):
        """Validate and normalize golden quote data after initialization."""
        # Ensure user_id is always a string
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenQuote":
        """
        Create GoldenQuote from dictionary data.

        Args:
            data: Dictionary with golden quote data

        Returns:
            GoldenQuote instance
        """
        # Handle both 'qq' and 'user_id' keys for backward compatibility
        user_id = data.get("user_id", data.get("qq", ""))

        return cls(
            content=data.get("content", "").strip(),
            sender=data.get("sender", "").strip(),
            reason=data.get("reason", "").strip(),
            user_id=str(user_id) if user_id else "",
        )

    def to_dict(self) -> dict:
        """
        Convert GoldenQuote to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "content": self.content,
            "sender": self.sender,
            "reason": self.reason,
            "user_id": self.user_id,
            "qq": int(self.user_id) if self.user_id.isdigit() else 0,  # Backward compat
        }

    @property
    def is_valid(self) -> bool:
        """Check if golden quote has valid data."""
        return bool(
            self.content and self.content.strip() and self.sender and self.sender.strip()
        )

    @property
    def qq(self) -> int:
        """Get QQ number for backward compatibility."""
        try:
            return int(self.user_id)
        except (ValueError, TypeError):
            return 0

    def with_user_id(self, user_id: str) -> "GoldenQuote":
        """
        Create a new GoldenQuote with updated user_id.

        Since GoldenQuote is frozen, we need to create a new instance.

        Args:
            user_id: The user ID to set

        Returns:
            New GoldenQuote instance with updated user_id
        """
        return GoldenQuote(
            content=self.content,
            sender=self.sender,
            reason=self.reason,
            user_id=str(user_id),
        )


@dataclass
class GoldenQuoteCollection:
    """
    Collection of golden quotes with utility methods.

    This is mutable to allow building up a collection of quotes.
    """

    quotes: List[GoldenQuote] = field(default_factory=list)

    def add(self, quote: GoldenQuote) -> None:
        """Add a golden quote to the collection."""
        if quote.is_valid:
            self.quotes.append(quote)

    def add_from_dict(self, data: dict) -> None:
        """Add a golden quote from dictionary data."""
        quote = GoldenQuote.from_dict(data)
        self.add(quote)

    def to_list(self) -> List[dict]:
        """Convert all quotes to list of dictionaries."""
        return [q.to_dict() for q in self.quotes]

    def __len__(self) -> int:
        return len(self.quotes)

    def __iter__(self):
        return iter(self.quotes)
