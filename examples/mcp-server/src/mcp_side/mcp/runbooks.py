"""Convention followed: **MCP controller** — group related ``@tool``,
``@resource``, and ``@prompt`` capabilities on a ``quadkit-ai-mcp``
``MCPController`` subclass with typed parameters so JSON Schemas are
generated automatically.
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp import MCPController, prompt, resource, tool

_INCIDENTS: dict[str, dict[str, str]] = {
    "INC-101": {
        "id": "INC-101",
        "severity": "sev1",
        "service": "checkout-api",
        "summary": "Elevated p99 latency on payment capture",
        "runbook": "runbook://payments",
    },
    "INC-102": {
        "id": "INC-102",
        "severity": "sev2",
        "service": "webhook-dispatcher",
        "summary": "Retry backlog growing for partner deliveries",
        "runbook": "runbook://webhooks",
    },
}

_RUNBOOKS: dict[str, str] = {
    "payments": (
        "1. Verify upstream acquirer status.\n"
        "2. Check connection pool saturation.\n"
        "3. Shift traffic to secondary region if error rate > 2%."
    ),
    "webhooks": (
        "1. Inspect dead-letter queue depth.\n"
        "2. Confirm partner TLS endpoint health.\n"
        "3. Drain queued retries with bounded concurrency."
    ),
}


class AllowBridgeAuthorizer:
    """Explicit ``MCPAuthorizerProtocol`` allowing initialized bridge clients.

    ``MCPServer`` fails closed by default when no authorizer is bound; binding
    an explicit authorizer keeps authorization visible and auditable.
    """

    def __init__(self, expected_client: str = "mcp-bridge") -> None:
        self._expected_client = expected_client

    async def authorize(
        self,
        *,
        method: str,
        params: dict[str, Any],
        client_info: dict[str, Any],
    ) -> bool:
        _ = (method, params)
        return client_info.get("name") == self._expected_client


class RunbookMCPController(MCPController):
    """Expose incident lookup tools, runbook resources, and triage prompts."""

    @tool("lookup_incident", description="Fetch an incident record by ticket ID")
    async def lookup_incident(self, incident_id: str) -> dict[str, Any]:
        record = _INCIDENTS.get(incident_id.upper())
        if record is None:
            return {"found": False, "incident_id": incident_id}
        return {"found": True, "incident": record}

    @tool("list_incidents", description="List open incidents filtered by severity")
    async def list_incidents(self, severity: str = "") -> list[dict[str, str]]:
        if not severity:
            return list(_INCIDENTS.values())
        wanted = severity.lower()
        return [item for item in _INCIDENTS.values() if item["severity"] == wanted]

    @resource("runbook://{topic}", description="Read an operational runbook by topic")
    async def read_runbook(self, topic: str) -> dict[str, str]:
        body = _RUNBOOKS.get(topic.lower(), "No runbook registered for this topic.")
        return {"uri": f"runbook://{topic}", "topic": topic, "steps": body}

    @prompt("triage_incident", description="Build a structured incident triage prompt")
    async def triage_incident(self, incident_id: str) -> list[dict[str, str]]:
        record = _INCIDENTS.get(incident_id.upper(), {"summary": "Unknown incident"})
        return [
            {
                "role": "user",
                "content": (
                    f"Triage incident {incident_id}: {record['summary']}. "
                    "Summarize blast radius, immediate mitigation, and next check."
                ),
            }
        ]


__all__ = ["AllowBridgeAuthorizer", "RunbookMCPController"]
