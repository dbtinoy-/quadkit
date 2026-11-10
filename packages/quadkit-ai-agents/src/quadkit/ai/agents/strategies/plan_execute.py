"""Plan and Execute strategy for agent reasoning.

Implements a two-phase reasoning approach:
    1. **PLAN** — The LLM creates a numbered step-by-step plan.
    2. **EXECUTE** — Each step is executed in order (tool call or LLM reasoning).
    3. **REPLAN** — On step failure, the LLM re-plans remaining steps.
    4. **SYNTHESIZE** — After execution, the LLM synthesizes a final answer.

This strategy excels at complex, multi-step tasks where the full plan
can be decomposed upfront. For tasks requiring reactive adaptation,
use ``ReActStrategy`` instead.

Reference:
    Wang et al., "Plan-and-Solve Prompting" (2023)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from quadkit.ai.agents.strategies.base import AbstractStrategy
from quadkit.ai.agents.strategies.plan_execute_executor import (
    call_llm,
    execute_reasoning_step,
    execute_tool_step,
    replan,
    run_tool,
    synthesize,
)
from quadkit.ai.agents.strategies.plan_execute_planner import (
    extract_final_answer,
    extract_step_result,
    format_completed_steps,
    format_plan,
    parse_plan,
)
from quadkit.ai.agents.strategies.plan_execute_synthesis import build_direct_response
from quadkit.ai.agents.strategies.plan_execute_types import (
    PLANNING_PROMPT,
    PlanStep,
    PlanStepStatus,
)
from quadkit.ai.agents.strategies.token_utils import TokenAccumulator
from quadkit.ai.agents.types import ReasoningStep, ToolExecutionRecord
from quadkit.contracts.ai.agents import AgentError, AgentResponse
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import ToolProtocol
    from quadkit.contracts.ai.llm import LLMClientProtocol

logger = get_logger(__name__)


class PlanAndExecuteStrategy(AbstractStrategy):
    """Plan and Execute reasoning strategy.

    Decomposes complex tasks into explicit plans, executes each step
    sequentially, and synthesizes the results into a final answer.

    This strategy is best for:
    - Multi-step research tasks
    - Tasks requiring ordered operations
    - Complex queries that benefit from explicit decomposition

    Example::

        strategy = PlanAndExecuteStrategy(max_steps=8, max_replans=2)
        result = await strategy.execute(
            message="Compare the revenue of Apple and Google",
            tools=[search_tool, calculator_tool],
            history=[],
            llm=llm_client,
        )
    """

    def __init__(
        self,
        max_steps: int = 10,
        max_replans: int = 2,
        tool_timeout: float = 30.0,
        observation_max_chars: int = 10_000,
        llm_timeout: float = 120.0,
    ) -> None:
        """Initialize the Plan and Execute strategy.

        Args:
            max_steps: Maximum number of plan steps.
            max_replans: Maximum replanning attempts on step failure.
            tool_timeout: Per-tool execution timeout in seconds.
            observation_max_chars: Max characters for tool output before truncation.
            llm_timeout: Per-LLM-call timeout in seconds.
        """
        self.max_steps = max_steps
        self.max_replans = max_replans
        self.tool_timeout = tool_timeout
        self.observation_max_chars = observation_max_chars
        self.llm_timeout = llm_timeout

    async def execute(
        self,
        message: str,
        tools: list[ToolProtocol],
        history: list[dict[str, Any]],
        llm: LLMClientProtocol,
        **kwargs: Any,
    ) -> Result[AgentResponse, AgentError]:
        """Execute the Plan-and-Execute reasoning loop.

        Args:
            message: The user's input message.
            tools: Tools available to the agent.
            history: Conversation history as list of message dicts.
            llm: LLM client implementing ``LLMClientProtocol``.
            **kwargs: Additional parameters (system_prompt, etc.).

        Returns:
            ``Ok(AgentResponse)`` with the final synthesized answer and
            full reasoning trace. ``Err(AgentError)`` on failure.
        """
        system_prompt: str = kwargs.get("system_prompt", "")
        guard_pipeline = kwargs.get("guard_pipeline")
        steps: list[ReasoningStep] = []
        tool_calls: list[ToolExecutionRecord] = []
        usage = TokenAccumulator()
        start_time = time.monotonic()

        tool_map: dict[str, ToolProtocol] = {t.name: t for t in tools}
        tool_descriptions = "\n".join(f"- **{t.name}**: {t.description}" for t in tools)

        # ---- PHASE 1: PLANNING ----
        planning_prompt = PLANNING_PROMPT.format(
            max_steps=self.max_steps,
            tool_descriptions=tool_descriptions or "(no tools available)",
        )
        plan_text = await self._call_llm(
            llm,
            message,
            history,
            system_prompt + planning_prompt,
            usage=usage,
        )
        if plan_text is None:
            return Err(AgentError("LLM returned empty response during planning phase"))

        plan = self._parse_plan(plan_text)
        if not plan:
            # No structured plan — fall back to direct synthesis
            return build_direct_response(
                initial_response=plan_text,
                steps=steps,
                tool_calls=tool_calls,
                start_time=start_time,
                usage=usage,
            )

        steps.append(
            ReasoningStep(
                step_number=0,
                thought=f"Created plan with {len(plan)} steps",
                action="plan",
                observation=plan_text,
            )
        )

        logger.info(
            "plan_execute_plan_created",
            step_count=len(plan),
            tool_steps=sum(1 for s in plan if s.tool_name),
        )

        # ---- PHASE 2: EXECUTION ----
        replan_count = 0

        for plan_step in plan:
            if plan_step.status == PlanStepStatus.SKIPPED:
                continue

            if plan_step.tool_name and plan_step.tool_name in tool_map:
                # Tool execution step
                step_result, tool_record = await self._execute_tool_step(
                    llm,
                    plan_step,
                    plan,
                    tool_map,
                    message,
                    history,
                    system_prompt,
                    usage=usage,
                    guard_pipeline=guard_pipeline,
                )
                if tool_record:
                    tool_calls.append(tool_record)

                steps.append(
                    ReasoningStep(
                        step_number=plan_step.number,
                        thought=f"Executing: {plan_step.description}",
                        action=plan_step.tool_name,
                        tool_call=tool_record,
                        observation=step_result,
                    )
                )

                if (
                    plan_step.status == PlanStepStatus.FAILED
                    and replan_count < self.max_replans
                ):
                    # ---- PHASE 3: REPLAN ----
                    replan_count += 1
                    new_plan = await self._replan(
                        llm,
                        plan,
                        plan_step,
                        step_result,
                        message,
                        history,
                        system_prompt,
                        usage=usage,
                    )
                    if new_plan:
                        # Replace remaining steps
                        for old_step in plan:
                            if old_step.number > plan_step.number:
                                old_step.status = PlanStepStatus.SKIPPED
                        plan.extend(new_plan)
                        steps.append(
                            ReasoningStep(
                                step_number=plan_step.number,
                                thought=f"Replanning after failure (attempt {replan_count})",
                                action="replan",
                                observation=f"Created {len(new_plan)} new steps",
                            )
                        )
                    continue
            else:
                # LLM reasoning step
                step_result = await self._execute_reasoning_step(
                    llm,
                    plan_step,
                    plan,
                    message,
                    history,
                    system_prompt,
                    usage=usage,
                    guard_pipeline=guard_pipeline,
                )

                steps.append(
                    ReasoningStep(
                        step_number=plan_step.number,
                        thought=f"Reasoning: {plan_step.description}",
                        action="reason",
                        observation=step_result,
                    )
                )

            plan_step.result = step_result
            plan_step.status = PlanStepStatus.COMPLETED

        # ---- PHASE 4: SYNTHESIS ----
        final_answer = await self._synthesize(
            llm,
            message,
            plan,
            history,
            system_prompt,
            usage=usage,
        )

        elapsed = (time.monotonic() - start_time) * 1000
        logger.info(
            "plan_execute_complete",
            steps=len(steps),
            tool_calls=len(tool_calls),
            replans=replan_count,
            duration_ms=round(elapsed, 2),
        )

        return Ok(
            AgentResponse(
                message=final_answer,
                steps=steps,
                tool_calls=tool_calls,
                total_tokens=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_ms=elapsed,
                metadata={
                    "strategy": "plan_and_execute",
                    "plan_steps": len(plan),
                    "replans": replan_count,
                },
            )
        )

    # ------------------------------------------------------------------
    # Plan Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_plan(text: str) -> list[PlanStep]:
        """Parse a numbered plan from LLM output."""
        return parse_plan(text)

    # ------------------------------------------------------------------
    # Step Execution
    # ------------------------------------------------------------------

    async def _execute_tool_step(
        self,
        llm: LLMClientProtocol,
        plan_step: PlanStep,
        plan: list[PlanStep],
        tool_map: dict[str, ToolProtocol],
        original_message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        usage: TokenAccumulator | None = None,
        guard_pipeline: Any = None,
    ) -> tuple[str, ToolExecutionRecord | None]:
        """Execute a tool-based plan step."""
        return await execute_tool_step(
            llm=llm,
            plan_step=plan_step,
            plan=plan,
            tool_map=tool_map,
            original_message=original_message,
            history=history,
            system_prompt=system_prompt,
            tool_timeout=self.tool_timeout,
            llm_timeout=self.llm_timeout,
            observation_max_chars=self.observation_max_chars,
            usage=usage,
            guard_pipeline=guard_pipeline,
        )

    async def _execute_reasoning_step(
        self,
        llm: LLMClientProtocol,
        plan_step: PlanStep,
        plan: list[PlanStep],
        original_message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        usage: TokenAccumulator | None = None,
        guard_pipeline: Any = None,
    ) -> str:
        """Execute a reasoning-only plan step via LLM."""
        return await execute_reasoning_step(
            llm=llm,
            plan_step=plan_step,
            plan=plan,
            original_message=original_message,
            history=history,
            system_prompt=system_prompt,
            llm_timeout=self.llm_timeout,
            observation_max_chars=self.observation_max_chars,
            usage=usage,
            guard_pipeline=guard_pipeline,
        )

    # ------------------------------------------------------------------
    # Replanning
    # ------------------------------------------------------------------

    async def _replan(
        self,
        llm: LLMClientProtocol,
        plan: list[PlanStep],
        failed_step: PlanStep,
        error: str,
        original_message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        usage: TokenAccumulator | None = None,
    ) -> list[PlanStep]:
        """Ask LLM to replan after a step failure."""
        return await replan(
            llm=llm,
            plan=plan,
            failed_step=failed_step,
            error=error,
            original_message=original_message,
            history=history,
            system_prompt=system_prompt,
            llm_timeout=self.llm_timeout,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        llm: LLMClientProtocol,
        original_message: str,
        plan: list[PlanStep],
        history: list[dict[str, Any]],
        system_prompt: str,
        usage: TokenAccumulator | None = None,
    ) -> str:
        """Synthesize final answer from all completed step results."""
        return await synthesize(
            llm=llm,
            original_message=original_message,
            plan=plan,
            history=history,
            system_prompt=system_prompt,
            llm_timeout=self.llm_timeout,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    async def _run_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_map: dict[str, ToolProtocol],
    ) -> ToolExecutionRecord:
        """Execute a tool with timeout and error recovery."""
        return await run_tool(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_map=tool_map,
            timeout=self.tool_timeout,
        )

    # ------------------------------------------------------------------
    # LLM Interaction
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        llm: LLMClientProtocol,
        original_message: str,
        history: list[dict[str, Any]],
        prompt: str,
        usage: TokenAccumulator | None = None,
    ) -> str | None:
        """Call the LLM and return text content, or ``None`` on failure."""
        from quadkit.ai.agents.strategies.parsing import build_chat_messages_from_dict

        messages = build_chat_messages_from_dict(original_message, history, prompt)
        return await call_llm(llm, messages, timeout=self.llm_timeout, usage=usage)

    # ------------------------------------------------------------------
    # Parsing Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_step_result(text: str) -> str | None:
        """Extract STEP_RESULT from LLM response."""
        return extract_step_result(text)

    @staticmethod
    def _extract_final_answer(text: str) -> str:
        """Extract FINAL_ANSWER marker, falling back to raw text."""
        return extract_final_answer(text)

    # ------------------------------------------------------------------
    # Message / Plan Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_plan(plan: list[PlanStep]) -> str:
        """Format plan steps as numbered list."""
        return format_plan(plan)

    @staticmethod
    def _format_completed_steps(plan: list[PlanStep]) -> str:
        """Format completed steps with their results."""
        return format_completed_steps(plan)


__all__ = ["PlanAndExecuteStrategy", "PlanStep", "PlanStepStatus"]
