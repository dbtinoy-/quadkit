"""Tests for Chat History contracts."""
from __future__ import annotations


def test_chat_message():
    """ChatMessage should have role and content."""
    from quadkit.contracts.ai.chat import ChatMessage
    
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_history():
    """ChatHistory should manage messages."""
    from quadkit.contracts.ai.chat import ChatHistory, ChatMessage
    
    history = ChatHistory()
    history.add_user_message("Hi")
    history.add_ai_message("Hello there!")
    
    messages = history.get_messages()
    assert len(messages) == 2
    assert messages[0].role == "user"


def test_chat_history_to_lc_format():
    """ChatHistory should convert to LangChain format."""
    from quadkit.contracts.ai.chat import ChatHistory
    
    history = ChatHistory()
    history.add_user_message("Hi")
    history.add_ai_message("Hello")
    
    lc_format = history.to_lc_format()
    assert len(lc_format) == 2
