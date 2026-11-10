"""Types and models for conversation management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from quadkit.domain import DomainModel
from quadkit.validation import Field

__all__ = ["ConversationConfig", "ConversationStats"]


@dataclass(init=False)
class ConversationConfig(DomainModel):
    """Configuration for conversation management.

    Example:
        >>> config = ConversationConfig(
        ...     max_tokens=4096,
        ...     reserve_tokens=1000,
        ...     trim_strategy="oldest"
        ... )
    """

    max_tokens: int = Field(
        default=4096,
        description="Maximum context window size in tokens",
    )
    reserve_tokens: int = Field(
        default=1000,
        description="Tokens to reserve for completion (subtracted from max_tokens)",
    )
    trim_strategy: str = Field(
        default="oldest",
        description="Strategy for trimming messages: 'oldest', 'middle', 'summary'",
    )
    keep_system: bool = Field(
        default=True,
        description="Always keep system message when trimming",
    )
    min_messages: int = Field(
        default=2,
        description="Minimum messages to keep (excluding system)",
    )


@dataclass(init=False)
class ConversationStats(DomainModel):
    """Statistics for a conversation.

    Example:
        >>> stats = ConversationStats(
        ...     total_messages=10,
        ...     total_tokens=2048,
        ...     user_messages=5,
        ...     assistant_messages=5
        ... )
    """

    total_messages: int = Field(default=0, description="Total messages in conversation")
    total_tokens: int = Field(default=0, description="Total tokens used")
    user_messages: int = Field(default=0, description="Number of user messages")
    assistant_messages: int = Field(
        default=0,
        description="Number of assistant messages",
    )
    system_messages: int = Field(default=0, description="Number of system messages")
    trimmed_count: int = Field(
        default=0,
        description="Number of times messages were trimmed",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Conversation creation time",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update time",
    )
