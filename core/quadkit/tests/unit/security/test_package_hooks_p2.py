"""P2 hook surface import verification for quadkit core security.

Adapted from quadkit-security/tests/unit/test_package_hooks_p2.py.
Adds origin-guard assertion proving modules resolve to quadkit core.
"""

from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError, is_dataclass

import pytest


# ---------------------------------------------------------------------------
# Origin guard
# ---------------------------------------------------------------------------


class TestHooksModuleIsCore:
    """Verify hooks resolves to quadkit core, not quadkit-security."""

    def test_hooks_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.hooks")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected hooks to resolve to quadkit core, got: {spec.origin!r}"
        )


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_security_hooks_root_module_exists() -> None:
    import quadkit.security
    from quadkit.security.hooks import (
        SecurityGuardBlockedHook,
        SecurityGuardPassedHook,
        SecurityThreatDetectedHook,
    )

    assert SecurityGuardPassedHook.__name__ == "SecurityGuardPassedHook"
    assert SecurityGuardBlockedHook.__name__ == "SecurityGuardBlockedHook"
    assert SecurityThreatDetectedHook.__name__ == "SecurityThreatDetectedHook"
    assert quadkit.security.SecurityGuardPassedHook is SecurityGuardPassedHook
    assert quadkit.security.SecurityGuardBlockedHook is SecurityGuardBlockedHook
    assert quadkit.security.SecurityThreatDetectedHook is SecurityThreatDetectedHook


def test_security_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.security.hooks import (
        SecurityGuardBlockedHook,
        SecurityGuardPassedHook,
    )

    passed = SecurityGuardPassedHook(guard_name="JWTGuard")
    blocked = SecurityGuardBlockedHook(
        guard_name="RoleGuard", reason="insufficient_permissions"
    )

    assert is_dataclass(passed)
    assert is_dataclass(blocked)

    with pytest.raises(TypeError):
        SecurityGuardPassedHook("JWTGuard")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        passed.guard_name = "other"  # type: ignore[misc]
