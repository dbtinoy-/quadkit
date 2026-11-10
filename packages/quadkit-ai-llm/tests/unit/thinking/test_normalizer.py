"""Tests for thinking text normalizer."""
from __future__ import annotations

import pytest

from quadkit.ai.llm.thinking import normalize_thinking_text


class TestNormalizeThinkingText:
    def test_xml_think_tags(self) -> None:
        text = "<think>This is my reasoning</think>Final answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "Final answer"
        assert thinking == "This is my reasoning"

    def test_qwen3_pipe_delimited(self) -> None:
        text = "<|think|>Reasoning here</|think|>The response"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The response"
        assert thinking == "Reasoning here"

    def test_gemma4_channel_format_canonical(self) -> None:
        """Official Gemma-4 format: <|channel>thought...<channel|>response."""
        text = "<|channel>thought\nThis is my thinking\n<channel|>\nThe answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The answer"
        assert thinking == "This is my thinking"

    def test_gemma4_channel_ghost_empty_thinking(self) -> None:
        """Gemma-4 26B/31B with thinking OFF emits an empty ghost block."""
        text = '<|channel>thought\n<channel|>\n{"urgency": "low"}'
        clean, thinking = normalize_thinking_text(text)
        assert clean == '{"urgency": "low"}'
        assert thinking is None  # empty thinking block → None

    def test_gemma4_channel_gguf_response_variant(self) -> None:
        """GGUF chat template variant using <|channel>response separator."""
        text = "<|channel>thought\nThinking...\n<|channel>response\nResult"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "Result"
        assert thinking == "Thinking..."

    def test_gemma4_channel_gguf_output_variant(self) -> None:
        """GGUF chat template variant using <|channel>output separator."""
        text = "<|channel>thought\nThinking...\n<|channel>output\nResult"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "Result"
        assert thinking == "Thinking..."

    def test_markdown_thinking_fence(self) -> None:
        text = "```thinking\nMy reasoning\n```\nThe final answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The final answer"
        assert thinking == "My reasoning"

    def test_bare_closing_think_tag(self) -> None:
        text = "Some reasoning without opening tag</think>The answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The answer"
        assert thinking == "Some reasoning without opening tag"

    def test_clean_text_passthrough(self) -> None:
        text = "This is just a normal response with no thinking tags"
        clean, thinking = normalize_thinking_text(text)
        assert clean == text
        assert thinking is None

    def test_json_content_not_mangled(self) -> None:
        text = '{"key": "value", "nested": {"a": 1}}'
        clean, thinking = normalize_thinking_text(text)
        assert clean == text
        assert thinking is None

    def test_multiline_thinking(self) -> None:
        text = "<think>\nLine 1 of reasoning\nLine 2 of reasoning\n</think>\nThe answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The answer"
        assert "Line 1 of reasoning" in thinking
        assert "Line 2 of reasoning" in thinking

    def test_thinking_with_json_content(self) -> None:
        text = '<think>Let me think</think>{"result": "ok"}'
        clean, thinking = normalize_thinking_text(text)
        assert clean == '{"result": "ok"}'
        assert thinking == "Let me think"

    def test_empty_thinking(self) -> None:
        text = "<think></think>The answer"
        clean, thinking = normalize_thinking_text(text)
        assert clean == "The answer"
        assert thinking is None  # empty thinking -> None

    def test_gemma4_bare_no_separator(self) -> None:
        """Gemma-4 via LM Studio: thinking block with no <|channel>response separator."""
        text = '<|channel>thought\nI need to analyze this turtle carefully.\n{"urgency": "low"}'
        clean, thinking = normalize_thinking_text(text)
        assert clean == '{"urgency": "low"}'
        assert "turtle" in thinking

    def test_gemma4_bare_no_separator_long_thinking(self) -> None:
        """Fallback path handles long thinking blocks that exceed log preview size."""
        long_thought = "x " * 300
        text = f"<|channel>thought\n{long_thought}\n{{\"urgency\": \"high\"}}"
        clean, thinking = normalize_thinking_text(text)
        assert clean == '{"urgency": "high"}'
        assert len(thinking) > 100  # thinking text was captured
