"""LLM workflow node."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from quadkit.logging import get_logger, safe_error_type
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

logger = get_logger(__name__)

_TEMPLATE_VAR_RE = re.compile(r"\{(\w+)\}")


@dataclass
class _Msg:
    """Minimal chat message satisfying ChatMessageProtocol duck-type."""

    role: str
    content: str


def _render(template: str, state: dict[str, Any]) -> str:
    """Substitute {key} placeholders in template from state."""

    def replacer(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(state.get(key, m.group(0)))

    return _TEMPLATE_VAR_RE.sub(replacer, template)


class LLMNode(AbstractWorkflowNode):
    """Workflow node that makes a raw LLM call.

    Args:
        name: Node identifier.
        llm: LLMClientProtocol implementation.
        prompt_template: Prompt string with optional {key} variables.
        system_prompt: Optional system message prepended to the call.
        output_key: State key where the completion is stored.
        model: Optional model override.
        temperature: Sampling temperature override.
        max_tokens: Max output token override.
    """

    def __init__(
        self,
        name: str,
        *,
        llm: Any,
        prompt_template: str = "{input}",
        system_prompt: str = "",
        output_key: str = "output",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(name, NodeType.LLM)
        self._llm = llm
        self._prompt_template = prompt_template
        self._system_prompt = system_prompt
        self._output_key = output_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Render the prompt from state and call the LLM.

        Args:
            state: Current workflow state used for prompt substitution.

        Returns:
            Dict with {output_key: completion_text}.
        """
        prompt = _render(self._prompt_template, state)
        messages: list[Any] = []
        if self._system_prompt:
            messages.append(_Msg(role="system", content=self._system_prompt))
        messages.append(_Msg(role="user", content=prompt))

        kwargs: dict[str, Any] = {}
        if self._model:
            kwargs["model"] = self._model
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens

        try:
            result = await self._llm.complete(messages, **kwargs)
        except Exception as exc:  # noqa: BLE001 — node degrades, workflow continues
            logger.warning(
                "llm_node_error",
                error_type=safe_error_type(exc),
            )
            return {self._output_key: "LLM request failed."}

        if result.is_err():
            error = result.unwrap_err()
            logger.warning(
                "llm_node_llm_err",
                error_type=safe_error_type(error),
            )
            return {self._output_key: "LLM request failed."}

        text = result.unwrap().content
        logger.debug("llm_node_done", output_len=len(text))
        return {self._output_key: text}


__all__ = ["LLMNode"]
