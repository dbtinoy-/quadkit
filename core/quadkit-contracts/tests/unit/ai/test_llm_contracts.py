"""Tests for LLM protocols in contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass

import pytest
from quadkit.contracts.ai.llm import Completion, CompletionProtocol


class TestCompletionSatisfiesProtocol:
    """Completion must remain structurally compatible with CompletionProtocol."""

    def test_instance_of_runtime_protocol(self) -> None:
        assert isinstance(Completion("hi", "fake"), CompletionProtocol)

    def test_any_frozen_value_object_satisfies_protocol(self) -> None:
        """Read-only protocol members must be satisfiable by immutable data."""

        @dataclass(frozen=True)
        class FrozenCompletion:
            content: str
            model: str
            thinking: object | None = None
            usage: dict[str, int] | None = None

        assert isinstance(FrozenCompletion("hi", "fake"), CompletionProtocol)


class TestCompletionUsage:
    """The usage field pins provider token accounting end to end."""

    def test_defaults_to_none(self) -> None:
        assert Completion("hi", "fake").usage is None

    def test_accepts_token_counts(self) -> None:
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        completion = Completion("hi", "fake", usage=usage)
        assert completion.usage == usage

    def test_is_frozen(self) -> None:
        completion = Completion("hi", "fake")
        with pytest.raises(FrozenInstanceError):
            completion.content = "mutated"  # type: ignore[misc]