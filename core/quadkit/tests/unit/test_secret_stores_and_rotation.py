"""Tests for secret stores (memory/env/file) and the rotation scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from typing import Any

import pytest

from quadkit.contracts.security import SecretNotFoundError
from quadkit.security.exceptions import SecretAccessError
from quadkit.security.secrets.rotation import SecretRotationScheduler
from quadkit.security.secrets.store import (
    EnvSecretStore,
    FileSecretStore,
    InMemorySecretStore,
    SecretValue,
)
from quadkit.security.secrets.types import SecretMetadata
from quadkit.security.types import SecretRotationPolicy

# ── SecretValue ───────────────────────────────────────────────────────────


class TestSecretValue:
    def test_masks_repr_and_format(self) -> None:
        v = SecretValue("hunter2")
        assert repr(v) == "SecretValue(***masked***)"
        assert f"{v}" == "SecretValue(***masked***)"
        assert v == "hunter2"  # still a str
        assert v + "!" == "hunter2!"


# ── InMemorySecretStore ───────────────────────────────────────────────────


class TestInMemorySecretStore:
    def test_crud_roundtrip(self) -> None:
        store = InMemorySecretStore({"api_key": "k1"})
        assert store.get_secret("api_key") == "k1"
        store.set_secret("db", "p")
        assert store.get_secret("db") == "p"
        store.set_secret("db", "p2")
        assert store.get_secret("db") == "p2"
        store.delete_secret("db")
        assert store.has_secret("db") is False

    def test_missing_secret_raises(self) -> None:
        store = InMemorySecretStore()
        with pytest.raises(SecretNotFoundError, match="not found"):
            store.get_secret("nope")
        with pytest.raises(SecretNotFoundError):
            store.delete_secret("nope")

    def test_exists_alias(self) -> None:
        store = InMemorySecretStore({"a": "1"})
        assert store.exists("a") is True
        assert store.exists("b") is False

    def test_initial_secrets_copy(self) -> None:
        seed = {"a": "1"}
        store = InMemorySecretStore(seed)
        seed["a"] = "mutated"
        assert store.get_secret("a") == "1"


# ── EnvSecretStore ────────────────────────────────────────────────────────


class TestEnvSecretStore:
    def test_read_and_clear_after_read(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_SECRET", "s3cr3t")
        store = EnvSecretStore()  # clear_after_read=True
        assert store.get_secret("MY_SECRET") == "s3cr3t"
        assert "MY_SECRET" not in os.environ
        with pytest.raises(SecretNotFoundError):
            store.get_secret("MY_SECRET")

    def test_keep_after_read_disabled(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_SECRET2", "v")
        store = EnvSecretStore(clear_after_read=False)
        assert store.get_secret("MY_SECRET2") == "v"
        assert os.environ["MY_SECRET2"] == "v"

    def test_set_has_delete(self, monkeypatch) -> None:
        monkeypatch.delenv("ENV_S", raising=False)
        store = EnvSecretStore()
        assert store.has_secret("ENV_S") is False
        store.set_secret("ENV_S", "x")
        assert store.has_secret("ENV_S") is True
        store.delete_secret("ENV_S")
        assert store.has_secret("ENV_S") is False
        with pytest.raises(SecretNotFoundError):
            store.delete_secret("ENV_S")

    def test_missing_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("ENV_MISSING", raising=False)
        store = EnvSecretStore()
        with pytest.raises(SecretNotFoundError):
            store.get_secret("ENV_MISSING")


# ── FileSecretStore ───────────────────────────────────────────────────────


class TestFileSecretStore:
    def test_roundtrip_and_permissions(self, tmp_path: Path) -> None:
        store = FileSecretStore(tmp_path / "secrets")
        assert store.has_secret("token") is False
        store.set_secret("token", "t-value\n")
        assert store.has_secret("token") is True
        assert store.get_secret("token") == "t-value"  # stripped

        mode = (tmp_path / "secrets" / "token").stat().st_mode & 0o777
        assert mode == 0o600

        store.delete_secret("token")
        assert store.has_secret("token") is False
        with pytest.raises(SecretNotFoundError):
            store.delete_secret("token")

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        store = FileSecretStore(tmp_path)
        with pytest.raises(SecretNotFoundError):
            store.get_secret("absent")

    def test_too_open_permissions_rejected(self, tmp_path: Path) -> None:
        store = FileSecretStore(tmp_path)
        path = tmp_path / "loose"
        path.write_text("secret")
        path.chmod(0o644)
        with pytest.raises(SecretAccessError, match="permissions are too open"):
            store.get_secret("loose")

    def test_group_writable_rejected(self, tmp_path: Path) -> None:
        store = FileSecretStore(tmp_path)
        path = tmp_path / "groupy"
        path.write_text("secret")
        path.chmod(0o620)
        with pytest.raises(SecretAccessError):
            store.get_secret("groupy")

    def test_path_traversal_names_neutralized(self, tmp_path: Path) -> None:
        store = FileSecretStore(tmp_path)
        store.set_secret("../evil", "v")
        # The .. and / are stripped/replaced — file stays inside base_dir.
        created = list(tmp_path.iterdir())
        assert len(created) == 1
        assert ".." not in created[0].name
        assert store.get_secret("../evil") == "v"


# ── SecretRotationScheduler ───────────────────────────────────────────────


class _FakeStore:
    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets or {})
        self.fail: type[Exception] | None = None

    def get_secret(self, name: str) -> Any:
        if self.fail is not None:
            raise self.fail(name)
        if name not in self._secrets:
            raise KeyError(name)
        return self._secrets[name]


def _policy(max_age: int = 30, warn: int = 7, auto: bool = False) -> SecretRotationPolicy:
    return SecretRotationPolicy(
        max_age_days=max_age, rotation_warning_days=warn, auto_rotate=auto
    )


class TestRotationScheduler:
    async def test_no_policy_means_no_rotation(self) -> None:
        scheduler = SecretRotationScheduler(_FakeStore({"a": "1"}))
        result = await scheduler.check_secret("a")
        assert result.rotation_needed is False
        assert result.message == "No rotation policy set"

    async def test_store_access_failure_reported(self) -> None:
        store = _FakeStore({"a": "1"})
        store.fail = KeyError
        scheduler = SecretRotationScheduler(store, policies={"a": _policy()})
        result = await scheduler.check_secret("a")
        assert result.rotation_needed is False
        assert "Failed to access secret" in result.message

    async def test_first_check_no_age(self) -> None:
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}), policies={"a": _policy()}
        )
        result = await scheduler.check_secret("a")
        assert result.age_days == 0.0
        assert result.expired is False
        assert result.warning is False

    async def test_expired_secret_with_metadata(self) -> None:
        old = datetime.now(UTC) - timedelta(days=35)
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}),
            policies={"a": _policy(max_age=30)},
            metadata_store={"a": SecretMetadata(name="a", last_rotated=old)},
        )
        result = await scheduler.check_secret("a")
        assert result.expired is True
        assert result.age_days > 30
        assert "expired" in result.message

    async def test_warning_window_without_auto_rotate(self) -> None:
        recent = datetime.now(UTC) - timedelta(days=25)
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}),
            policies={"a": _policy(max_age=30, warn=7, auto=False)},
            metadata_store={"a": SecretMetadata(name="a", last_rotated=recent)},
        )
        result = await scheduler.check_secret("a")
        assert result.warning is True
        assert result.expired is False
        assert result.rotation_needed is False  # no auto_rotate
        assert "will expire in" in result.message

    async def test_warning_with_auto_rotate_needs_rotation(self) -> None:
        recent = datetime.now(UTC) - timedelta(days=25)
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}),
            policies={"a": _policy(max_age=30, warn=7, auto=True)},
            metadata_store={"a": SecretMetadata(name="a", last_rotated=recent)},
        )
        result = await scheduler.check_secret("a")
        assert result.rotation_needed is True

    async def test_age_from_previous_check_times(self) -> None:
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}), policies={"a": _policy(max_age=1, warn=0)}
        )
        first = await scheduler.check_secret("a")
        assert first.age_days == 0.0
        # Pretend the previous check was 2 days ago.
        scheduler._check_times["a"] = datetime.now(UTC) - timedelta(days=2)  # noqa: SLF001
        second = await scheduler.check_secret("a")
        assert second.age_days > 1
        assert second.expired is True

    async def test_check_all_and_needing_rotation(self) -> None:
        old = datetime.now(UTC) - timedelta(days=100)
        fresh = datetime.now(UTC) - timedelta(days=1)
        scheduler = SecretRotationScheduler(
            _FakeStore({"old": "1", "fresh": "2"}),
            policies={"old": _policy(max_age=30), "fresh": _policy(max_age=30)},
            metadata_store={
                "old": SecretMetadata(name="old", last_rotated=old),
                "fresh": SecretMetadata(name="fresh", last_rotated=fresh),
            },
        )
        results = await scheduler.check_all()
        assert {r.secret_name for r in results} == {"old", "fresh"}
        needing = await scheduler.get_secrets_needing_rotation()
        assert needing == ["old"]

    def test_policy_management(self) -> None:
        scheduler = SecretRotationScheduler(_FakeStore())
        assert scheduler.get_policy("a") is None
        scheduler.set_policy("a", _policy(max_age=10))
        assert scheduler.get_policy("a") is not None
        scheduler.set_policy("a", _policy(max_age=20))
        assert scheduler.get_policy("a").max_age_days == 20  # type: ignore[union-attr]
        scheduler.remove_policy("a")
        assert scheduler.get_policy("a") is None
        scheduler.remove_policy("missing")  # no-op

    def test_record_rotation_updates_and_creates_metadata(self) -> None:
        scheduler = SecretRotationScheduler(_FakeStore())
        scheduler.record_rotation("new-secret")
        meta = scheduler._metadata_store["new-secret"]  # noqa: SLF001
        assert meta.name == "new-secret"
        assert meta.last_rotated is not None

        existing = SecretMetadata(name="existing")
        scheduler._metadata_store["existing"] = existing  # noqa: SLF001
        scheduler.record_rotation("existing")
        assert scheduler._metadata_store["existing"].last_rotated is not None  # noqa: SLF001

    async def test_rotation_resets_expiry(self) -> None:
        old = datetime.now(UTC) - timedelta(days=100)
        scheduler = SecretRotationScheduler(
            _FakeStore({"a": "1"}),
            policies={"a": _policy(max_age=30)},
            metadata_store={"a": SecretMetadata(name="a", last_rotated=old)},
        )
        before = await scheduler.check_secret("a")
        assert before.expired is True
        scheduler.record_rotation("a")
        after = await scheduler.check_secret("a")
        assert after.expired is False
        assert after.age_days < 1
