"""Tests for MFAManager using MFAConfig values."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from quadkit.auth.config import BackupCodeConfig, MFAConfig, TOTPConfig
from quadkit.auth.mfa.manager import MFAManager


def _mock_user_store() -> MagicMock:
    store = MagicMock()
    store.get_user_by_id = AsyncMock(return_value=None)
    store.update_user = AsyncMock()
    return store


def test_mfa_manager_default_config() -> None:
    manager = MFAManager(user_store=_mock_user_store())
    assert manager.config is not None
    assert manager.config.totp.digits == 6
    assert manager.config.totp.interval == 30
    assert manager.config.totp.valid_window == 1
    assert manager.config.backup.issuer == "quadkit"
    assert manager.config.backup.count == 10
    assert manager.config.backup.length == 8


def test_mfa_manager_custom_config() -> None:
    cfg = MFAConfig(
        totp=TOTPConfig(digits=8, interval=60, valid_window=2),
        backup=BackupCodeConfig(issuer="my-app", count=5, length=10),
        max_challenge_attempts=5,
    )
    manager = MFAManager(user_store=_mock_user_store(), config=cfg)
    assert manager.config.totp.digits == 8
    assert manager.config.backup.issuer == "my-app"
    assert manager.config.backup.count == 5
