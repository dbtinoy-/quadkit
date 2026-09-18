"""Contributor boot failures are classified into safe operational summaries."""

from quadkit.contracts.admin.contributor_boot import (
    summarize_contributor_boot_failure,
)
from quadkit.contracts.exceptions.container import UnresolvableDependencyError


def test_unresolvable_service_is_an_expected_contributor_disablement() -> None:
    failure = summarize_contributor_boot_failure(
        UnresolvableDependencyError(
            "multi-line internals must not reach the event\nsecond line",
            dependency="SearchService",
        )
    )

    assert failure.expected is True
    assert failure.reason == "required service is not registered"
    assert failure.summary == "SearchService"


def test_unresolvable_service_without_dependency_uses_one_line_message() -> None:
    failure = summarize_contributor_boot_failure(
        UnresolvableDependencyError("Service is not configured\ninternal detail")
    )

    assert failure.expected is True
    assert failure.summary == "Service is not configured"


def test_unexpected_runtime_error_remains_a_failure() -> None:
    failure = summarize_contributor_boot_failure(RuntimeError("boot exploded"))

    assert failure.expected is False
    assert failure.reason == "RuntimeError"
    assert failure.summary == "boot exploded"
