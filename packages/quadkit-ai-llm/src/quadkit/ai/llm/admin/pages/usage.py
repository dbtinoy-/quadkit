from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent, Stat, StatContent
from quadkit.contracts.ai.llm import TokenCounterProtocol
from quadkit.contracts.ai.routing import InferenceLoggerProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class LlmUsagePage:
    """Usage statistics for /admin/ai/llm/usage."""

    def __init__(
        self,
        counter: TokenCounterProtocol | None = None,
        logger: InferenceLoggerProtocol | None = None,
    ) -> None:
        self._counter = counter
        self._logger = logger

    async def handle(self, request: Any) -> PageContent:
        if self._logger is None:
            return PageContent(
                title="Usage",
                body=EmptyContent(
                    title="Usage Data Unavailable",
                    message="No inference logger is configured. Usage statistics cannot be displayed.",
                    icon="bar-chart-2",
                ),
            )

        logs: list[Any] = []
        try:
            logs = await self._logger.get_recent(limit=500)
        except Exception:
            logs = []

        if not logs:
            return PageContent(
                title="Usage",
                body=EmptyContent(
                    title="No Usage Data",
                    message="No inference data has been recorded yet.",
                    icon="inbox",
                ),
            )

        total_prompt = 0
        total_completion = 0
        total_cost = 0.0
        success_count = 0
        for log in logs:
            if not log.succeeded or log.result is None:
                continue
            result = log.result
            total_prompt += getattr(result, "prompt_tokens", 0)
            total_completion += getattr(result, "completion_tokens", 0)
            total_cost += getattr(result, "cost", 0.0)
            success_count += 1

        total_tokens = total_prompt + total_completion

        return PageContent(
            title="Usage",
            body=StatContent(
                stats=(
                    Stat(
                        label="Total Tokens",
                        value=f"{total_tokens:,}",
                        icon="align-left",
                    ),
                    Stat(
                        label="Prompt Tokens",
                        value=f"{total_prompt:,}",
                        icon="corner-up-left",
                    ),
                    Stat(
                        label="Completion Tokens",
                        value=f"{total_completion:,}",
                        icon="corner-down-right",
                    ),
                    Stat(
                        label="Estimated Cost",
                        value=f"${total_cost:.4f}",
                        icon="dollar-sign",
                    ),
                )
            ),
        )
