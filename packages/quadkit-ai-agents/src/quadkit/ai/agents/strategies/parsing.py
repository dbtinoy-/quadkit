"""Shared parsing utilities for agent strategies."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.ai.llm import ChatMessage, Role


def extract_thought(text: str) -> str:
    """Extract the THOUGHT section from the LLM response."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("THOUGHT:"):
            return stripped[len("THOUGHT:") :].strip()
    return text.split("\n", maxsplit=1)[0][:200]


def extract_final_answer(text: str) -> str | None:
    """Extract FINAL_ANSWER if present."""
    marker = "FINAL_ANSWER:"
    upper = text.upper()
    idx = upper.find(marker)
    if idx == -1:
        return None
    return text[idx + len(marker) :].strip()


def extract_tool_call(text: str) -> tuple[str | None, dict[str, Any]]:
    """Extract ACTION and ACTION_INPUT from the LLM response."""
    from quadkit.serialization.backends.json import JSONDecodeError, loads

    action_name: str | None = None
    action_input: dict[str, Any] = {}

    for line in text.split("\n"):
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("ACTION:") and not upper.startswith("ACTION_INPUT:"):
            action_name = stripped[len("ACTION:") :].strip()
        elif upper.startswith("ACTION_INPUT:"):
            raw = stripped[len("ACTION_INPUT:") :].strip()
            try:
                action_input = loads(raw)
            except (ValueError, JSONDecodeError):
                remaining = text[text.index(stripped) :]
                brace_start = remaining.find("{")
                if brace_start != -1:
                    depth = 0
                    for i, ch in enumerate(remaining[brace_start:]):
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        if depth == 0:
                            try:
                                action_input = loads(
                                    remaining[brace_start : brace_start + i + 1]
                                )
                            except (ValueError, JSONDecodeError):
                                pass
                            break

    return action_name, action_input


def build_chat_messages(
    message: str,
    history: list[ChatMessage],
    system_prompt: str,
) -> list[ChatMessage]:
    """Convert history + new message into ChatMessage objects."""
    messages: list[ChatMessage] = []

    if system_prompt:
        messages.append(ChatMessage(role=Role.SYSTEM, content=system_prompt))

    messages.extend(history)

    messages.append(ChatMessage(role=Role.USER, content=message))
    return messages


def build_chat_messages_from_dict(
    message: str,
    history: list[dict[str, Any]],
    system_prompt: str,
) -> list[ChatMessage]:
    """Convert history (as dicts) + new message into ChatMessage objects."""
    messages: list[ChatMessage] = []

    if system_prompt:
        messages.append(ChatMessage(role=Role.SYSTEM, content=system_prompt))

    for entry in history:
        role_str = entry.get("role", "user")
        content = entry.get("content", "")
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.USER
        messages.append(ChatMessage(role=role, content=content))

    messages.append(ChatMessage(role=Role.USER, content=message))
    return messages


__all__ = [
    "build_chat_messages",
    "build_chat_messages_from_dict",
    "extract_final_answer",
    "extract_thought",
    "extract_tool_call",
]
