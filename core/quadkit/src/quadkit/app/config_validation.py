"""Boot-time configuration validation for :class:`~quadkit.app.base.Application`.

Extracted from ``Application._validate_config`` to keep the base class
under the 500-LOC budget; behavior is verbatim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.config import ConfigProtocol
    from quadkit.logging import LoggerProtocol


def validate_app_config(
    config: ConfigProtocol,
    logger: LoggerProtocol,
) -> None:
    """Validate *config* against the active environment.

    Runs :meth:`validate_for_environment
    <quadkit.contracts.core.config.ConfigProtocol.validate_for_environment>`
    on the root config and collects all returned
    :class:`~quadkit.contracts.core.config.ConfigIssue` entries.

    - ``severity="warning"`` issues are logged.
    - ``severity="error"`` issues (e.g. ``debug=True`` in production)
      abort the boot with :class:`ConfigurationError`.

    Args:
        config: The root application config.
        logger: Logger receiving warning-level issues.

    Raises:
        ConfigurationError: When hard validation constraints are violated.
    """
    from quadkit.config.lib.validation import validate_all_configs
    from quadkit.contracts.exceptions.config import ConfigurationError

    issues = validate_all_configs([config])
    for issue in issues:
        if issue.severity != "error":
            logger.warning(
                "config.validation.issue",
                field=issue.field,
                message=issue.message,
                suggestion=issue.suggestion,
            )
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        details = "; ".join(f"{i.field}: {i.message}" for i in errors)
        hints = "; ".join(i.suggestion for i in errors if i.suggestion)
        raise ConfigurationError(
            f"Configuration validation failed — refusing to start: {details}"
            + (f" ({hints})" if hints else ""),
            issues=list(issues),
        )


__all__ = ["validate_app_config"]
