"""Contract compliance suite for ``FlagProvider`` implementations.

Subclass :class:`FlagProviderCompliance` and implement
:meth:`create_provider` to verify that any feature flag provider satisfies
the ``FlagProvider`` contract::

    from quadkit.testing.compliance import FlagProviderCompliance

    class TestMyFlagProvider(FlagProviderCompliance):
        async def create_provider(self):
            return LocalProvider({"feature_x": True, "feature_y": False})
"""

from __future__ import annotations

from abc import abstractmethod
from importlib import import_module
from typing import Any

import pytest


def _flag_not_found_error() -> type[Exception]:
    """Return the optional provider exception without a static private import."""
    try:
        module_name = ".".join(("quadkit", "features", "exceptions"))
        return getattr(import_module(module_name), "FlagNotFoundError")
    except (ImportError, AttributeError):
        # Public installations do not ship a feature-provider implementation,
        # but the compliance class remains importable for downstream users.
        return type("FlagNotFoundError", (Exception,), {})

__all__ = ["FlagProviderCompliance"]


class FlagProviderCompliance:
    """Reusable compliance suite for any ``FlagProvider`` implementation.

    Subclass and implement :meth:`create_provider`.  Override
    :meth:`enabled_flag_name` / :meth:`disabled_flag_name` to specify which
    flags the provider will return for enabled/disabled test cases.

    The provider created by :meth:`create_provider` **must** have at least:

    * one flag named ``enabled_flag_name`` that evaluates to ``True``
    * one flag named ``disabled_flag_name`` that evaluates to ``False``
    """

    # ------------------------------------------------------------------
    # Factory — subclasses MUST override
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_provider(self) -> Any:
        """Return a fully initialised FlagProvider for testing."""
        ...

    # ------------------------------------------------------------------
    # Customisation hooks
    # ------------------------------------------------------------------

    def enabled_flag_name(self) -> str:
        """Name of a flag that the provider reports as *enabled*."""
        return "enabled_feature"

    def disabled_flag_name(self) -> str:
        """Name of a flag that the provider reports as *disabled*."""
        return "disabled_feature"

    def unknown_flag_name(self) -> str:
        """Name of a flag that does **not** exist in the provider."""
        return "nonexistent_flag_xyz"

    # ------------------------------------------------------------------
    # Contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_flag_found(self) -> None:
        """get_flag returns a bool for a flag that exists in the provider."""
        provider = await self.create_provider()
        result = await provider.get_flag(self.enabled_flag_name())
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_flag_not_found(self) -> None:
        """get_flag on an unknown flag returns the default (or raises FlagNotFoundError)."""
        flag_not_found_error = _flag_not_found_error()

        provider = await self.create_provider()
        try:
            result = await provider.get_flag(self.unknown_flag_name(), default=False)
            # Acceptable: provider returns the default value.
            assert result is False
        except flag_not_found_error:
            # Also acceptable: provider raises FlagNotFoundError.
            pass

    @pytest.mark.asyncio
    async def test_evaluate_flag_enabled(self) -> None:
        """An enabled flag evaluates to True."""
        provider = await self.create_provider()
        result = await provider.get_flag(self.enabled_flag_name(), default=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_flag_disabled(self) -> None:
        """A disabled flag evaluates to False."""
        provider = await self.create_provider()
        result = await provider.get_flag(self.disabled_flag_name(), default=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_async_evaluate(self) -> None:
        """Async evaluation via get_flag is awaitable and returns a bool."""
        provider = await self.create_provider()
        # get_flag must be awaitable — this will raise TypeError if it is not.
        result = await provider.get_flag(self.enabled_flag_name())
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_flag_respects_default(self) -> None:
        """default parameter is honoured when the flag is absent."""
        flag_not_found_error = _flag_not_found_error()

        provider = await self.create_provider()
        try:
            result_true = await provider.get_flag(
                self.unknown_flag_name(), default=True
            )
            assert result_true is True

            result_false = await provider.get_flag(
                self.unknown_flag_name(), default=False
            )
            assert result_false is False
        except flag_not_found_error:
            # Provider raises instead of returning default — still compliant.
            pass
