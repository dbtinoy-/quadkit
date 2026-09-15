"""Boot-time composition assertions for provider exports."""

from __future__ import annotations

from typing import Any


async def assert_contracts_resolve(container: Any, contracts: list[type]) -> None:
    """Resolve every contract, failing loudly on the first miss.

    Args:
        container: DI resolver exposing ``resolve(type, bypass_visibility=...)``.
        contracts: Contract types a provider declares in ``exports``.

    Raises:
        AssertionError: naming the first contract that cannot be resolved.
    """
    for contract in contracts:
        try:
            await container.resolve(contract, bypass_visibility=True)
        except Exception as exc:  # noqa: BLE001 — any failure means unresolved
            raise AssertionError(
                f"contract failed to resolve: {contract.__name__}: {exc}"
            ) from exc


__all__ = ["assert_contracts_resolve"]
