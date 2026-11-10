"""Unit tests for quadkit-ai-llm conversation management."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.conversation.manager import (
    ConversationConfig,
    ConversationManager,
    ConversationStats,
)
from quadkit.ai.llm.types import ChatMessage, Role


class TestConversationConfig:
    """Tests for ConversationConfig."""

    def test_default_config(self) -> None:
        """Test ConversationConfig default values."""
        config = ConversationConfig()

        assert config.max_tokens == 4096
        assert config.reserve_tokens == 1000
        assert config.trim_strategy == "oldest"
        assert config.keep_system is True
        assert config.min_messages == 2

    def test_custom_config(self) -> None:
        """Test ConversationConfig with custom values."""
        config = ConversationConfig(
            max_tokens=8192,
            reserve_tokens=2000,
            trim_strategy="summary",
            keep_system=False,
            min_messages=1,
        )

        assert config.max_tokens == 8192
        assert config.reserve_tokens == 2000
        assert config.trim_strategy == "summary"
        assert config.keep_system is False
        assert config.min_messages == 1


class TestConversationStats:
    """Tests for ConversationStats."""

    def test_default_stats(self) -> None:
        """Test ConversationStats default values."""
        stats = ConversationStats()

        assert stats.total_messages == 0
        assert stats.total_tokens == 0
        assert stats.user_messages == 0
        assert stats.assistant_messages == 0

    def test_custom_stats(self) -> None:
        """Test ConversationStats with custom values."""
        stats = ConversationStats(
            total_messages=10,
            total_tokens=2048,
            user_messages=5,
            assistant_messages=5,
        )

        assert stats.total_messages == 10
        assert stats.total_tokens == 2048
        assert stats.user_messages == 5
        assert stats.assistant_messages == 5


class TestConversationManager:
    """Tests for ConversationManager."""

    @pytest.mark.asyncio
    async def test_empty_conversation(self) -> None:
        """Test ConversationManager with no messages."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        history = manager.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_add_message(self) -> None:
        """Test adding a message via add_message."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="Hello, AI!")

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].role == Role.USER
        assert history[0].content == "Hello, AI!"

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self) -> None:
        """Test adding multiple messages."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="Hello")
        await manager.add_message(role=Role.ASSISTANT.value, content="Hi there")
        await manager.add_message(role=Role.USER.value, content="How are you?")

        history = manager.get_history()
        assert len(history) == 3
        assert history[0].content == "Hello"
        assert history[1].content == "Hi there"
        assert history[2].content == "How are you?"

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test getting conversation statistics."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="Hello")
        await manager.add_message(role=Role.ASSISTANT.value, content="Hi")

        stats = manager.get_stats()
        assert stats.total_messages == 2
        assert stats.user_messages == 1
        assert stats.assistant_messages == 1

    @pytest.mark.asyncio
    async def test_token_count(self) -> None:
        """Test getting token count."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="Hello world")

        # Token count should be calculated
        token_count = manager.get_token_count()
        assert token_count >= 0

    @pytest.mark.asyncio
    async def test_available_tokens(self) -> None:
        """Test getting available tokens for completion."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="Test")

        available = manager.get_available_tokens()
        assert available >= 0
        assert available <= config.max_tokens


class TestConversationManagerChatMessage:
    """Tests using ChatMessage objects."""

    @pytest.mark.asyncio
    async def test_add_chat_message_object(self) -> None:
        """Test adding ChatMessage object."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        msg = ChatMessage(
            role=Role.USER,
            content="Hello",
            name="user1",
        )
        await manager.add_message(role=msg.role.value, content=msg.content)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].content == "Hello"


class TestConversationManagerEdgeCases:
    """Edge case tests for ConversationManager."""

    @pytest.mark.asyncio
    async def test_system_message(self) -> None:
        """Test adding system message."""
        config = ConversationConfig(keep_system=True)
        manager = ConversationManager(config)

        await manager.add_message(role=Role.SYSTEM.value, content="You are helpful.")
        await manager.add_message(role=Role.USER.value, content="Hi")

        history = manager.get_history()
        # System message should be first
        assert history[0].role == Role.SYSTEM
        assert history[0].content == "You are helpful."

    @pytest.mark.asyncio
    async def test_empty_message_content(self) -> None:
        """Test adding empty message content."""
        config = ConversationConfig()
        manager = ConversationManager(config)

        await manager.add_message(role=Role.USER.value, content="")

        history = manager.get_history()
        assert len(history) == 1
