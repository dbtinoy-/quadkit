"""Shared token accounting helpers for agent strategies.

Every strategy funnels LLM completions through these helpers so token
usage is counted consistently. Semantics mirror the original
``function_calling`` implementation: prefer the prompt/completion split
when either side is reported, fall back to ``usage.total_tokens``, and
return ``0`` when usage is missing entirely.
"""

from __future__ import annotations

from quadkit.contracts.ai.llm import Completion, CompletionProtocol

CompletionInput = Completion | CompletionProtocol


def token_split(completion: CompletionInput) -> tuple[int, int]:
    """Extract the prompt/completion token split from a completion.

    Args:
        completion: LLM completion result.

    Returns:
        Tuple of ``(prompt_tokens, completion_tokens)``.  Both are
        ``0`` when usage is missing or not reported.
    """
    usage = getattr(completion, "usage", None)
    if not usage:
        return 0, 0
    if isinstance(usage, dict):
        return (
            int(usage.get("prompt_tokens", 0) or 0),
            int(usage.get("completion_tokens", 0) or 0),
        )
    return (
        int(getattr(usage, "prompt_tokens", 0) or 0),
        int(getattr(usage, "completion_tokens", 0) or 0),
    )


def count_tokens(completion: CompletionInput) -> int:
    """Count total tokens for a completion.

    Prefers the prompt/completion split when either side is reported;
    otherwise falls back to ``usage.total_tokens``.  Returns ``0`` when
    usage is missing entirely.

    Args:
        completion: LLM completion result.

    Returns:
        Total token count consumed by the completion.
    """
    prompt, completion_tokens = token_split(completion)
    if prompt or completion_tokens:
        return prompt + completion_tokens
    usage = getattr(completion, "usage", None)
    if isinstance(usage, dict):
        return int(usage.get("total_tokens", 0) or 0)
    return int(getattr(usage, "total_tokens", 0) or 0)


class TokenAccumulator:
    """Mutable token totals accumulated across multiple LLM calls."""

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, completion: CompletionInput) -> None:
        """Accumulate usage from one completion.

        Args:
            completion: LLM completion result.
        """
        prompt, completion_tokens = token_split(completion)
        self.prompt_tokens += prompt
        self.completion_tokens += completion_tokens
        self.total_tokens += count_tokens(completion)


__all__ = ["TokenAccumulator", "count_tokens", "token_split"]
