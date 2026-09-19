"""Tests for SecretRotationPolicy contract.

Adapted from quadkit-security/tests/unit/test_secret_rotation_policy.py.
"""

from __future__ import annotations

import pytest

from quadkit.security.types import SecretRotationPolicy
from quadkit.security.types import SecretRotationPolicy as DirectImport


class TestSecretRotationPolicyDefaults:
    """SecretRotationPolicy has sensible default values."""

    def test_default_max_age_days(self) -> None:
        """Default max_age_days is 90."""
        policy = SecretRotationPolicy()
        assert policy.max_age_days == 90

    def test_default_rotation_warning_days(self) -> None:
        """Default rotation_warning_days is 14."""
        policy = SecretRotationPolicy()
        assert policy.rotation_warning_days == 14

    def test_default_auto_rotate_is_false(self) -> None:
        """auto_rotate defaults to False."""
        policy = SecretRotationPolicy()
        assert policy.auto_rotate is False

    def test_custom_values(self) -> None:
        """All fields can be customised."""
        policy = SecretRotationPolicy(
            max_age_days=30,
            rotation_warning_days=7,
            auto_rotate=True,
        )
        assert policy.max_age_days == 30
        assert policy.rotation_warning_days == 7
        assert policy.auto_rotate is True


class TestSecretRotationPolicyIsWarningDue:
    """``is_warning_due()`` correctness."""

    def test_no_warning_well_before_threshold(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(current_age_days=10) is False

    def test_no_warning_just_before_threshold(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(current_age_days=75.9) is False

    def test_warning_exactly_at_threshold(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(current_age_days=76) is True

    def test_warning_past_threshold(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(current_age_days=85) is True

    def test_warning_when_expired(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90, rotation_warning_days=14)
        assert policy.is_warning_due(current_age_days=91) is True


class TestSecretRotationPolicyIsExpired:
    """``is_expired()`` correctness."""

    def test_not_expired_when_young(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(current_age_days=10) is False

    def test_not_expired_just_before_max(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(current_age_days=89.99) is False

    def test_expired_exactly_at_max_age(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(current_age_days=90) is True

    def test_expired_past_max_age(self) -> None:
        policy = SecretRotationPolicy(max_age_days=90)
        assert policy.is_expired(current_age_days=100) is True


class TestSecretRotationPolicyImport:
    """SecretRotationPolicy is accessible from the public contracts API."""

    def test_importable_from_security_types(self) -> None:
        assert SecretRotationPolicy is DirectImport

    def test_in_all_exports(self) -> None:
        from quadkit.contracts.security import __all__ as exported  # noqa: PLC0415

        assert "SecretRotationPolicy" in exported
