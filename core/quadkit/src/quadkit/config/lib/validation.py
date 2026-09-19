"""Config validation orchestration for Quadkit Framework.

Provides a central function to validate all registered configurations
against a target deployment environment.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.logging import get_logger

logger = get_logger(__name__)


def validate_all_configs(
    configs: list[Any],
    env: Environment | None = None,
) -> list[ConfigIssue]:
    """Validate a list of config objects against *env*.

    Iterates over each item in *configs*, calls
    ``validate_for_environment`` when the method is available, and
    collects all returned issues.

    Args:
        configs: Iterable of config objects.  Items that do not implement
            ``validate_for_environment`` are silently skipped.
        env: Target environment override.  When ``None`` (the default)
            each config resolves its **own** active environment (its
            ``env``/``environment`` field, falling back to
            ``QK_ENV``/``APP_ENV``).  Passing an explicit value forces
            every config to validate against that environment.

    Returns:
        A flat list of all :class:`~quadkit.contracts.core.config.ConfigIssue`
        instances produced by the registered configs.
    """
    all_issues: list[ConfigIssue] = []

    for config in configs:
        validate_fn = getattr(config, "validate_for_environment", None)
        if callable(validate_fn):
            try:
                # Pass ``env`` through verbatim (including ``None``) so
                # each config falls back to its own environment field —
                # overriding it here with Environment.from_env() would
                # ignore ``env: production`` declared in application.yaml.
                issues = validate_fn(env)
                all_issues.extend(issues)
            except (TypeError, AttributeError, ValueError) as e:
                logger.debug(
                    "config.validation.error",
                    error=str(e),
                    config_type=type(config).__name__,
                )

    return all_issues


def is_insecure_secret(field: str, value: str) -> bool:
    """Return True when *value* looks like an unchanged placeholder secret.

    Tests both that the field name resembles a secret field and that the
    value contains a known placeholder substring.

    Args:
        field: Field name (used to confirm it is a secret field).
        value: The string value to evaluate.

    Returns:
        ``True`` if the value appears to be an insecure placeholder.
    """
    from quadkit.config.constants import INSECURE_SECRET_VALUES, SECRET_FIELD_PATTERNS

    field_lower = field.lower()
    if not any(p in field_lower for p in SECRET_FIELD_PATTERNS):
        return False
    value_lower = value.lower()
    return any(placeholder in value_lower for placeholder in INSECURE_SECRET_VALUES)


__all__ = ["is_insecure_secret", "validate_all_configs"]
