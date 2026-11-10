"""Deterministic scenario scripts driving the scripted LLM.

The ReAct strategy parses ``THOUGHT / ACTION / ACTION_INPUT`` markers
from the LLM's completion text and terminates on ``FINAL_ANSWER``.
Each scenario is a list of pre-written completions — one per reasoning
step — that the ``ScriptedLLM`` pops from a FIFO queue.

This makes the agent loop run for real (tools get called, the strategy
parser drives the loop) while model output stays byte-stable across
runs — perfect for testing and demos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.primitives import Registry

# --- Scenario scripts ------------------------------------------------

HAPPY_SCRIPT: list[str] = [
    (
        "THOUGHT: I need the order details first.\n"
        "ACTION: lookup_order\n"
        'ACTION_INPUT: {"order_id": "A-100"}'
    ),
    (
        "THOUGHT: The order shipped via FastShip.\n"
        "FINAL_ANSWER: Order A-100 shipped via FastShip, tracking FS123456789."
    ),
]

MULTI_TOOL_SCRIPT: list[str] = [
    (
        "THOUGHT: Look up the order.\n"
        "ACTION: lookup_order\n"
        'ACTION_INPUT: {"order_id": "A-102"}'
    ),
    (
        "THOUGHT: Delivered recently; compute the refund.\n"
        "ACTION: calculate_refund\n"
        'ACTION_INPUT: {"order_total": 74.5, "days_since_delivery": 10}'
    ),
    (
        "THOUGHT: Half refund applies.\n"
        "FINAL_ANSWER: You are eligible for a $37.25 half refund."
    ),
]

FAILURE_SCRIPT: list[str] = [
    "THOUGHT: Try the wrong tool.\nACTION: teleport_order\nACTION_INPUT: {}",
    (
        "THOUGHT: That tool does not exist; answer directly.\n"
        "FINAL_ANSWER: I could not complete that request."
    ),
]


# --- Scenario registry ------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One deterministic demo act: key, display label, scripted turns."""

    key: str
    label: str
    script: list[str] = field(default_factory=list)


def _build_scenarios() -> Registry[str, Scenario]:
    """Framework Registry keyed by scenario id.

    The controller looks up scenarios by key from the POST body,
    loads the script into the ``ScriptedLLM`` FIFO, then calls
    ``SupportAgent.ask()``.
    """
    registry: Registry[str, Scenario] = Registry()
    registry.register("happy", Scenario("happy", "Happy path", HAPPY_SCRIPT))
    registry.register(
        "multi_tool", Scenario("multi_tool", "Multi-tool", MULTI_TOOL_SCRIPT)
    )
    registry.register("failure", Scenario("failure", "Failure", FAILURE_SCRIPT))
    return registry


SCENARIOS: Registry[str, Scenario] = _build_scenarios()
