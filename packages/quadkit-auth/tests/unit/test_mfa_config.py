"""Tests for MFA configuration models."""
from __future__ import annotations

from quadkit.auth.config import AuthConfig, BackupCodeConfig, MFAConfig, TOTPConfig


def test_mfa_config_defaults() -> None:
    cfg = MFAConfig()
    assert cfg.enabled is True
    assert cfg.totp.digits == 6
    assert cfg.totp.interval == 30
    assert cfg.totp.valid_window == 1
    assert cfg.backup.issuer == "quadkit"
    assert cfg.backup.count == 10
    assert cfg.backup.length == 8
    assert cfg.max_challenge_attempts == 3


def test_auth_config_mfa_defaults() -> None:
    cfg = AuthConfig(token={"secret_key": "test"}, secret_key="test")
    assert cfg.mfa is not None
    assert cfg.mfa.enabled is True
    assert cfg.mfa.totp.digits == 6


def test_mfa_config_from_dict() -> None:
    data = {
        "enabled": True,
        "totp": {"digits": 8, "interval": 60, "valid_window": 2},
        "backup": {"issuer": "my-app", "count": 5, "length": 10},
        "max_challenge_attempts": 5,
    }
    cfg = MFAConfig(**data)
    assert cfg.totp.digits == 8
    assert cfg.totp.interval == 60
    assert cfg.backup.issuer == "my-app"
    assert cfg.backup.count == 5
    assert cfg.max_challenge_attempts == 5


def test_mfa_config_partial_dict() -> None:
    """Partial dict only overrides specified fields; rest use defaults."""
    cfg = MFAConfig(totp={"digits": 8})
    assert cfg.totp.digits == 8
    assert cfg.totp.interval == 30  # default
    assert cfg.backup.issuer == "quadkit"  # default
