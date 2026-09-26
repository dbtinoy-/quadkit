"""P2-event-bus-exc: Event bus except clause must not carry redundant exception types."""

from __future__ import annotations

import inspect

import quadkit.events.buses.event as event_module


class TestEventBusNoRedundantExceptionTypes:
    """P2: Listing RuntimeError/TypeError/ValueError/OSError before Exception is redundant."""

    def test_redundant_multi_type_tuple_absent_from_drain_queue(self) -> None:
        """The drain-queue except tuple must not list types subsumed by Exception.

        The unique fingerprint of the buggy code is TypeError + ValueError + OSError
        all appearing sequentially in the same except tuple as Exception.  That exact
        multi-line pattern cannot appear anywhere else in the file.
        """
        source = inspect.getsource(event_module)
        # This exact four-type sequence is unique to the buggy except tuple.
        buggy_pattern = "TypeError,\n                        ValueError,\n                        OSError,\n                        Exception,"
        assert buggy_pattern not in source, (
            "Drain-queue except clause still contains redundant types before Exception"
        )

    def test_except_exception_as_exc_present(self) -> None:
        """The drain-queue error handler must still catch Exception (as exc)."""
        source = inspect.getsource(event_module)
        assert "except Exception as exc:" in source, (
            "Drain-queue error handler must use 'except Exception as exc:'"
        )
