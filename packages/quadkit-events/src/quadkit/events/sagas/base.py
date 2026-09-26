"""SagaProtocol base classes and decorators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.workflow.steps import SagaStep

if TYPE_CHECKING:
    from collections.abc import Callable


def saga_step(
    name: str,
    *,
    compensation: bool = False,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Callable:
    """Decorator to mark saga step methods."""

    def decorator(func: Callable) -> Callable:
        func._saga_step_name = name  # type: ignore[attr-defined]
        func._saga_is_compensation = compensation  # type: ignore[attr-defined]
        func._saga_max_retries = max_retries  # type: ignore[attr-defined]
        func._saga_retry_delay = retry_delay  # type: ignore[attr-defined]
        return func

    return decorator


class SagaBase:
    """Base class for defining sagas."""

    name: str = ""

    def _get_steps(self) -> list[SagaStep]:
        """Discover ordered step definitions from decorated methods."""
        actions: dict[str, Callable] = {}
        compensations: dict[str, Callable] = {}
        retries: dict[str, int] = {}
        delays: dict[str, float] = {}
        order: list[str] = []

        for attr_name in dir(self):
            method = getattr(self.__class__, attr_name, None)
            if method is None:
                continue
            step_name = getattr(method, "_saga_step_name", None)
            if step_name is None:
                continue
            if getattr(method, "_saga_is_compensation", False):
                compensations[step_name] = getattr(self, attr_name)
            else:
                actions[step_name] = getattr(self, attr_name)
                retries[step_name] = getattr(method, "_saga_max_retries", 3)
                delays[step_name] = getattr(method, "_saga_retry_delay", 1.0)
                if step_name not in order:
                    order.append(step_name)

        return [
            SagaStep(
                name=sn,
                action=actions[sn],
                compensation=compensations.get(sn),
                max_retries=retries.get(sn, 3),
                retry_delay=delays.get(sn, 1.0),
            )
            for sn in order
        ]
