"""DraftVerifyExecutor — draft-then-verify pattern using cheap and expensive models."""

from __future__ import annotations

import asyncio

from quadkit.contracts import (
    LLMClientProtocol,
)
from quadkit.contracts.ai.exceptions import LLMError
from quadkit.contracts.ai.llm import ChatMessage, Completion
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class DraftVerifyExecutor:
    """Draft-then-verify pattern using cheap + expensive model pair.

    Fires a cheap/fast model and an expensive/capable model in parallel.
    If the cheap model's draft passes verification, cancels the expensive
    model and returns the draft immediately. Otherwise waits for the
    expensive model's result.

    Opt-in strategy for scenarios where latency matters more than guaranteed
    quality on the first try.
    """

    def __init__(
        self,
        draft_client: LLMClientProtocol,
        verify_client: LLMClientProtocol,
        pro_client: LLMClientProtocol,
    ) -> None:
        """Initialize the DraftVerifyExecutor.

        Args:
            draft_client: Fast/cheap LLM client for draft generation.
            verify_client: Verifier LLM client (typically small/fast).
            pro_client: Slow/expensive LLM client for fallback.
        """
        self._draft = draft_client
        self._verify = verify_client
        self._pro = pro_client
        self._background_tasks: set[asyncio.Task] = set()

    async def execute(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Result[Completion, LLMError]:
        """Execute draft-then-verify pattern.

        1. Fire draft_client and pro_client in parallel.
        2. Await draft (faster).
        3. Verify draft with verify_client (yes/no).
        4. If verified: cancel pro_client, return draft.
        5. If not verified: await pro_client, return its result.

        Args:
            messages: Chat messages to send to both models.
            model: Optional model override (applied to pro_client only).
            temperature: Optional temperature override.
            max_tokens: Optional max_tokens override.

        Returns:
            Result containing Completion on success, LLMError on failure.
        """
        draft_task = asyncio.create_task(
            self._draft.complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        pro_task = asyncio.create_task(
            self._pro.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        self._background_tasks.add(draft_task)
        self._background_tasks.add(pro_task)
        draft_task.add_done_callback(self._background_tasks.discard)
        pro_task.add_done_callback(self._background_tasks.discard)

        draft_result = await draft_task
        if draft_result.is_ok():
            draft_completion = draft_result.unwrap()
        else:
            draft_error = draft_result.unwrap_err()
            pro_task.cancel()
            logger.warning(
                "draft_generation_failed",
                error_type=safe_error_type(draft_error),
            )
            return Err(
                LLMError(
                    "Draft LLM request failed",
                    details={"error_type": safe_error_type(draft_error)},
                ),
            )
        draft_text = draft_completion.content

        verify_messages = [
            *messages,
            ChatMessage(role="assistant", content=draft_text),
            ChatMessage(
                role="user",
                content=f"Is the following response correct and complete? Response: {draft_text[:200]}...",
            ),
        ]
        verify_result = await self._verify.complete(verify_messages, max_tokens=10)
        if verify_result.is_ok():
            verify_text = verify_result.unwrap().content.lower()
        else:
            verify_error = verify_result.unwrap_err()
            logger.warning(
                "draft_verify_failed",
                error_type=safe_error_type(verify_error),
            )
            verify_text = "invalid"

        rejected = any(
            w in verify_text for w in ["no", "not", "incorrect", "invalid", "wrong"]
        )
        accepted = any(w in verify_text for w in ["yes", "correct", "valid"])
        draft_accepted = accepted and not rejected

        if draft_accepted:
            pro_task.cancel()
            logger.info("draft_verify_accepted")
            return Ok(draft_completion)  # type: ignore[arg-type]

        logger.info("draft_verify_rejected")
        pro_result = await pro_task
        if pro_result.is_err():
            pro_error = pro_result.unwrap_err()
            logger.warning(
                "fallback_generation_failed",
                error_type=safe_error_type(pro_error),
            )
            return Err(
                LLMError(
                    "Fallback LLM request failed",
                    details={"error_type": safe_error_type(pro_error)},
                ),
            )
        return pro_result
