"""Tests for the scripted LLM boundary."""

from __future__ import annotations

import pytest

from quadkit.result import Ok

from support_agent.repository.scripted_llm import EmptyScriptError, ScriptedLLM


class TestScriptedLLM:
    @pytest.mark.asyncio
    async def test_pops_entries_in_fifo_order(self) -> None:
        llm = ScriptedLLM(["first", "second"])

        first = await llm.complete([{"role": "user", "content": "hi"}])
        second = await llm.complete([{"role": "user", "content": "hi"}])

        assert isinstance(first, Ok)
        assert first.unwrap().content == "first"
        assert second.unwrap().content == "second"
        assert llm.remaining == 0

    @pytest.mark.asyncio
    async def test_empty_queue_raises_empty_script_error(self) -> None:
        llm = ScriptedLLM([])

        with pytest.raises(EmptyScriptError):
            await llm.complete([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_load_replaces_script(self) -> None:
        llm = ScriptedLLM(["stale"])
        llm.load(["fresh"])
        result = await llm.complete([])

        assert result.unwrap().content == "fresh"

    @pytest.mark.asyncio
    async def test_completion_carries_deterministic_usage(self) -> None:
        llm = ScriptedLLM(["FINAL_ANSWER: y"])
        result = await llm.complete([])

        completion = result.unwrap()
        assert completion.usage.total_tokens == 36
        assert completion.model == "scripted"
