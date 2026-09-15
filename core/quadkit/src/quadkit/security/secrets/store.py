"""Secret store implementations for development and local runtime.

Provides an in-memory store plus opt-in environment and file-backed stores
with defensive handling for secret values.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat

from quadkit.contracts.security import SecretNotFoundError
from quadkit.logging import get_logger
from quadkit.security.exceptions import SecretAccessError

logger = get_logger(__name__)


class SecretValue(str):
    """String secret value with masked ``repr`` for safer logging."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "SecretValue(***masked***)"

    def __format__(self, format_spec: str) -> str:
        return "SecretValue(***masked***)"


class InMemorySecretStore:
    """In-memory secret store for testing and local development.

    This implementation stores secrets in a simple dictionary, suitable for
    unit tests and local development. It is NOT secure for production use.

    Example::

        from quadkit.security.secrets import InMemorySecretStore

        store = InMemorySecretStore({"api_key": "test-key"})
        assert store.get_secret("api_key") == "test-key"
    """

    def __init__(self, initial_secrets: dict[str, str] | None = None) -> None:
        """Initialize with optional initial secrets.

        Args:
            initial_secrets: Dictionary of secret name → value.
        """
        self._secrets: dict[str, str] = dict(initial_secrets or {})

    def get_secret(self, name: str) -> str:
        """Return the value of a secret by name.

        Args:
            name: Unique secret identifier.

        Returns:
            The plaintext secret value.

        Raises:
            SecretNotFoundError: If no secret with that name exists.
        """
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret '{name}' not found")
        return SecretValue(self._secrets[name])

    def set_secret(self, name: str, value: str) -> None:
        """Write or overwrite a secret.

        Args:
            name: Unique secret identifier.
            value: Plaintext secret value.
        """
        self._secrets[name] = value
        logger.debug("secret_set", secret_name=name)

    def delete_secret(self, name: str) -> None:
        """Delete a secret by name.

        Args:
            name: Unique secret identifier.

        Raises:
            SecretNotFoundError: If no secret with that name exists.
        """
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret '{name}' not found")
        del self._secrets[name]
        logger.debug("secret_deleted", secret_name=name)

    def has_secret(self, name: str) -> bool:
        """Check if a secret exists.

        Args:
            name: Unique secret identifier.

        Returns:
            True if the secret exists, False otherwise.
        """
        return name in self._secrets

    def exists(self, name: str) -> bool:
        """Backward-compatible alias for :meth:`has_secret`."""
        return self.has_secret(name)


class EnvSecretStore:
    """Environment-variable backed secret store.

    By default this store clears secrets from ``os.environ`` after read to
    reduce accidental leakage in later subprocesses.
    """

    def __init__(self, *, clear_after_read: bool = True) -> None:
        self._clear_after_read = clear_after_read

    def get_secret(self, name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            raise SecretNotFoundError(f"Secret '{name}' not found")
        if self._clear_after_read:
            os.environ.pop(name, None)
        return SecretValue(value)

    def set_secret(self, name: str, value: str) -> None:
        os.environ[name] = value

    def delete_secret(self, name: str) -> None:
        if name not in os.environ:
            raise SecretNotFoundError(f"Secret '{name}' not found")
        del os.environ[name]

    def has_secret(self, name: str) -> bool:
        return name in os.environ


class FileSecretStore:
    """File-backed secret store.

    Expects one file per secret under ``base_dir``. Files must not be
    group/world readable or writable.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)

    def _path_for(self, name: str) -> Path:
        safe_name = name.replace("..", "").replace("/", "_")
        return self._base_dir / safe_name

    @staticmethod
    def _assert_restrictive_permissions(path: Path) -> None:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SecretAccessError(
                f"Secret file '{path}' permissions are too open ({oct(mode)}); "
                "expected owner-only permissions (e.g., 0o600)."
            )

    def get_secret(self, name: str) -> str:
        path = self._path_for(name)
        if not path.exists():
            raise SecretNotFoundError(f"Secret '{name}' not found")
        self._assert_restrictive_permissions(path)
        return SecretValue(path.read_text(encoding="utf-8").strip())

    def set_secret(self, name: str, value: str) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(name)
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)

    def delete_secret(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            raise SecretNotFoundError(f"Secret '{name}' not found")
        path.unlink()

    def has_secret(self, name: str) -> bool:
        return self._path_for(name).exists()


__all__ = [
    "EnvSecretStore",
    "FileSecretStore",
    "InMemorySecretStore",
    "SecretValue",
]
