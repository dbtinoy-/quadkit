"""Tests for Memory composition contracts (G-02 parity)."""
from __future__ import annotations

import pytest


def test_conversation_memory_add_message():
    """ConversationMemory should add a message."""
    from quadkit.contracts.ai.memory import ConversationMemory
    mem = ConversationMemory()
    mem.add_message("Hello")
    assert "Hello" in mem.get_messages()


def test_conversation_memory_limits():
    """ConversationMemory should respect max_messages."""
    from quadkit.contracts.ai.memory import ConversationMemory
    mem = ConversationMemory(max_messages=2)
    mem.add_message("first")
    mem.add_message("second")
    mem.add_message("third")  # should evict first
    msgs = mem.get_messages()
    assert len(msgs) == 2
    assert "third" in msgs


def test_window_memory_limits():
    """WindowMemory should keep only last N messages."""
    from quadkit.contracts.ai.memory import WindowMemory
    mem = WindowMemory(window_size=2)
    for i in range(5):
        mem.add_message(f"msg{i}")
    msgs = mem.get_messages()
    assert len(msgs) == 2


def test_memory_protocol_exists():
    """MemoryProtocol should exist for parity."""
    from quadkit.contracts.ai.memory import MemoryProtocol
    assert MemoryProtocol is not None
