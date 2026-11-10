"""Mid-loop guard hook: tool observations are checked at the OBSERVE boundary (D3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from quadkit.result import Ok


class MockObservationPipeline:
    """Returns block/redact/allow per call; can also raise."""

    def __init__(
        self,
        *,
        blocked: bool = False,
        final_content: str | None = None,
        raise_on_check: BaseException | None = None,
    ) -> None:
        self._blocked = blocked
        self._final = final_content
        self._raise_on_check = raise_on_check
        self.calls: list[dict[str, Any]] = []

    async def check_input(self, content: str, **kwargs: Any) -> Any:
        self.calls.append({"content": content, "kwargs": kwargs})
        if self._raise_on_check is not None:
            raise self._raise_on_check
        if self._blocked:
            agg = SimpleNamespace(
                blocked=True,
                blocking_result=SimpleNamespace(reason="blocked-tool-output"),
            )
        else:
            agg = SimpleNamespace(
                blocked=False,
                final_content=self._final if self._final is not None else content,
            )
        return Ok(agg)


@pytest.mark.asyncio
async def test_guard_observation_redacts() -> None:
    from quadkit.ai.agents.strategies.guard_hook import guard_observation

    pipeline = MockObservationPipeline(final_content="[REDACTED]")
    out = await guard_observation(pipeline, "raw tool output", tool_name="ls")
    assert out == "[REDACTED]"
    assert pipeline.calls[0]["kwargs"]["metadata"] == {
        "source": "tool_observation",
        "tool_name": "ls",
    }


@pytest.mark.asyncio
async def test_guard_observation_blocks() -> None:
    from quadkit.ai.agents.strategies.guard_hook import (
        ToolObservationBlockedError,
        guard_observation,
    )

    pipeline = MockObservationPipeline(blocked=True)
    with pytest.raises(ToolObservationBlockedError, match="Tool output blocked") as exc:
        await guard_observation(pipeline, "evil output", tool_name="web_fetch")
    assert "blocked-tool-output" not in str(exc.value)


@pytest.mark.asyncio
async def test_guard_observation_fails_closed_on_infra_error() -> None:
    from quadkit.ai.agents.strategies.guard_hook import (
        ToolObservationGuardError,
        guard_observation,
    )

    secret = "GUARD_FAILURE_SENTINEL"
    pipeline = MockObservationPipeline(raise_on_check=RuntimeError(secret))
    with pytest.raises(ToolObservationGuardError) as exc:
        await guard_observation(pipeline, "payload", tool_name="x")
    assert secret not in str(exc.value)
    assert exc.value.details == {"error_type": "RuntimeError"}
    assert exc.value.__cause__ is None


@pytest.mark.asyncio
async def test_guard_observation_noop_without_pipeline() -> None:
    from quadkit.ai.agents.strategies.guard_hook import guard_observation

    assert await guard_observation(None, "anything", tool_name="x") == "anything"


@pytest.mark.asyncio
async def test_guard_observation_redact_to_empty_fails_closed() -> None:
    """Redacting to empty must not fall back to the raw content."""

    from quadkit.ai.agents.strategies.guard_hook import guard_observation

    pipeline = MockObservationPipeline(final_content="")
    out = await guard_observation(pipeline, "raw tool output", tool_name="ls")
    assert out == ""
