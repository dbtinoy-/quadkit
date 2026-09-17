"""Contributor boot failure classification — distinguishes expected
missing-dependency failures from genuine errors."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.contracts.exceptions.container import UnresolvableDependencyError


@dataclass(frozen=True, slots=True)
class ContributorBootFailure:
    """Structured summary of a contributor boot failure."""

    expected: bool
    reason: str
    summary: str


def summarize_contributor_boot_failure(exc: Exception) -> ContributorBootFailure:
    """Classify a contributor boot exception as expected or genuine.

    ``ModuleNotFoundError`` and ``ImportError`` raised during contributor
    boot are typically expected when an optional package is absent.
    ``UnresolvableDependencyError`` likewise means an optional contributor's
    backing service is not registered in this deployment. All other errors
    are treated as genuine failures.
    """
    if isinstance(exc, (ModuleNotFoundError, ImportError)):
        name = getattr(exc, "name", "") or str(exc)
        return ContributorBootFailure(
            expected=True,
            reason=f"optional dependency not installed: {name}",
            summary=str(exc),
        )

    if isinstance(exc, UnresolvableDependencyError):
        dependency = str(exc.details.get("dependency") or "").strip()
        return ContributorBootFailure(
            expected=True,
            reason="required service is not registered",
            # QuadkitError.__str__ includes codes, hints, and newlines. The
            # structured dependency name is the useful, log-safe summary.
            summary=dependency or exc.message.splitlines()[0],
        )

    if isinstance(exc, QuadkitError):
        code = getattr(exc, "_code", "")
        return ContributorBootFailure(
            expected=False,
            reason=f"{code} {type(exc).__name__}",
            summary=str(exc),
        )

    return ContributorBootFailure(
        expected=False,
        reason=type(exc).__name__,
        summary=str(exc),
    )


__all__ = [
    "ContributorBootFailure",
    "summarize_contributor_boot_failure",
]
