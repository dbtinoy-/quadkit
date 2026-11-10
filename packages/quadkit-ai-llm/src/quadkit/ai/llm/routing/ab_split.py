from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from quadkit.contracts.ai.llm import LLMClientProtocol
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

__all__ = ["ABSplitConfig", "ABSplitStrategy"]


@dataclass(frozen=True)
class ABSplitConfig:
    """Configuration for A/B traffic splitting between two LLM providers.

    Attributes:
        control_key: Container key for the control (baseline) provider.
        treatment_key: Container key for the treatment (experimental) provider.
        treatment_percentage: 0–100, percentage of traffic to route to treatment.
        split_key_field: Request field used to deterministically assign traffic.
    """

    control_key: str
    treatment_key: str
    treatment_percentage: int = 10
    split_key_field: str = "user_id"

    def __post_init__(self) -> None:
        """Validate percentage range.

        Raises:
            ValueError: If treatment_percentage is not in [0, 100].
        """
        if not 0 <= self.treatment_percentage <= 100:
            raise ValueError(
                f"treatment_percentage must be 0-100, got {self.treatment_percentage}"
            )


class ABSplitStrategy:
    """Routes LLM requests between control and treatment providers using deterministic hashing.

    Uses MD5 hashing on the split key to ensure consistent assignment:
    the same user always gets the same variant for a given configuration.

    Args:
        config: A/B split configuration.
        control: The control (baseline) LLM provider.
        treatment: The treatment (experimental) LLM provider.
    """

    def __init__(
        self,
        config: ABSplitConfig,
        control: LLMClientProtocol,
        treatment: LLMClientProtocol,
    ) -> None:
        self._config = config
        self._control = control
        self._treatment = treatment

    def _should_use_treatment(self, request: Any) -> bool:
        """Deterministically assign request to control or treatment.

        Hashes ``split_key_field`` from the request (or ``str(request)`` as
        fallback) to a value in [0, 99], then compares against
        ``treatment_percentage``.

        Args:
            request: The model request (any object with a split_key_field attribute).

        Returns:
            True if request should go to treatment, False for control.
        """
        split_value = str(getattr(request, self._config.split_key_field, ""))
        if not split_value:
            return False

        hash_bytes = hashlib.md5(  # noqa: S324
            f"{split_value}:{self._config.treatment_key}".encode(),
            usedforsecurity=False,
        ).digest()
        bucket = int.from_bytes(hash_bytes[:4], "big") % 100
        return bucket < self._config.treatment_percentage

    async def route(self, request: Any) -> LLMClientProtocol:
        """Select the appropriate provider for this request.

        Args:
            request: The model request to route.

        Returns:
            Either the control or treatment LLM provider.
        """
        use_treatment = self._should_use_treatment(request)
        variant = "treatment" if use_treatment else "control"
        logger.debug("ab_split_routed", variant=variant)
        return self._treatment if use_treatment else self._control
