"""Tests for quadkit.testing.lib.smoke.assert_contracts_resolve."""

from __future__ import annotations

import pytest

from quadkit.testing.lib.smoke import assert_contracts_resolve


class _Ok:
    """Registered contract."""


class _Missing:
    """Unregistered contract."""


def _container_with(*registered: type) -> object:
    class _C:
        async def resolve(
            self, service_type: type, bypass_visibility: bool = False
        ) -> object:
            if service_type in registered:
                return object()
            raise LookupError(service_type.__name__)

    return _C()


@pytest.mark.asyncio
async def test_passes_when_all_registered() -> None:
    await assert_contracts_resolve(_container_with(_Ok), [_Ok])


@pytest.mark.asyncio
async def test_names_the_missing_contract() -> None:
    with pytest.raises(AssertionError, match="_Missing"):
        await assert_contracts_resolve(_container_with(), [_Missing])
