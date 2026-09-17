"""Secrets registry for secret management.

This module provides a registry pattern for managing secrets.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
import secrets
import stat
import string

from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SecretInfo:
    """Information about a secret."""

    name: str
    description: str
    required: bool = True
    env_var: str | None = None
    default_value: str | None = None


class SecretBackend(abc.ABC):
    """Abstract base class for secret backends."""

    name: str

    @abc.abstractmethod
    def get(self, key: str) -> str | None:
        """Get a secret value."""

    @abc.abstractmethod
    def set(self, key: str, value: str) -> None:
        """Set a secret value."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Delete a secret."""

    @abc.abstractmethod
    def list(self) -> list[str]:
        """List all secret keys."""

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a secret exists."""


class EnvVarSecretBackend(SecretBackend):
    """Backend that uses environment variables."""

    name = "env"

    def get(self, key: str) -> str | None:
        import os

        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        import os

        os.environ[key] = value

    def delete(self, key: str) -> None:
        import os

        os.environ.pop(key, None)

    def list(self) -> list[str]:
        import os

        return list(os.environ.keys())

    def exists(self, key: str) -> bool:
        import os

        return key in os.environ


class DotenvSecretBackend(SecretBackend):
    """Backend that uses .env files."""

    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self._secrets: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        # Deferred (plans/09172026 C-02): the security store pulls the
        # framework security chain (~125 ms); only secret-file loads pay it.
        from quadkit.security.secrets.store import SecretAccessError

        try:
            path = Path(self.env_file)
            if path.exists():
                self._assert_restrictive_permissions(path)
                with open(path) as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if line and not line.startswith("#"):
                            if "=" in line:
                                key, value = line.split("=", 1)
                                self._secrets[key.strip()] = value.strip()
        except SecretAccessError:
            raise
        except Exception as exc:  # noqa: BLE001 — secrets load failures are logged, never raised
            logger.debug("secrets_load_failed", error=str(exc))

    def _save(self) -> None:
        try:
            path = Path(self.env_file)
            with open(path, "w") as f:
                for key, value in self._secrets.items():
                    f.write(f"{key}={value}\n")
            path.chmod(0o600)
        except Exception as exc:  # noqa: BLE001 — secrets save failures are logged, never raised
            logger.debug("secrets_save_failed", error=str(exc))

    @staticmethod
    def _assert_restrictive_permissions(path: Path) -> None:
        from quadkit.security.secrets.store import SecretAccessError

        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SecretAccessError(
                f"Dotenv secret file '{path}' permissions are too open "
                f"({oct(mode)}); expected owner-only permissions."
                "Run `chmod 600` on the file to fix."
            )

    def get(self, key: str) -> str | None:
        return self._secrets.get(key)

    def set(self, key: str, value: str) -> None:
        self._secrets[key] = value
        self._save()

    def delete(self, key: str) -> None:
        self._secrets.pop(key, None)
        self._save()

    def list(self) -> list[str]:
        return list(self._secrets.keys())

    def exists(self, key: str) -> bool:
        return key in self._secrets


class SecretsRegistry:
    """Registry for secret management."""

    _backend: SecretBackend = EnvVarSecretBackend()
    _secret_definitions: dict[str, SecretInfo] = {}

    @classmethod
    def set_backend(cls, backend: SecretBackend) -> None:
        """Set the secret backend."""
        cls._backend = backend

    @classmethod
    def register_secret(
        cls,
        name: str,
        description: str,
        required: bool = True,
        env_var: str | None = None,
        default_value: str | None = None,
    ) -> None:
        """Register a secret definition."""
        cls._secret_definitions[name] = SecretInfo(
            name=name,
            description=description,
            required=required,
            env_var=env_var,
            default_value=default_value,
        )

    @classmethod
    def get_secret(cls, name: str) -> str | None:
        """Get a secret value."""
        secret_info = cls._secret_definitions.get(name)
        if secret_info and secret_info.env_var:
            return cls._backend.get(secret_info.env_var)
        return cls._backend.get(name)

    @classmethod
    def set_secret(cls, name: str, value: str) -> None:
        """Set a secret value."""
        secret_info = cls._secret_definitions.get(name)
        if secret_info and secret_info.env_var:
            cls._backend.set(secret_info.env_var, value)
        else:
            cls._backend.set(name, value)

    @classmethod
    def delete_secret(cls, name: str) -> None:
        """Delete a secret."""
        secret_info = cls._secret_definitions.get(name)
        if secret_info and secret_info.env_var:
            cls._backend.delete(secret_info.env_var)
        else:
            cls._backend.delete(name)

    @classmethod
    def list_secrets(cls) -> list[SecretInfo]:
        """List all registered secrets."""
        return list(cls._secret_definitions.values())

    @classmethod
    def check_secrets(cls) -> dict[str, bool]:
        """Check which secrets are set."""
        results = {}
        for name, info in cls._secret_definitions.items():
            if info.env_var:
                results[name] = cls._backend.exists(info.env_var)
            else:
                results[name] = cls._backend.exists(name)
        return results

    @classmethod
    def get_missing_secrets(cls) -> list[SecretInfo]:
        """Get list of missing required secrets."""
        missing = []
        for info in cls._secret_definitions.values():
            if info.required:
                key = info.env_var or info.name
                if not cls._backend.exists(key):
                    missing.append(info)
        return missing


def generate_secret(
    length: int = 32,
    include_digits: bool = True,
    include_special: bool = False,
) -> str:
    """Generate a random secret.

    Args:
        length: Length of the secret
        include_digits: Include digits in the secret
        include_special: Include special characters

    Returns:
        A random secret string
    """
    chars = string.ascii_letters
    if include_digits:
        chars += string.digits
    if include_special:
        chars += string.punctuation

    return "".join(secrets.choice(chars) for _ in range(length))


def generate_api_key() -> str:
    """Generate an API key."""
    return f"lg_{secrets.token_urlsafe(32)}"


def generate_jwt_secret(length: int = 64) -> str:
    """Generate a JWT secret."""
    return generate_secret(length=length, include_digits=True, include_special=True)


__all__ = [
    "DotenvSecretBackend",
    "EnvVarSecretBackend",
    "SecretBackend",
    "SecretInfo",
    "SecretsRegistry",
    "generate_api_key",
    "generate_jwt_secret",
    "generate_secret",
]
