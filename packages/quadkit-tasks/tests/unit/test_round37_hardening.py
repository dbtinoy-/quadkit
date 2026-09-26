"""Round 37 hardening pins — driver errors must degrade per the tasks contract.

Compute.reset — shutting down the compute pool that fails with a
non-builtin driver error must not raise (test-isolation teardown).

Run with: pytest tests/unit/test_round37_hardening.py -v
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from quadkit.tasks.concurrency.facade import Compute


class _DriverError(Exception):
    """Stand-in for a driver/SDK error type (not OSError/RuntimeError)."""


class TestComputeReset:
    def test_pool_shutdown_driver_error_is_swallowed(self) -> None:
        pool = MagicMock()
        pool.shutdown = MagicMock(side_effect=_DriverError("pool wedged"))

        # Deterministic branch: a non-running current loop makes reset()
        # take the run_until_complete() path instead of the fire-and-forget
        # task path (whose branch depends on suite event-loop state).
        # pytest-asyncio leaves the policy loop unset in sync tests, so
        # install an explicit one and clean it up.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        Compute._pool = pool
        try:
            # Must not raise — reset is best-effort teardown.
            Compute.reset()
        finally:
            Compute._pool = None
            loop.close()
            asyncio.set_event_loop(None)

        pool.shutdown.assert_called_once()
