"""Data types and prompt templates for the Plan-and-Execute strategy.

Contains the ``PlanStep`` dataclass, ``PlanStepStatus`` enum, and all
prompt-template constants used across the planning and execution phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class PlanStepStatus(StrEnum):
    """Status of a plan step."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in the agent's plan."""

    number: int
    """Step number (1-based)."""

    description: str
    """What this step should accomplish."""

    tool_name: str | None = None
    """Tool to use (None if this is an LLM reasoning step)."""

    tool_args: dict[str, Any] | None = None
    """Arguments for the tool call."""

    result: str | None = None
    """Result after execution."""

    status: PlanStepStatus = PlanStepStatus.PENDING
    """Status of this step."""


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PLANNING_PROMPT = """
You are a Plan-and-Execute agent. You solve complex tasks by creating a plan first,
then executing each step.

## Phase: PLANNING

Create a numbered plan to accomplish the user's task. Each step should be ONE
atomic action — either a tool call or a reasoning step.

## Output Format

```
PLAN:
1. [TOOL:tool_name] Description of what to do with the tool
2. [REASON] Analyze the results from step 1
3. [TOOL:another_tool] Use another tool with the analysis
4. [REASON] Synthesize the final answer
```

## Rules
- Prefix tool steps with [TOOL:tool_name] where tool_name matches an available tool.
- Prefix reasoning steps with [REASON].
- Keep the plan concise (max {max_steps} steps).
- Each step should clearly state its purpose.

## Available Tools
{tool_descriptions}
"""

EXECUTION_PROMPT = """You are executing step {step_number} of your plan.

## Current Plan
{plan_text}

## Completed Steps
{completed_steps}

## Current Step
Step {step_number}: {step_description}

Execute this step. If it's a tool call, provide:
ACTION: tool_name
ACTION_INPUT: {{"arg": "value"}}

If it's a reasoning step, provide your analysis and conclude with:
STEP_RESULT: <your result for this step>
"""

REPLAN_PROMPT = """Step {failed_step} failed. Exception details are withheld for privacy.

## Original Plan
{plan_text}

## Completed Steps
{completed_steps}

## Remaining Steps
{remaining_steps}

Create a revised plan for the remaining steps, accounting for the failure.
Use the same format:
PLAN:
1. [TOOL:tool_name] or [REASON] Description
"""

SYNTHESIS_PROMPT = """You have completed all steps. Synthesize a final answer.

## Original Task
{original_task}

## Completed Steps and Results
{all_results}

Provide a clear, comprehensive final answer based on the results above.
FINAL_ANSWER: <your synthesized answer>
"""


__all__ = [
    "EXECUTION_PROMPT",
    "PLANNING_PROMPT",
    "REPLAN_PROMPT",
    "SYNTHESIS_PROMPT",
    "PlanStep",
    "PlanStepStatus",
]
