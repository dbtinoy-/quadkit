"""Relay retry classification — pinned to new-api's status ranges.

The default policy is a compatibility contract, not a preference: it decides
whether a request fails over to another channel or surfaces an error. These
tests pin the exact ranges so a "tidy-up" cannot quietly narrow failover —
the failure mode that made the framework's previous ``status >= 500`` test
wrong for a gateway.
"""

from __future__ import annotations

import pytest

from quadkit.contracts.ai.relay import (
    NEVER_RETRY_STATUSES,
    NEW_API_RETRY_RANGES,
    RelayRetryPolicy,
)

#: Every status the default policy retries, one representative per band plus
#: the inclusive boundaries, which is where an off-by-one hides.
RETRYABLE = (
    100,
    150,
    199,
    300,
    350,
    399,
    401,
    404,
    407,
    409,
    429,
    499,
    500,
    502,
    503,
    505,
    511,
    523,
    525,
    550,
    599,
)

#: Statuses the default policy never retries on another channel.
NOT_RETRYABLE = (
    0,
    99,
    400,
    408,
    504,
    524,
    600,
    599 + 100,
)


def test_default_ranges_are_the_new_api_ranges() -> None:
    """The pinned tuple is new-api's ``AutomaticRetryStatusCodeRanges``."""
    assert NEW_API_RETRY_RANGES == (
        (100, 199),
        (300, 399),
        (401, 407),
        (409, 499),
        (500, 503),
        (505, 523),
        (525, 599),
    )
    assert RelayRetryPolicy.default().ranges == NEW_API_RETRY_RANGES


def test_never_retry_statuses_are_pinned() -> None:
    """400 is malformed; 408/504/524 may already have been processed upstream."""
    assert frozenset({400, 408, 504, 524}) == NEVER_RETRY_STATUSES


@pytest.mark.parametrize("status", RETRYABLE)
def test_retryable_statuses(status: int) -> None:
    """Every band is retried, boundaries included."""
    assert RelayRetryPolicy.default().is_retryable(status) is True


@pytest.mark.parametrize("status", NOT_RETRYABLE)
def test_not_retryable_statuses(status: int) -> None:
    """The excluded statuses and out-of-band values are not retried."""
    assert RelayRetryPolicy.default().is_retryable(status) is False


def test_never_retry_wins_over_a_range_that_covers_it() -> None:
    """An explicit never-retry entry beats a covering range."""
    policy = RelayRetryPolicy(ranges=((400, 500),), never_retry=frozenset({429}))
    assert policy.is_retryable(429) is False
    assert policy.is_retryable(430) is True


def test_server_errors_only_is_the_conservative_alternative() -> None:
    """The pre-ranges behavior stays available without forking the type."""
    policy = RelayRetryPolicy.server_errors_only()
    assert policy.is_retryable(503) is True
    assert policy.is_retryable(500) is True
    assert policy.is_retryable(429) is False
    assert policy.is_retryable(403) is False
    assert policy.is_retryable(400) is False


def test_server_errors_only_retries_504() -> None:
    """The conservative policy is 5xx-only, so its 504 exclusion is dropped.

    This is the deliberate difference from the default: a deployment that opts
    into it accepts a duplicate-work risk on gateway timeouts in exchange for
    never relocating a request that failed for a channel-specific reason.
    """
    policy = RelayRetryPolicy.server_errors_only()
    assert policy.is_retryable(504) is True
    assert policy.is_retryable(524) is True


@pytest.mark.parametrize(
    "ranges",
    [
        (),
        ((599, 500),),
        ((99, 200),),
        ((400, 600),),
        ((400,),),
    ],
)
def test_invalid_ranges_are_rejected(ranges: tuple[tuple[int, ...], ...]) -> None:
    """A malformed range fails at construction, not at request time."""
    with pytest.raises(ValueError, match=r"range"):
        RelayRetryPolicy(ranges=ranges)  # type: ignore[arg-type]


def test_policy_is_frozen_and_hashable() -> None:
    """The policy is a value object, safe to share across channels."""
    policy = RelayRetryPolicy.default()
    assert policy == RelayRetryPolicy.default()
    assert hash(policy) == hash(RelayRetryPolicy.default())
    with pytest.raises(AttributeError):
        policy.ranges = ()  # type: ignore[misc]
