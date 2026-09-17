"""Chat History contracts for Quadkit.

Defines chat message and history classes analogous to LangChain's chat history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    """A chat message (like LangChain's BaseMessage).

    Attributes:
        role: The role (user, assistant, system).
        content: The message content.
    """

    role: str
    content: str
    name: str | None = None
    additional_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_lc_dict(self) -> dict[str, Any]:
        """Convert to LangChain dict format."""
        return {
            "type": "human" if self.role == "user" else "ai",
            "data": {
                "content": self.content,
                "additional_kwargs": self.additional_kwargs,
            },
        }


class ChatHistory:
    """Chat history (like LangChain's ChatMessageHistory).

    Manages chat messages and converts to LangChain format.
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self._messages.append(ChatMessage(role="user", content=content))

    def add_ai_message(self, content: str) -> None:
        """Add an AI message."""
        self._messages.append(ChatMessage(role="assistant", content=content))

    def add_message(self, message: ChatMessage) -> None:
        """Add a message."""
        self._messages.append(message)

    def get_messages(self) -> list[ChatMessage]:
        """Get all messages."""
        return list(self._messages)

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    def to_lc_format(self) -> list[dict[str, Any]]:
        """Convert to LangChain message format."""
        return [msg.to_lc_dict() for msg in self._messages]


__all__ = [
    "ChatHistory",
    "ChatMessage",
]
