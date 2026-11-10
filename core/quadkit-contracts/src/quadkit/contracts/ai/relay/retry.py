"""Upstream retry classification for the relay gateway.

A gateway routes across channels, so "the request failed" and "the request
failed *for this channel*" are different facts. A channel that answers 429
is rate-limited right now; 401/403 means its credential was rejected; 404
means the model is not provisioned there. Every one of those is worth
trying on a different channel. A 400 is not — the request itself is
malformed, and every channel will reject it identically.

The default ranges are new-api's ``AutomaticRetryStatusCodeRanges``, which
the gateway mirrors deliberately:

- 1xx and 3xx — the upstream did not answer the request (interim or
  redirect); another channel may.
- 401–407 — credential or proxy-auth rejection for this channel.
- 409–499 — request rejected for a reason specific to this channel or
  deployment (429 quota, 403 policy, 404 catalog); 408 is excluded because
  the timeout is a property of the connection, not the channel.
- 500–503, 505–523, 525–599 — upstream faults worth a second channel.
- 400, 408, 504, 524 — never retried on another channel. 400 is malformed;
  the other three may already have been processed upstream, so a retry
  risks duplicate work (and duplicate billing).

The policy is a value object, not a protocol: it carries no I/O and is safe
to construct anywhere. Callers that want the previous "5xx only" behavior
use :meth:`RelayRetryPolicy.server_errors_only`; that remains available so
a deployment can choose conservatively without forking the type.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Lowest and highest status a policy may reference.
MIN_STATUS = 100
MAX_STATUS = 599

#: new-api's ``AutomaticRetryStatusCodeRanges``, in inclusive pairs.
NEW_API_RETRY_RANGES: tuple[tuple[int, int], ...] = (
    (100, 199),
    (300, 399),
    (401, 407),
    (409, 499),
    (500, 503),
    (505, 523),
    (525, 599),
)

#: Statuses that are never retried on another channel, whatever the ranges say.
NEVER_RETRY_STATUSES: frozenset[int] = frozenset({400, 408, 504, 524})

#: The conservative alternative: retry only on a server-side failure.
SERVER_ERROR_RANGES: tuple[tuple[int, int], ...] = ((500, 599),)


@dataclass(frozen=True, slots=True)
class RelayRetryPolicy:
    """Which upstream statuses justify trying another channel.

    Attributes:
        ranges: Inclusive ``(start, end)`` pairs of retryable statuses.
            Validated in :meth:`__post_init__` so a typo cannot silently
            disable retries for a whole band.
        never_retry: Statuses excluded even when a range covers them. The
            explicit list wins, which is why 400 is here as well as absent
            from :data:`NEW_API_RETRY_RANGES`.
    """

    ranges: tuple[tuple[int, int], ...] = NEW_API_RETRY_RANGES
    never_retry: frozenset[int] = NEVER_RETRY_STATUSES

    def __post_init__(self) -> None:
        """Validate the ranges.

        Raises:
            ValueError: A range is malformed, out of the 100–599 band, or
                inverted.
        """
        if not self.ranges:
            raise ValueError("ranges must not be empty")
        for pair in self.ranges:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError(f"range must be a (start, end) pair, got {pair!r}")
            start, end = pair
            if not (MIN_STATUS <= start <= end <= MAX_STATUS):
                raise ValueError(
                    f"range {pair!r} must satisfy {MIN_STATUS} <= start <= end <= {MAX_STATUS}"
                )

    def is_retryable(self, status: int) -> bool:
        """Whether ``status`` is worth another channel.

        Args:
            status: The upstream HTTP status. Values outside 100–599 are
                never retryable — they are not a status the gateway can
                reason about.

        Returns:
            ``True`` when the request should fail over rather than surface
            the upstream error to the caller.
        """
        if status in self.never_retry:
            return False
        if not MIN_STATUS <= status <= MAX_STATUS:
            return False
        return any(start <= status <= end for start, end in self.ranges)

    @classmethod
    def default(cls) -> RelayRetryPolicy:
        """Return the new-api-compatible policy."""
        return cls()

    @classmethod
    def server_errors_only(cls) -> RelayRetryPolicy:
        """Return the conservative 5xx-only policy.

        This is what the gateway did before the ranges existed; it stays
        available so a deployment can opt out of cross-channel failover on
        4xx without forking the type.
        """
        return cls(ranges=SERVER_ERROR_RANGES, never_retry=frozenset())


__all__ = [
    "MAX_STATUS",
    "MIN_STATUS",
    "NEVER_RETRY_STATUSES",
    "NEW_API_RETRY_RANGES",
    "SERVER_ERROR_RANGES",
    "RelayRetryPolicy",
]
