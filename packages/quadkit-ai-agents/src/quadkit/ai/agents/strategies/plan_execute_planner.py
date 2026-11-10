"""Synchronous planning helpers for the Plan-and-Execute strategy.

Provides pure-function utilities for:
- Parsing a numbered plan from raw LLM text.
- Formatting a plan and its completed steps for LLM prompts.
- Extracting structured markers (``STEP_RESULT:``, ``FINAL_ANSWER:``) from
  LLM responses.

All functions in this module are synchronous and side-effect free — they
operate on plain data types and do not call the LLM or any I/O.
"""

from __future__ import annotations

import re

from quadkit.ai.agents.strategies.plan_execute_types import PlanStep, PlanStepStatus

# ---------------------------------------------------------------------------
# Plan parsing
# ---------------------------------------------------------------------------


def parse_plan(text: str) -> list[PlanStep]:
    """Parse a numbered plan from LLM output.

    Expected format::

        PLAN:
        1. [TOOL:search] Search for revenue data
        2. [REASON] Analyze the search results

    Returns at most 10 steps (hard cap for safety).
    """
    plan: list[PlanStep] = []
    in_plan = False

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("PLAN:"):
            in_plan = True
            continue

        if not in_plan:
            continue

        # Match numbered steps: "1. [TOOL:name] description" or "1. [REASON] description"
        match = re.match(
            r"(\d+)\.\s*(?:\[TOOL:(\w+)\])?\s*(?:\[REASON\])?\s*(.*)",
            stripped,
        )
        if match:
            step_num = int(match.group(1))
            tool_name = match.group(2)
            description = match.group(3).strip()
            plan.append(
                PlanStep(
                    number=step_num,
                    description=description,
                    tool_name=tool_name,
                )
            )
        elif stripped and plan:
            # Non-matching line after plan started — plan is done
            if not stripped[0].isdigit():
                break

    return plan[:10]  # Cap at max steps for safety


# ---------------------------------------------------------------------------
# Plan formatting
# ---------------------------------------------------------------------------


def format_plan(plan: list[PlanStep]) -> str:
    """Format plan steps as a numbered list for LLM prompts."""
    lines = []
    for step in plan:
        prefix = f"[TOOL:{step.tool_name}]" if step.tool_name else "[REASON]"
        status = (
            f" ({step.status.value if isinstance(step.status, PlanStepStatus) else str(step.status)})"
            if step.status != PlanStepStatus.PENDING
            else ""
        )
        lines.append(f"{step.number}. {prefix} {step.description}{status}")
    return "\n".join(lines)


def format_completed_steps(plan: list[PlanStep]) -> str:
    """Format completed steps with their results for LLM prompts."""
    completed = [s for s in plan if s.status == PlanStepStatus.COMPLETED and s.result]
    if not completed:
        return ""
    return "\n".join(
        f"Step {s.number}: {s.description}\n  → {s.result}" for s in completed
    )


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------


def extract_step_result(text: str) -> str | None:
    """Extract the ``STEP_RESULT:`` marker from an LLM response.

    Returns the text following the marker, or ``None`` if not present.
    """
    marker = "STEP_RESULT:"
    idx = text.upper().find(marker)
    if idx == -1:
        return None
    return text[idx + len(marker) :].strip()


def extract_final_answer(text: str) -> str:
    """Extract the ``FINAL_ANSWER:`` marker, falling back to raw text.

    Returns the text following the marker if present, otherwise the full
    stripped text.
    """
    marker = "FINAL_ANSWER:"
    idx = text.upper().find(marker)
    if idx == -1:
        return text.strip()
    return text[idx + len(marker) :].strip()


__all__ = [
    "extract_final_answer",
    "extract_step_result",
    "format_completed_steps",
    "format_plan",
    "parse_plan",
]
