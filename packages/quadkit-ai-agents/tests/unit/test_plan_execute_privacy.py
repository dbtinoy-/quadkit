"""Privacy regression tests for Plan-and-Execute failure handling."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.agents.strategies.plan_execute_executor import replan, run_tool
from quadkit.ai.agents.strategies.plan_execute_types import PlanStep, PlanStepStatus

pytestmark = pytest.mark.asyncio


class _Completion:
    content = ""


class _Result:
    @staticmethod
    def is_ok() -> bool:
        return True

    @staticmethod
    def unwrap() -> _Completion:
        return _Completion()


class _CapturingLLM:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def complete(self, messages: list[Any]) -> _Result:
        self.messages = messages
        return _Result()


async def test_tool_failure_record_omits_private_details() -> None:
    private_tool_name = "private-internal-tool-tenant-42"
    private_error = "api_key=sk-private /srv/tenant-42/secrets.json"

    class _FailingTool:
        async def execute(self) -> None:
            raise RuntimeError(private_error)

    failure = await run_tool(
        private_tool_name,
        {},
        {private_tool_name: _FailingTool()},
        timeout=1.0,
    )
    unknown = await run_tool(private_tool_name, {}, {}, timeout=1.0)

    assert failure.error == "Tool execution failed (RuntimeError)"
    assert unknown.error == "Unknown tool"
    for record in (failure, unknown):
        assert private_tool_name not in (record.error or "")
        assert private_error not in (record.error or "")


async def test_replan_prompt_withholds_raw_error_details() -> None:
    llm = _CapturingLLM()
    private_error = "api_key=sk-private /srv/tenant-42/secrets.json"
    failed_step = PlanStep(
        number=1,
        description="Check the configured data source",
        status=PlanStepStatus.FAILED,
    )

    await replan(
        llm=llm,
        plan=[failed_step],
        failed_step=failed_step,
        error=private_error,
        original_message="Review the data source",
        history=[],
        system_prompt="",
        llm_timeout=1.0,
    )

    prompt = "\n".join(message.content for message in llm.messages)
    assert private_error not in prompt
    assert "sk-private" not in prompt
    assert "/srv/tenant-42/secrets.json" not in prompt
    assert "Exception details are withheld for privacy" in prompt
