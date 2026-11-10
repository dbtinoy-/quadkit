"""Test ChatMessage multimodal content support."""

from __future__ import annotations

from quadkit.contracts.ai.multimodal import ImageUrlPart, TextPart


def test_contracts_chat_message_accepts_list_content() -> None:
    """ChatMessage in contracts must accept list[ContentPart] for content."""
    from quadkit.contracts.ai.llm import ChatMessage as ContractsChatMessage
    from quadkit.contracts.ai.llm import Role

    msg = ContractsChatMessage(
        role=Role.USER,
        content=[
            TextPart(text="Describe this image"),
            ImageUrlPart(url="https://example.com/cat.jpg"),
        ],
    )
    assert isinstance(msg.content, list)
    assert msg.content[1].url == "https://example.com/cat.jpg"


def test_llm_chat_message_accepts_list_content() -> None:
    """ChatMessage in quadkit-ai-llm must accept list[ContentPart]."""
    from quadkit.ai.llm.types import ChatMessage
    from quadkit.contracts.ai.llm import Role

    msg = ChatMessage(
        role=Role.USER,
        content=[
            TextPart(text="What is in this photo?"),
            ImageUrlPart(url="https://example.com/photo.jpg"),
        ],
    )
    assert isinstance(msg.content, list)
    assert len(msg.content) == 2


def test_llm_chat_message_str_content_still_works() -> None:
    """String content must remain backward-compatible."""
    from quadkit.ai.llm.types import ChatMessage
    from quadkit.contracts.ai.llm import Role

    msg = ChatMessage(role=Role.USER, content="hello")
    assert msg.content == "hello"


def test_contracts_chat_message_str_content_still_works() -> None:
    """String content must remain backward-compatible in contracts ChatMessage."""
    from quadkit.contracts.ai.llm import ChatMessage as ContractsChatMessage
    from quadkit.contracts.ai.llm import Role

    msg = ContractsChatMessage(role=Role.USER, content="legacy string")
    assert msg.content == "legacy string"
