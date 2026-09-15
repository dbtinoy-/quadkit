"""Boot-time secrets validation for Quadkit Framework.

Provides ``SecretsPolicy`` (configuration) and ``SecretsValidator`` (concrete
implementation) so that every application gets safe, consistent secret
validation at startup without reinventing it.

Apps register the secrets they want validated; the framework supplies the
logic.

Usage::

    from quadkit.config.secrets import SecretsPolicy, SecretsValidator
    from quadkit.contracts.core.config import Environment

    policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
    validator = SecretsValidator(policy)
    validator.validate(
        {
            "JWT_SECRET": "my-very-long-production-secret-value-here",
            "DATABASE_URL": "postgresql://...",
        }
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from quadkit.contracts.core.config import Environment
from quadkit.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------

#: Values that are clearly placeholders — fail on production, warn on dev.
DEFAULT_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "",
        "dev-secret",
        "change-me",
        "changeme",
        "xxx",
        "placeholder",
    }
)

#: Minimum lengths for commonly known secret names (substring match, case-insensitive).
#: Apps may extend this via ``SecretsPolicy.min_lengths``.
DEFAULT_MIN_LENGTHS: dict[str, int] = {
    "jwt_secret": 32,
    "jwt_signing_key": 32,
    "signing_key": 32,
    "secret_key": 32,
    "oauth_client_secret": 16,
    "client_secret": 16,
    "api_secret": 16,
    "access_token_secret": 32,
    "encryption_key": 32,
    "session_secret": 32,
    "admin_secret": 32,
}


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretViolation:
    """A single secret validation failure.

    Attributes:
        name: The secret name (key) that failed validation.
        reason: Human-readable description of the problem.
    """

    name: str
    reason: str


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SecretsValidatorProtocol(Protocol):
    """Protocol for boot-time secret validation.

    Implement this to provide a custom validator, or use the default
    :class:`SecretsValidator` implementation.
    """

    def validate(self, secrets: dict[str, str]) -> None:
        """Validate *secrets* against the active policy.

        Args:
            secrets: Mapping of secret name → secret value.  Names should be
                descriptive (e.g. ``"JWT_SECRET"``).

        Raises:
            ConfigurationError: When strict mode is active and any violation
                is found.

        In non-strict mode violations are logged as warnings and boot
        continues.
        """
        ...


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretsPolicy:
    """Configuration that governs how secrets are validated at boot.

    Attributes:
        strict: When ``True``, any violation raises :class:`ConfigurationError`
            and aborts boot.  When ``False``, violations are logged as
            warnings and boot continues.
        allow_placeholders_in_dev: When ``True`` (the default for
            ``DEVELOPMENT``), placeholder values in the ``placeholders`` set
            are tolerated.  This is a per-environment convenience flag — set
            it to ``False`` on dev machines that need production parity.
        placeholders: Set of string values considered insecure placeholders.
            Defaults to :data:`DEFAULT_PLACEHOLDER_VALUES`.
        min_lengths: Per-secret-name minimum length overrides.  Keys are
            **substrings** matched case-insensitively against the secret name.
            Overrides merge with (and extend) ``DEFAULT_MIN_LENGTHS``.
    """

    strict: bool = True
    allow_placeholders_in_dev: bool = False
    placeholders: frozenset[str] = field(
        default_factory=lambda: DEFAULT_PLACEHOLDER_VALUES
    )
    min_lengths: dict[str, int] = field(default_factory=dict)

    @classmethod
    def for_environment(cls, env: Environment) -> SecretsPolicy:
        """Return the default policy for *env*.

        - ``PRODUCTION`` / ``STAGING``: strict=True, no placeholder allowance.
        - ``DEVELOPMENT``: strict=False, placeholders permitted.
        - ``TEST``: strict=False, placeholders permitted (for fixtures).

        Args:
            env: The deployment environment.

        Returns:
            A :class:`SecretsPolicy` with sensible defaults for *env*.
        """
        if env in (Environment.PRODUCTION, Environment.STAGING):
            return cls(strict=True, allow_placeholders_in_dev=False)
        return cls(strict=False, allow_placeholders_in_dev=True)

    def effective_min_lengths(self) -> dict[str, int]:
        """Return merged minimum-length map (defaults + overrides).

        App-supplied ``min_lengths`` take precedence over
        :data:`DEFAULT_MIN_LENGTHS`.

        Returns:
            A dict mapping secret-name substrings to minimum lengths.
        """
        merged = dict(DEFAULT_MIN_LENGTHS)
        merged.update(self.min_lengths)
        return merged


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


class SecretsValidator:
    """Default secrets validator implementation.

    Checks each registered secret against the :class:`SecretsPolicy`:

    1. Placeholder detection — rejects known placeholder values unless
       ``allow_placeholders_in_dev`` is ``True``.
    2. Minimum length — rejects values shorter than the per-name threshold.

    Args:
        policy: The :class:`SecretsPolicy` controlling validation behaviour.
    """

    def __init__(self, policy: SecretsPolicy) -> None:
        self._policy = policy

    def validate(self, secrets: dict[str, str]) -> None:
        """Validate *secrets* against the active policy.

        Args:
            secrets: Mapping of secret name → value.

        Raises:
            quadkit.contracts.exceptions.ConfigurationError: In strict mode
                when one or more violations are found.
        """
        violations = self._collect_violations(secrets)
        if not violations:
            return

        if self._policy.strict:
            self._raise(violations)
        else:
            for v in violations:
                logger.warning(
                    "secrets.validation.warning",
                    secret_name=v.name,
                    reason=v.reason,
                )

    # -- internals -----------------------------------------------------------

    def _collect_violations(self, secrets: dict[str, str]) -> list[SecretViolation]:
        violations: list[SecretViolation] = []
        for name, value in secrets.items():
            violation = self._check_secret(name, value)
            if violation is not None:
                violations.append(violation)
        return violations

    def _check_secret(self, name: str, value: str) -> SecretViolation | None:
        # 1. Placeholder check
        if not self._policy.allow_placeholders_in_dev:
            if value in self._policy.placeholders:
                display = repr(value) if value else "(empty string)"
                return SecretViolation(
                    name=name,
                    reason=f"value is a known placeholder ({display})",
                )

        # 2. Minimum length check
        min_len = self._resolve_min_length(name)
        if min_len and len(value) < min_len:
            return SecretViolation(
                name=name,
                reason=f"value is too short (got {len(value)} chars, need ≥ {min_len})",
            )

        return None

    def _resolve_min_length(self, name: str) -> int:
        """Return the minimum required length for *name*, or 0 if not constrained."""
        name_lower = name.lower()
        lengths = self._policy.effective_min_lengths()
        for pattern, min_len in lengths.items():
            if pattern in name_lower:
                return min_len
        return 0

    def _raise(self, violations: list[SecretViolation]) -> None:
        from quadkit.contracts.exceptions import ConfigurationError

        lines = [f"  {v.name}: {v.reason}" for v in violations]
        message = "Boot-time secrets validation failed:\n" + "\n".join(lines)
        raise ConfigurationError(message)


__all__ = [
    "DEFAULT_MIN_LENGTHS",
    "DEFAULT_PLACEHOLDER_VALUES",
    "SecretViolation",
    "SecretsPolicy",
    "SecretsValidator",
    "SecretsValidatorProtocol",
]
