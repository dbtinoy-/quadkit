"""Unit tests for quadkit core security constants.

Adapted from quadkit-security/tests/unit/test_security_constants.py.
TestVersion is removed — the core constants.py does not expose __version__.
Adds origin-guard assertion proving the module resolves to quadkit core.
"""

from __future__ import annotations

import importlib.util


# ---------------------------------------------------------------------------
# Origin guard
# ---------------------------------------------------------------------------


class TestConstantsModuleIsCore:
    """Verify constants resolves to quadkit core, not quadkit-security."""

    def test_constants_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.constants")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected constants to resolve to quadkit core, got: {spec.origin!r}"
        )


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestEnvironmentPrefix:
    """Tests for environment variable prefixes."""

    def test_env_prefix(self) -> None:
        from quadkit.security import constants as const  # noqa: PLC0415

        assert const.ENV_PREFIX == "QK_SECURITY__"

    def test_env_nested_delimiter(self) -> None:
        from quadkit.security import constants as const  # noqa: PLC0415

        assert const.ENV_NESTED_DELIMITER == "__"


class TestGuardDefaults:
    """Tests for guard default constants."""

    def test_default_guard_error_message(self) -> None:
        from quadkit.security import constants as const  # noqa: PLC0415

        assert const.DEFAULT_GUARD_ERROR_MESSAGE == "Access denied."

    def test_default_guard_error_code(self) -> None:
        from quadkit.security import constants as const  # noqa: PLC0415

        assert const.DEFAULT_GUARD_ERROR_CODE == "GUARD_DENIED"


class TestAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_expected_items(self) -> None:
        from quadkit.security import constants as const  # noqa: PLC0415

        expected = [
            "DEFAULT_GUARD_ERROR_CODE",
            "DEFAULT_GUARD_ERROR_MESSAGE",
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
        ]
        for item in expected:
            assert item in const.__all__

    def test_version_token_not_in_core_constants(self) -> None:
        """The core constants.py must NOT expose __version__.

        The version token referenced 'quadkit-security' metadata, which no
        longer exists in a dissolved state.  Core constants must not re-add it.
        """
        from quadkit.security import constants as const  # noqa: PLC0415

        assert not hasattr(const, "__version__"), (
            "Core security constants must not expose __version__; "
            "that was a quadkit-security artifact."
        )
