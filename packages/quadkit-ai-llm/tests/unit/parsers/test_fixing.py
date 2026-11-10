"""Regression tests for safe format-fixing parser errors."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.ai.llm.parsers.fixing import FormatFixingParser
from quadkit.ai.llm.structured.exceptions import ParseError


class _FailingParser:
    def __init__(self, message: str) -> None:
        self.message = message

    def parse(self, text: str) -> object:
        raise ParseError(self.message)


@pytest.mark.asyncio
async def test_parse_error_text_is_not_logged_returned_or_sent_to_fix_llm(
    capsys,
) -> None:
    secret = "FORMAT_FIXING_SECRET_SENTINEL"
    llm_client = AsyncMock()
    llm_client.complete.return_value = SimpleNamespace(content="still invalid")
    parser = FormatFixingParser(
        _FailingParser(secret),
        llm_client,
        retry_budget=1,
    )

    with pytest.raises(ParseError) as exc_info:
        await parser.parse("invalid model output")

    error = exc_info.value
    assert secret not in str(error)
    assert secret not in repr(error.to_dict())
    assert error.__cause__ is None
    sent_messages = llm_client.complete.call_args.kwargs["messages"]
    assert secret not in sent_messages[0]["content"]
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


@pytest.mark.asyncio
async def test_fix_call_exception_text_is_not_exposed(capsys) -> None:
    secret = "FORMAT_FIX_CALL_SECRET_SENTINEL"
    llm_client = AsyncMock()
    llm_client.complete.side_effect = RuntimeError(secret)
    parser = FormatFixingParser(
        _FailingParser("invalid format"),
        llm_client,
        retry_budget=1,
    )

    with pytest.raises(ParseError) as exc_info:
        await parser.parse("invalid model output")

    error = exc_info.value
    assert secret not in str(error)
    assert secret not in repr(error.to_dict())
    assert error.__cause__ is None
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
