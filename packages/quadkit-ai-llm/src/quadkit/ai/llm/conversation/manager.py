"""Conversation management for multi-turn LLM interactions.

This module provides conversation management with context window handling,
automatic message trimming, token counting, and system prompt management.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.llm.types import ChatMessage, Completion, Role
from quadkit.contracts.ai.llm import TokenCounterProtocol
from quadkit.contracts.core import Metadata

if TYPE_CHECKING:
    from quadkit.contracts import AbstractLLMClient


__all__ = [
    "ConversationConfig",
    "ConversationManager",
    "ConversationStats",
]


from quadkit.ai.llm.conversation.types import ConversationConfig, ConversationStats


class ConversationManager:
    """Manage multi-turn conversations with automatic context window management.

    This class handles:
    - Message history management
    - Automatic token counting
    - Context window trimming
    - System prompt handling
    - Conversation statistics

    Example:
        >>> from quadkit.ai.llm import OpenAIClient, ConversationManager
        >>>
        >>> client = OpenAIClient(api_key="sk-...", model="gpt-4")
        >>> manager = ConversationManager(
        ...     client=client,
        ...     system_prompt="You are a helpful assistant.",
        ...     max_tokens=4096
        ... )
        >>>
        >>> # Add user message and get response
        >>> response = await manager.chat("What is Python?")
        >>> print(response.content)
        >>>
        >>> # Continue conversation
        >>> response = await manager.chat("Tell me more about it")
        >>> print(response.content)
        >>>
        >>> # Get conversation history
        >>> history = manager.get_history()
        >>> stats = manager.get_stats()
        >>> print(f"Total messages: {stats.total_messages}")
        >>> print(f"Total tokens: {stats.total_tokens}")
    """

    def __init__(
        self,
        client: AbstractLLMClient,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        reserve_tokens: int = 1000,
        trim_strategy: str = "oldest",
        metadata: Metadata | None = None,
        token_counter: TokenCounterProtocol | None = None,
    ) -> None:
        """Initialize conversation manager.

        Args:
            client: LLM client for completions
            system_prompt: Optional system prompt (prepended to all conversations)
            max_tokens: Maximum context window size
            reserve_tokens: Tokens to reserve for completion
            trim_strategy: Message trimming strategy ('oldest', 'middle', 'summary')
            metadata: Additional metadata for the conversation
            token_counter: Optional TokenCounterProtocol implementation.
                          If not provided, uses CharEstimateCounter.
        """
        self._client = client
        self._system_prompt = system_prompt
        self._messages: list[ChatMessage] = []
        self._metadata = metadata or {}

        # Initialize configuration
        self._config = ConversationConfig(
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
            trim_strategy=trim_strategy,
        )

        # Initialize token counter
        if token_counter is None:
            from quadkit.ai.llm.pricing.tokens import CharEstimateCounter

            token_counter = CharEstimateCounter()
        self._token_counter: TokenCounterProtocol = token_counter

        # Initialize stats
        self._stats = ConversationStats()

        # Add system message if provided
        if system_prompt:
            system_msg = ChatMessage(role=Role.SYSTEM, content=system_prompt)
            self._messages.append(system_msg)
            self._stats.system_messages += 1
            self._update_token_count_sync()

    async def chat(
        self,
        message: str,
        role: Role = Role.USER,
        **completion_kwargs: Any,
    ) -> Completion:
        """Send a message and get a response.

        Args:
            message: Message content
            role: Message role (default: USER)
            **completion_kwargs: Additional kwargs for completion

        Returns:
            Completion response from LLM

        Example:
            >>> response = await manager.chat("Hello!")
            >>> print(response.content)
        """
        # Add user message
        user_msg = ChatMessage(role=role, content=message)
        self._messages.append(user_msg)

        if role == Role.USER:
            self._stats.user_messages += 1
        elif role == Role.ASSISTANT:
            self._stats.assistant_messages += 1

        # Update token count and trim if needed
        await self._update_token_count()
        await self._trim_if_needed()

        # Get completion — pass ChatMessage objects directly to preserve thinking_blocks
        result = await self._client.complete(
            messages=self._messages,
            **completion_kwargs,
        )
        if result.is_err():
            raise result.unwrap_err()
        completion = result.unwrap()

        # Normalize string completions into Completion model for downstream consumers
        if isinstance(completion, str):
            model_name = completion_kwargs.get("model")
            if not isinstance(model_name, str):
                model_name = getattr(self._client, "model", None)
            if not isinstance(model_name, str):
                model_name = "unknown"
            completion = Completion(content=completion, model=model_name)

        # Add assistant response to history, preserving thinking blocks for
        # providers (e.g. Anthropic) that require re-injection in subsequent turns.
        thinking_blocks: list[dict[str, Any]] | None = None
        if completion.thinking and completion.thinking.signature:
            thinking_blocks = [
                {
                    "type": "thinking",
                    "thinking": completion.thinking.content,
                    "signature": completion.thinking.signature,
                }
            ]
        assistant_msg = ChatMessage(
            role=Role.ASSISTANT,
            content=completion.content,
            thinking_blocks=thinking_blocks,
        )
        self._messages.append(assistant_msg)
        self._stats.assistant_messages += 1

        # Update stats
        await self._update_token_count()
        self._stats.last_updated = datetime.now(UTC)

        return cast("Completion", completion)

    async def add_message(
        self,
        role: Role,
        content: str,
        update_stats: bool = True,
    ) -> None:
        """Add a message to conversation history without getting a response.

        Args:
            role: Message role
            content: Message content
            update_stats: Whether to update statistics

        Example:
            >>> await manager.add_message(Role.USER, "Hello")
            >>> await manager.add_message(Role.ASSISTANT, "Hi there!")
        """
        msg = ChatMessage(role=role, content=content)
        self._messages.append(msg)

        if update_stats:
            if role == Role.USER:
                self._stats.user_messages += 1
            elif role == Role.ASSISTANT:
                self._stats.assistant_messages += 1
            elif role == Role.SYSTEM:
                self._stats.system_messages += 1

            await self._update_token_count()
            self._stats.last_updated = datetime.now(UTC)

    def get_history(
        self,
        include_system: bool = True,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        """Get conversation history.

        Args:
            include_system: Include system message in history
            limit: Maximum number of messages to return (most recent)

        Returns:
            List of chat messages

        Example:
            >>> history = manager.get_history(limit=10)
            >>> for msg in history:
            ...     print(f"{msg.role}: {msg.content}")
        """
        messages = self._messages.copy()

        if not include_system:
            messages = list(filter(lambda msg: msg.role != Role.SYSTEM, messages))

        if limit is not None:
            messages = messages[-limit:]

        return messages

    def get_stats(self) -> ConversationStats:
        """Get conversation statistics.

        Returns:
            Conversation statistics

        Example:
            >>> stats = manager.get_stats()
            >>> print(f"Total tokens: {stats.total_tokens}")
        """
        return cast("ConversationStats", self._stats.model_copy())

    def clear_history(self, keep_system: bool = True) -> None:
        """Clear conversation history.

        Args:
            keep_system: Keep system message when clearing

        Example:
            >>> manager.clear_history()
        """
        if keep_system and self._system_prompt:
            system_msg = ChatMessage(role=Role.SYSTEM, content=self._system_prompt)
            self._messages = [system_msg]
            self._stats = ConversationStats(system_messages=1)
        else:
            self._messages = []
            self._stats = ConversationStats()

        self._update_token_count_sync()

    def update_system_prompt(self, system_prompt: str) -> None:
        """Update the system prompt.

        Args:
            system_prompt: New system prompt

        Example:
            >>> manager.update_system_prompt("You are a Python expert.")
        """
        self._system_prompt = system_prompt

        # Remove old system message and add new one
        self._messages = list(
            filter(lambda msg: msg.role != Role.SYSTEM, self._messages),
        )
        system_msg = ChatMessage(role=Role.SYSTEM, content=system_prompt)
        self._messages.insert(0, system_msg)

        self._update_token_count_sync()

    def get_token_count(self) -> int:
        """Get current total token count.

        Returns:
            Total tokens in conversation

        Example:
            >>> tokens = manager.get_token_count()
            >>> print(f"Current tokens: {tokens}")
        """
        return self._stats.total_tokens

    def get_available_tokens(self) -> int:
        """Get available tokens for completion.

        Returns:
            Available tokens (max_tokens - current_tokens - reserve_tokens)
            Can be negative if context window is exceeded

        Example:
            >>> available = manager.get_available_tokens()
            >>> print(f"Available for completion: {available}")
        """
        used = self._stats.total_tokens
        reserved = self._config.reserve_tokens
        max_tokens = self._config.max_tokens
        return max_tokens - used - reserved

    def _update_token_count_sync(self) -> None:
        """Update total token count synchronously (for initialization)."""
        self._stats.total_tokens = self._token_counter.count_messages(self._messages)
        self._stats.total_messages = len(self._messages)

    async def _update_token_count(self) -> None:
        """Update total token count."""
        self._stats.total_tokens = self._token_counter.count_messages(self._messages)
        self._stats.total_messages = len(self._messages)

    async def _trim_if_needed(self) -> None:
        """Trim messages if context window is exceeded."""
        available = self.get_available_tokens()

        if available < 0:
            # Need to trim messages
            if self._config.trim_strategy == "oldest":
                await self._trim_oldest()
            elif self._config.trim_strategy == "middle":
                await self._trim_middle()
            else:
                # Default to oldest if strategy not recognized
                await self._trim_oldest()

            self._stats.trimmed_count += 1

    async def _trim_oldest(self) -> None:
        """Trim oldest messages (keeping system message)."""
        # Keep system message if configured
        system_messages = []
        other_messages = []

        for msg in self._messages:
            if msg.role == Role.SYSTEM and self._config.keep_system:
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # Keep minimum number of messages
        min_keep = self._config.min_messages
        if len(other_messages) > min_keep:
            # Remove oldest messages until we're under token limit
            while self.get_available_tokens() < 0 and len(other_messages) > min_keep:
                other_messages.pop(0)

        self._messages = system_messages + other_messages
        await self._update_token_count()

    async def _trim_middle(self) -> None:
        """Trim middle messages (keeping system, first few, and last few)."""
        # Keep system message
        system_messages = []
        other_messages = []

        for msg in self._messages:
            if msg.role == Role.SYSTEM and self._config.keep_system:
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        if len(other_messages) <= self._config.min_messages:
            return

        # Keep first and last messages, remove middle
        keep_each_side = self._config.min_messages // 2
        while (
            self.get_available_tokens() < 0 and len(other_messages) > keep_each_side * 2
        ):
            # Remove from middle
            middle_idx = len(other_messages) // 2
            other_messages.pop(middle_idx)

        self._messages = system_messages + other_messages
        await self._update_token_count()

    def export_history(self) -> dict[str, Any]:
        """Export conversation history to dictionary.

        Returns:
            Dictionary with conversation data (JSON-serializable)

        Example:
            >>> data = manager.export_history()
            >>> from quadkit import serialization as json
            >>> with open("conversation.json", "w") as f:
            ...     json.dump(data, f)
        """
        return {
            "messages": [msg.model_dump(mode="json") for msg in self._messages],
            "stats": self._stats.model_dump(mode="json"),
            "config": self._config.model_dump(mode="json"),
            "metadata": self._metadata,
        }

    @classmethod
    def from_history(
        cls,
        client: AbstractLLMClient,
        history_data: dict[str, Any],
    ) -> ConversationManager:
        """Create conversation manager from exported history.

        Args:
            client: LLM client
            history_data: Exported history data

        Returns:
            ConversationManager instance

        Example:
            >>> from quadkit import serialization as json
            >>> with open("conversation.json") as f:
            ...     data = json.load(f)
            >>> manager = ConversationManager.from_history(client, data)
        """
        config = history_data.get("config", {})
        metadata = history_data.get("metadata", {})

        manager = cls(
            client=client,
            system_prompt=None,  # Will be loaded from messages
            max_tokens=config.get("max_tokens", 4096),
            reserve_tokens=config.get("reserve_tokens", 1000),
            trim_strategy=config.get("trim_strategy", "oldest"),
            metadata=metadata,
        )

        # Load messages
        messages_data = history_data.get("messages", [])
        manager._messages = [ChatMessage(**msg) for msg in messages_data]

        # Load stats
        stats_data = history_data.get("stats", {})
        if stats_data:
            manager._stats = ConversationStats(**stats_data)

        manager._update_token_count_sync()

        return manager

    def __len__(self) -> int:
        """Get number of messages in conversation."""
        return len(self._messages)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ConversationManager("
            f"messages={len(self._messages)}, "
            f"tokens={self._stats.total_tokens}, "
            f"available={self.get_available_tokens()})"
        )
