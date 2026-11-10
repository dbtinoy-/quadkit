"""Unit tests for ConversationManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.conversation.manager import ConversationManager
from quadkit.ai.llm.conversation.types import ConversationConfig, ConversationStats
from quadkit.ai.llm.types import ChatMessage, Completion, Role
from quadkit.result import Ok


def _make_client(response_content: str = "Hello!") -> MagicMock:
    """Create a mock LLM client returning an Ok(Completion)."""
    client = MagicMock()
    client.model = "test-model"
    completion = Completion(content=response_content, model="test-model")
    client.complete = AsyncMock(return_value=Ok(completion))
    return client


# ── ConversationConfig / ConversationStats ────────────────────────────

class TestConversationConfig:
    def test_defaults(self) -> None:
        cfg = ConversationConfig()
        assert cfg.max_tokens == 4096
        assert cfg.reserve_tokens == 1000
        assert cfg.trim_strategy == "oldest"
        assert cfg.keep_system is True
        assert cfg.min_messages == 2

    def test_custom_values(self) -> None:
        cfg = ConversationConfig(max_tokens=8192, trim_strategy="middle")
        assert cfg.max_tokens == 8192
        assert cfg.trim_strategy == "middle"


class TestConversationStats:
    def test_defaults(self) -> None:
        stats = ConversationStats()
        assert stats.total_messages == 0
        assert stats.total_tokens == 0
        assert stats.user_messages == 0
        assert stats.assistant_messages == 0
        assert stats.system_messages == 0
        assert stats.trimmed_count == 0


# ── ConversationManager init ─────────────────────────────────────────

class TestConversationManagerInit:
    def test_init_no_system_prompt(self) -> None:
        client = _make_client()
        mgr = ConversationManager(client=client)
        assert len(mgr) == 0
        assert mgr.get_token_count() == 0

    def test_init_with_system_prompt(self) -> None:
        client = _make_client()
        mgr = ConversationManager(client=client, system_prompt="Be helpful.")
        assert len(mgr) == 1
        history = mgr.get_history()
        assert history[0].role == Role.SYSTEM
        assert history[0].content == "Be helpful."

    def test_repr(self) -> None:
        client = _make_client()
        mgr = ConversationManager(client=client, system_prompt="sys")
        r = repr(mgr)
        assert "ConversationManager" in r


# ── chat() ────────────────────────────────────────────────────────────

class TestConversationManagerChat:
    @pytest.mark.asyncio
    async def test_chat_adds_user_and_assistant_messages(self) -> None:
        client = _make_client("World")
        mgr = ConversationManager(client=client)

        result = await mgr.chat("Hello")
        assert result.content == "World"
        assert len(mgr) == 2  # user + assistant

        stats = mgr.get_stats()
        assert stats.user_messages == 1
        assert stats.assistant_messages == 1

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self) -> None:
        client = _make_client("Sure")
        mgr = ConversationManager(client=client, system_prompt="Be brief.")

        result = await mgr.chat("Summarize")
        assert result.content == "Sure"
        assert len(mgr) == 3  # system + user + assistant

    @pytest.mark.asyncio
    async def test_chat_multiple_turns(self) -> None:
        client = _make_client("Reply")
        mgr = ConversationManager(client=client)

        await mgr.chat("Turn 1")
        await mgr.chat("Turn 2")
        await mgr.chat("Turn 3")

        stats = mgr.get_stats()
        assert stats.user_messages == 3
        assert stats.assistant_messages == 3


# ── add_message() ────────────────────────────────────────────────────

class TestAddMessage:
    @pytest.mark.asyncio
    async def test_add_message_user(self) -> None:
        mgr = ConversationManager(client=_make_client())
        await mgr.add_message(Role.USER, "Hello")
        assert len(mgr) == 1

    @pytest.mark.asyncio
    async def test_add_message_assistant(self) -> None:
        mgr = ConversationManager(client=_make_client())
        await mgr.add_message(Role.ASSISTANT, "Hi")
        stats = mgr.get_stats()
        assert stats.assistant_messages == 1

    @pytest.mark.asyncio
    async def test_add_message_system(self) -> None:
        mgr = ConversationManager(client=_make_client())
        await mgr.add_message(Role.SYSTEM, "Context")
        stats = mgr.get_stats()
        assert stats.system_messages == 1

    @pytest.mark.asyncio
    async def test_add_message_no_stats(self) -> None:
        mgr = ConversationManager(client=_make_client())
        await mgr.add_message(Role.USER, "No stats", update_stats=False)
        assert len(mgr) == 1
        assert mgr.get_stats().user_messages == 0


# ── get_history() ────────────────────────────────────────────────────

class TestGetHistory:
    def test_get_history_includes_system(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        history = mgr.get_history(include_system=True)
        assert len(history) == 1
        assert history[0].role == Role.SYSTEM

    def test_get_history_excludes_system(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        history = mgr.get_history(include_system=False)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self) -> None:
        mgr = ConversationManager(client=_make_client())
        await mgr.add_message(Role.USER, "a")
        await mgr.add_message(Role.ASSISTANT, "b")
        await mgr.add_message(Role.USER, "c")

        history = mgr.get_history(limit=2)
        assert len(history) == 2
        assert history[0].content == "b"
        assert history[1].content == "c"


# ── clear_history() ─────────────────────────────────────────────────

class TestClearHistory:
    def test_clear_keep_system(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        mgr.clear_history(keep_system=True)
        assert len(mgr) == 1
        assert mgr.get_history()[0].role == Role.SYSTEM

    def test_clear_remove_system(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        mgr.clear_history(keep_system=False)
        assert len(mgr) == 0


# ── update_system_prompt() ───────────────────────────────────────────

class TestUpdateSystemPrompt:
    def test_update_system_prompt(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="old")
        mgr.update_system_prompt("new")
        history = mgr.get_history()
        assert history[0].content == "new"
        assert len(history) == 1


# ── get_available_tokens() ───────────────────────────────────────────

class TestGetAvailableTokens:
    def test_available_tokens(self) -> None:
        mgr = ConversationManager(
            client=_make_client(), max_tokens=4096, reserve_tokens=1000
        )
        # Initially 0 tokens used ⇒ available = 4096 - 0 - 1000
        assert mgr.get_available_tokens() == 3096


# ── export / from_history ────────────────────────────────────────────

class TestExportImport:
    def test_export_history(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        data = mgr.export_history()
        assert "messages" in data
        assert "stats" in data
        assert "config" in data
        assert data["messages"][0]["role"] == "system"

    def test_from_history_roundtrip(self) -> None:
        mgr = ConversationManager(client=_make_client(), system_prompt="sys")
        data = mgr.export_history()

        mgr2 = ConversationManager.from_history(_make_client(), data)
        assert len(mgr2) == 1
        assert mgr2.get_history()[0].content == "sys"
