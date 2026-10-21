"""Per-label-set series bookkeeping shared by the metric implementations.

The collector's metrics keep a bounded window of observations, which is the
right shape for dashboards ("what happened recently") but the wrong shape for
Prometheus exposition ("what is this series' value now"): a label set whose
last sample has aged out of the window would vanish from a scrape.  Each
metric type therefore also accumulates a per-label-set view, keyed by the
canonical label key produced here.
"""

from __future__ import annotations

__all__ = ["SeriesKey", "series_key"]

#: Canonical, hashable representation of a label set: sorted ``(name, value)``
#: pairs, so ``{"b": "2", "a": "1"}`` and ``{"a": "1", "b": "2"}`` are one key.
SeriesKey = tuple[tuple[str, str], ...]


def series_key(labels: dict[str, str]) -> SeriesKey:
    """Return a canonical key for *labels* (sorted, order-independent)."""
    return tuple(sorted(labels.items()))
