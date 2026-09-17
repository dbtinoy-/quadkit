"""Convention followed: **Service pattern** — the outbound integration
lives behind a small protocol; the provider binds the production client
(or a test fake) so handlers never import httpx or read secrets.

External integration seam for the AI Assistant demo. Quadkit ships no AI
client; this is the boundary where any OpenAI-compatible chat endpoint
plugs in. The fake used by tests implements the same protocol — no
network, no API key.
"""

from __future__ import annotations

from typing import Protocol

import httpx


class AssistantClient(Protocol):
    """Anything that can turn a chat transcript into an answer."""

    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class HttpAssistantClient:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        self._model = model

    async def complete(self, messages: list[dict[str, str]]) -> str:
        """POST the transcript and return the assistant message text."""
        response = await self._client.post(
            "/chat/completions", json={"model": self._model, "messages": messages}
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.aclose()


__all__ = ["AssistantClient", "HttpAssistantClient"]
