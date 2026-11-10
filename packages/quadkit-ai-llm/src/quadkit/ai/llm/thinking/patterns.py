"""Thinking block pattern definitions for LLM output extraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThinkingPattern:
    """Pattern for detecting and extracting thinking blocks from LLM output.

    Attributes:
        name: Human-readable name of the pattern.
        start_marker: Opening delimiter. May be empty string for bare-closing variant.
        end_marker: Closing delimiter.
        strip_end_marker: Whether the end marker itself should be removed from content.
    """

    name: str
    start_marker: str
    end_marker: str
    strip_end_marker: bool


# Ordered list of patterns (most specific first)
# Ordered list of patterns (most specific first)
THINKING_PATTERNS: list[ThinkingPattern] = [
    # Gemma-4 channel format — handled by _extract_gemma_channel() in normalizer.py.
    # Official format: <|channel>thought\n...thinking...\n<channel|>\n...response...
    # The start_marker here is unused by the special-case handler but kept for
    # documentation. The normalizer identifies this entry by name="gemma_channel".
    ThinkingPattern(
        name="gemma_channel",
        start_marker="<|channel>thought",
        end_marker="<channel|>",
        strip_end_marker=True,
    ),
    # Qwen3 pipe-delimited format: <|think|>...</|think|>
    ThinkingPattern(
        name="qwen3_pipe",
        start_marker="<|think|>",
        end_marker="</|think|>",
        strip_end_marker=True,
    ),
    # XML think tags (DeepSeek-R1, Qwen3): <think>...</think>
    ThinkingPattern(
        name="xml_think",
        start_marker="<think>",
        end_marker="</think>",
        strip_end_marker=True,
    ),
    # Markdown fence: ```thinking\n...\n```
    ThinkingPattern(
        name="markdown_fence",
        start_marker="```thinking",
        end_marker="```",
        strip_end_marker=True,
    ),
    # Bare closing tag (no opening): ...thinking text...</think>
    ThinkingPattern(
        name="bare_closing_tag",
        start_marker="",
        end_marker="</think>",
        strip_end_marker=True,
    ),
]

__all__ = ["THINKING_PATTERNS", "ThinkingPattern"]
