"""Tests for feature flag protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.feature_flags.protocols import (
    FlagManagerProtocol,
    FlagProviderProtocol,
    MutableFlagProviderProtocol,
)


class TestFlagProviderProtocol:
    """Tests for FlagProviderProtocol."""

    @pytest.mark.asyncio
    async def test_has_get_flag_method(self) -> None:
        """Test protocol has get_flag async method."""

        class Provider:
            async def get_flag(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        provider = Provider()
        result = await provider.get_flag("feature", default=False)
        assert result is True

    def test_has_get_flag_sync_method(self) -> None:
        """Test protocol has get_flag_sync method."""

        class Provider:
            def get_flag_sync(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        provider = Provider()
        result = provider.get_flag_sync("feature", default=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_get_variant_method(self) -> None:
        """Test protocol has get_variant async method."""

        class Provider:
            async def get_variant(
                self,
                name: str,
                *,
                default: str = "",
                context: dict[str, Any] | None = None,
            ) -> str:
                return "variant_a"

        provider = Provider()
        result = await provider.get_variant("feature", default="")
        assert result == "variant_a"

    def test_has_get_variant_sync_method(self) -> None:
        """Test protocol has get_variant_sync method."""

        class Provider:
            def get_variant_sync(
                self,
                name: str,
                *,
                default: str = "",
                context: dict[str, Any] | None = None,
            ) -> str:
                return "variant_a"

        provider = Provider()
        result = provider.get_variant_sync("feature", default="")
        assert result == "variant_a"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Provider:
            async def get_flag(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return False

            def get_flag_sync(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return False

            async def get_variant(
                self,
                name: str,
                *,
                default: str = "",
                context: dict[str, Any] | None = None,
            ) -> str:
                return ""

            def get_variant_sync(
                self,
                name: str,
                *,
                default: str = "",
                context: dict[str, Any] | None = None,
            ) -> str:
                return ""

        assert isinstance(Provider(), FlagProviderProtocol)


class TestMutableFlagProviderProtocol:
    """Tests for MutableFlagProviderProtocol."""

    @pytest.mark.asyncio
    async def test_has_set_flag_method(self) -> None:
        """Test protocol has set_flag async method."""

        class Provider:
            async def set_flag(
                self,
                name: str,
                value: bool,
            ) -> None:
                pass

            def get_flag_sync(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        provider = Provider()
        await provider.set_flag("feature", True)
        result = provider.get_flag_sync("feature")
        assert result is True

    def test_has_set_flag_sync_method(self) -> None:
        """Test protocol has set_flag_sync method."""

        class Provider:
            def set_flag_sync(
                self, name: str, value: bool
            ) -> None:
                pass

            def get_flag_sync(
                self,
                name: str,
                *,
                default: bool = False,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        provider = Provider()
        provider.set_flag_sync("feature", True)
        result = provider.get_flag_sync("feature")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_set_variant_method(self) -> None:
        """Test protocol has set_variant async method."""

        class Provider:
            async def set_variant(
                self,
                name: str,
                variant: str,
            ) -> None:
                pass

            def get_variant_sync(
                self,
                name: str,
                *,
                default: str = "",
                context: dict[str, Any] | None = None,
            ) -> str:
                return "variant_a"

        provider = Provider()
        await provider.set_variant("feature", "variant_a")
        result = provider.get_variant_sync("feature")
        assert result == "variant_a"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Provider:
            async def get_flag(
                self, name: str, *, default: bool = False, context: dict | None = None
            ) -> bool:
                return False

            def get_flag_sync(
                self, name: str, *, default: bool = False, context: dict | None = None
            ) -> bool:
                return False

            async def get_variant(
                self, name: str, *, default: str = "", context: dict | None = None
            ) -> str:
                return ""

            def get_variant_sync(
                self, name: str, *, default: str = "", context: dict | None = None
            ) -> str:
                return ""

            async def set_flag(self, name: str, value: bool) -> None:
                pass

            def set_flag_sync(self, name: str, value: bool) -> None:
                pass

            async def set_variant(self, name: str, variant: str) -> None:
                pass

            def set_variant_sync(self, name: str, variant: str) -> None:
                pass

        assert isinstance(Provider(), MutableFlagProviderProtocol)


class TestFlagManagerProtocol:
    """Tests for FlagManagerProtocol."""

    @pytest.mark.asyncio
    async def test_has_add_provider_method(self) -> None:
        """Test protocol has add_provider method."""

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def is_enabled(
                self,
                key: str,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        manager = Manager()
        assert hasattr(manager, "add_provider")

    @pytest.mark.asyncio
    async def test_has_is_enabled_method(self) -> None:
        """Test protocol has is_enabled async method."""

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def is_enabled(
                self,
                key: str,
                context: dict[str, Any] | None = None,
            ) -> bool:
                return True

        manager = Manager()
        result = await manager.is_enabled("feature")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_get_value_method(self) -> None:
        """Test protocol has get_value async method."""

        from quadkit.contracts.feature_flags.models import FlagValue

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def get_value(
                self,
                key: str,
                default: FlagValue,
                context: dict[str, Any] | None = None,
            ) -> FlagValue:
                return default

        manager = Manager()
        result = await manager.get_value("feature", default=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_evaluate_method(self) -> None:
        """Test protocol has evaluate async method."""

        from quadkit.contracts.feature_flags.models import FlagEvaluation, FlagType

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def evaluate(
                self,
                key: str,
                context: dict[str, Any] | None = None,
            ) -> FlagEvaluation:
                return FlagEvaluation(value=True, key=key, flag_type=FlagType.BOOLEAN, reason="test")

        manager = Manager()
        result = await manager.evaluate("feature")
        assert result.value is True

    @pytest.mark.asyncio
    async def test_has_get_all_flags_method(self) -> None:
        """Test protocol has get_all_flags async method."""

        from quadkit.contracts.feature_flags.models import FlagEvaluation

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def get_all_flags(
                self,
                context: dict[str, Any] | None = None,
            ) -> dict[str, FlagEvaluation]:
                return {}

        manager = Manager()
        result = await manager.get_all_flags()
        assert isinstance(result, dict)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Manager:
            def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
                pass

            async def is_enabled(
                self, key: str, context: dict | None = None
            ) -> bool:
                return False

            async def get_value(
                self, key: str, default: Any, context: dict | None = None
            ) -> Any:
                return default

            async def evaluate(
                self, key: str, context: dict | None = None
            ) -> Any:
                return {}

            async def get_all_flags(
                self, context: dict | None = None
            ) -> dict:
                return {}

        assert isinstance(Manager(), FlagManagerProtocol)
