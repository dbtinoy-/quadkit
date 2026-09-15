"""Tests for security types (Task 1 — core package creation).

Adapted from quadkit-security/tests/unit/test_security_types.py.
"""

from __future__ import annotations

import pytest

from quadkit.security.types import SecretRotationPolicy


class TestSecretRotationPolicy:
    """Tests for SecretRotationPolicy."""

    def test_default_values(self) -> None:
        """Test default policy values."""
        policy = SecretRotationPolicy()
        assert policy.max_age_days == 90
        assert policy.rotation_warning_days == 14
        assert policy.auto_rotate is False

    def test_custom_values(self) -> None:
        """Test custom policy values."""
        policy = SecretRotationPolicy(
            max_age_days=30,
            rotation_warning_days=7,
            auto_rotate=True,
        )
        assert policy.max_age_days == 30
        assert policy.rotation_warning_days == 7
        assert policy.auto_rotate is True

    def test_is_warning_due_before_threshold(self) -> None:
        """Test warning is not due before threshold."""
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(0) is False
        assert policy.is_warning_due(50) is False
        assert policy.is_warning_due(75) is False

    def test_is_warning_due_at_threshold(self) -> None:
        """Test warning is due at threshold."""
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(76) is True

    def test_is_warning_due_after_threshold(self) -> None:
        """Test warning is due after threshold."""
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(80) is True
        assert policy.is_warning_due(89) is True

    def test_is_expired_before_threshold(self) -> None:
        """Test secret is not expired before max age."""
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(0) is False
        assert policy.is_expired(50) is False
        assert policy.is_expired(89) is False

    def test_is_expired_at_max_age(self) -> None:
        """Test secret is expired at max age."""
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(90) is True

    def test_is_expired_after_max_age(self) -> None:
        """Test secret is expired after max age."""
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(100) is True
        assert policy.is_expired(200) is True

    def test_is_expired_with_fractional_days(self) -> None:
        """Test with fractional days."""
        policy = SecretRotationPolicy(max_age_days=1)
        assert policy.is_expired(0.5) is False
        assert policy.is_expired(1.0) is True

    def test_is_warning_due_with_fractional_days(self) -> None:
        """Test warning with fractional days."""
        policy = SecretRotationPolicy(max_age_days=30, rotation_warning_days=10)
        assert policy.is_warning_due(19.5) is False
        assert policy.is_warning_due(20.0) is True

    def test_warning_threshold_calculation(self) -> None:
        """Test warning threshold is correctly calculated."""
        policy = SecretRotationPolicy(max_age_days=100, rotation_warning_days=25)
        assert policy.max_age_days - policy.rotation_warning_days == 75
        assert policy.is_warning_due(74.9) is False
        assert policy.is_warning_due(75.0) is True

    def test_zero_warning_days(self) -> None:
        """Test with zero warning days."""
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=0)
        assert policy.is_warning_due(90) is True
        assert policy.is_warning_due(89) is False

    def test_types_exported(self) -> None:
        """Test that types are in __all__."""
        from quadkit.security.types import __all__

        assert "SecretRotationPolicy" in __all__

    def test_dataclass_repr(self) -> None:
        """Test dataclass representation."""
        policy = SecretRotationPolicy(max_age_days=30, auto_rotate=True)
        repr_str = repr(policy)
        assert "SecretRotationPolicy" in repr_str
        assert "max_age_days=30" in repr_str
