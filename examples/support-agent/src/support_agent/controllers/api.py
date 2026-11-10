"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON API for the support-agent console — no HTML lives here.

Handlers return ``Result`` values; the web pipeline renders ``Ok`` payloads
and maps ``Err`` errors to ProblemDetail responses via ``ResultResponseMapper``.

Routes:

- ``GET  /api/tools``   — list registered tools for the console sidebar
- ``POST /api/ask``     — run one scenario-scripted ReAct turn

The ask endpoint accepts ``{"question": "...", "scenario": "happy"}`` and
returns a traced response with steps, tool calls, token counts, and timing.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from quadkit.contracts.ai.agents import AgentError
from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, get, post
from support_agent.repository.scenarios import SCENARIOS
from support_agent.repository.scripted_llm import ScriptedLLM
from support_agent.services.support_service import (
    SupportAgent,
    build_support_agent,
)

# AgentError is not a DomainError, so the result bridge maps it to 500
# (server fault) by default — no per-app registration needed.


async def _body(request: Request) -> dict[str, Any]:
    """Parse the request body through the framework serializer."""
    raw = await request.body()
    if not raw:
        return {}
    parsed = json_loads(raw)
    return dict(parsed) if isinstance(parsed, dict) else {}


def _payload(response: Any) -> dict[str, Any]:
    """Flatten an AgentResponse into a JSON-safe dict for the console."""
    return {
        "answer": response.message,
        "steps": [
            {
                "step_number": step.step_number,
                "thought": step.thought,
                "action": step.action,
            }
            for step in response.steps
        ],
        "tool_calls": [
            {
                "tool_name": call.tool_name,
                "succeeded": call.succeeded,
                "error": call.error,
            }
            for call in response.tool_calls
        ],
        "total_tokens": response.total_tokens,
        "duration_ms": round(response.duration_ms, 1),
    }


class AgentApiController(Controller):
    """Endpoints consumed by the ui/static/app.js fetch client.

    The framework resolves this controller when a request matches its routes.
    All collaborators come via constructor injection — no service locator.
    """

    def __init__(self, scripted: ScriptedLLM, support: SupportAgent) -> None:
        self._scripted = scripted
        self._support = support

    @get("/api/tools")
    async def tools(self, request: Request) -> list[dict[str, str]]:
        """List registered tools for the console sidebar."""
        agent = build_support_agent()
        return [{"name": t.name, "description": t.description} for t in agent.tools]

    @post("/api/ask")
    async def ask(
        self,
        request: Request,
    ) -> Result[dict[str, Any], AgentError | NotFoundError | ValidationError]:
        """Run one scenario-scripted ReAct turn.

        Returns ``Ok(payload)`` on success, or ``Err`` mapped to 404/422/500
        by the framework's result bridge.
        """
        data = await _body(request)
        scenario_key = str(data.get("scenario", ""))
        scenario = SCENARIOS.get(scenario_key)
        if scenario is None:
            return Err(NotFoundError(f"unknown scenario: {scenario_key!r}"))

        question = str(data.get("question", "")).strip()
        if not question:
            return Err(ValidationError("question is required"))

        # Load the scripted completions for this scenario into the FIFO
        # queue — the ReAct strategy pops them one per reasoning step.
        self._scripted.load(scenario.script)
        inner = await self._support.ask(question)
        if inner.is_err():
            return Err(inner.unwrap_err())
        return Ok(_payload(inner.unwrap()))


__all__ = ["AgentApiController"]
