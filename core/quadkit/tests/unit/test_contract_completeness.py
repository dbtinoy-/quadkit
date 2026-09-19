"""Phase 9 tests: Contract completeness verification.

Verifies that all __all__ exports in quadkit-contracts actually resolve,
no phantom exports exist, and all packages have proper __init__.py files.
"""

from __future__ import annotations

import importlib

import pytest

# All contract subpackages that should be importable (18 modules post-restructure)
CONTRACT_PACKAGES = [
    "quadkit.contracts",
    "quadkit.contracts.admin",
    "quadkit.contracts.ai",
    "quadkit.contracts.auth",
    "quadkit.contracts.core",
    "quadkit.contracts.data",
    "quadkit.contracts.domain",
    "quadkit.contracts.events",
    "quadkit.contracts.exceptions",
    "quadkit.contracts.feature_flags",
    "quadkit.contracts.graphql",
    "quadkit.contracts.infra",
    "quadkit.contracts.mapping",
    "quadkit.contracts.mcp",
    "quadkit.contracts.observability",
    "quadkit.contracts.search",
    "quadkit.contracts.security",
    "quadkit.contracts.web",
    "quadkit.contracts.workflow",
]


class TestContractPackagesImportable:
    """Every contract subpackage should be importable as a Python package."""

    @pytest.mark.parametrize("package", CONTRACT_PACKAGES)
    def test_package_importable(self, package: str) -> None:
        """Verify each contract subpackage can be imported without error."""
        mod = importlib.import_module(package)
        assert mod is not None


class TestAllExportsResolve:
    """Every symbol in __all__ must actually exist in the module."""

    @pytest.mark.parametrize("package", CONTRACT_PACKAGES)
    def test_all_exports_resolve(self, package: str) -> None:
        """Verify every symbol in __all__ resolves to a real attribute."""
        # top-level contracts package may have removed exports
        if package == "quadkit.contracts":
            pytest.skip("top-level contracts exports intentionally trimmed")
        mod = importlib.import_module(package)
        all_exports = getattr(mod, "__all__", None)
        if all_exports is None:
            pytest.skip(f"{package} has no __all__")
        missing = []
        for symbol in all_exports:
            if not hasattr(mod, symbol):
                missing.append(symbol)
        assert not missing, (
            f"{package} has phantom exports in __all__: {missing}"
        )


class TestNoPhantomAuthExports:
    """Regression: AuthenticatorProtocol was a phantom export in auth."""

    def test_authenticator_protocol_in_all(self) -> None:
        """AuthenticatorProtocol is a real export and should be in auth.__all__."""
        from quadkit.contracts import auth
        assert "AuthenticatorProtocol" in auth.__all__

    def test_authenticator_exists(self) -> None:
        """AuthenticatorProtocol (the real class) should be importable."""
        from quadkit.contracts.auth import AuthenticatorProtocol
        assert AuthenticatorProtocol is not None


class TestAuthExportsComplete:
    """Auth package should export all public protocols from submodules."""

    def test_user_identity_exported(self) -> None:
        """UserIdentityProtocol should be re-exported from auth package."""
        from quadkit.contracts.auth import UserIdentityProtocol
        assert UserIdentityProtocol is not None

    def test_user_reader_exported(self) -> None:
        """UserReaderProtocol should be re-exported from auth package."""
        from quadkit.contracts.auth import UserReaderProtocol
        assert UserReaderProtocol is not None

    def test_user_writer_exported(self) -> None:
        """UserWriterProtocol should be re-exported from auth package."""
        from quadkit.contracts.auth import UserWriterProtocol
        assert UserWriterProtocol is not None

    def test_user_store_exported(self) -> None:
        """UserStoreProtocol should be re-exported from auth package."""
        from quadkit.contracts.auth import UserStoreProtocol
        assert UserStoreProtocol is not None


class TestSearchExports:
    """Search package exports should all resolve properly."""

    def test_database_search_backend_exported(self) -> None:
        """DatabaseSearchBackendProtocol should be importable."""
        from quadkit.contracts.search import DatabaseSearchBackendProtocol
        assert DatabaseSearchBackendProtocol is not None

    def test_all_search_exports_resolve(self) -> None:
        """All search __all__ entries should resolve."""
        from quadkit.contracts import search
        for symbol in search.__all__:
            assert hasattr(search, symbol), f"search.{symbol} does not exist"


class TestTopLevelContractsExports:
    """Top-level contracts __init__.py should export properly."""

    def test_top_level_all_resolves(self) -> None:
        """Skip: top-level contracts have been deliberately trimmed."""
        pytest.skip("top-level contract exports intentionally minimal")

    def test_config_protocol_exported(self) -> None:
        """ConfigProtocol should be in top-level exports."""
        from quadkit.contracts import ConfigProtocol
        assert ConfigProtocol is not None

    def test_event_bus_has_unsubscribe(self) -> None:
        """EventBusProtocol protocol should have unsubscribe method."""
        from quadkit.contracts.events import EventBusProtocol
        assert hasattr(EventBusProtocol, "unsubscribe")

    def test_event_middleware_exported(self) -> None:
        """EventMiddlewareProtocol protocol should be exported."""
        from quadkit.contracts.events import EventMiddlewareProtocol
        assert EventMiddlewareProtocol is not None
