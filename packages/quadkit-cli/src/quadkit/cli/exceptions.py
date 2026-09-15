"""CLI-specific exceptions."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import QuadkitError


class CliError(QuadkitError):
    """Base exception for quadkit-cli operations."""

    _code: str = "QK_ERR_CLI_001"

    def __init__(
        self,
        message: str | None = None,
        causes: list[str] | None = None,
        suggestions: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CLI error.

        Args:
            message: Human-readable error message.
            causes: List of potential causes for the error.
            suggestions: List of suggestions to resolve the error.
            **kwargs: Additional keyword arguments passed to parent.
        """
        super().__init__(message, **kwargs)
        self.causes = causes or []
        self.suggestions = suggestions or []


class ConfigNotFoundError(CliError):
    """Raised when application.yaml configuration file is not found."""

    _code: str = "QK_ERR_CLI_002"

    def __init__(self) -> None:
        """Initialize config not found error."""
        super().__init__(
            message="Configuration file 'application.yaml' not found",
            suggestions=["Run 'quadkit init' to create a new project"],
        )


class ProviderNotInstalledError(CliError):
    """Raised when a required provider package is not installed."""

    _code: str = "QK_ERR_CLI_003"

    def __init__(self, provider: str) -> None:
        """Initialize provider not installed error.

        Args:
            provider: Name of the missing provider.
        """
        super().__init__(
            message=f"Provider '{provider}' is not installed",
            suggestions=[f"Install with: pip install quadkit-{provider}"],
        )


__all__ = ["CliError", "ConfigNotFoundError", "ProviderNotInstalledError"]
