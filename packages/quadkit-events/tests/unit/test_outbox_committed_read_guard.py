"""Relay consumes the shared guard without knowledge of concrete SQL adapters."""

import pytest

from quadkit.contracts.data.sql.committed_reads import CommittedReadState
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.outbox import OutboxPublisher


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (CommittedReadState.UNSUPPORTED_PROVIDER, "verified SQL provider"),
        (CommittedReadState.UNSUPPORTED_POOL, "verified connection pool"),
        (CommittedReadState.UNOBSERVABLE_TRANSACTION, "observable transaction"),
        (CommittedReadState.IN_TRANSACTION, "within a database transaction"),
        (True, "verified SQL provider"),
        ("safe", "verified SQL provider"),
        (None, "verified SQL provider"),
        ([], "verified SQL provider"),
    ],
)
def test_negative_or_malformed_guard_is_refused(state: object, message: str) -> None:
    class Adapter:
        supports_committed_read_guard_v1 = True

        def committed_read_state(self) -> object:
            return state

    with pytest.raises(EventStoreError, match=message):
        OutboxPublisher._ensure_outside_transaction(Adapter())


@pytest.mark.parametrize("marker", [None, False, 1, "true"])
def test_marker_is_strict_and_old_marker_is_insufficient(marker: object) -> None:
    class Adapter:
        supports_outbox_committed_reads_v1 = True
        supports_committed_read_guard_v1 = marker

        def committed_read_state(self) -> CommittedReadState:
            pytest.fail("invalid capability must not invoke the adapter")

    with pytest.raises(EventStoreError, match="verified SQL provider"):
        OutboxPublisher._ensure_outside_transaction(Adapter())


def test_raising_guard_does_not_escape_as_success() -> None:
    class Adapter:
        supports_committed_read_guard_v1 = True

        def committed_read_state(self) -> CommittedReadState:
            raise RuntimeError("cannot inspect lease")

    with pytest.raises(EventStoreError, match="inspection failed") as error:
        OutboxPublisher._ensure_outside_transaction(Adapter())
    assert isinstance(error.value.__cause__, RuntimeError)


def test_safe_contract_and_missing_method() -> None:
    class Adapter:
        supports_committed_read_guard_v1 = True

        def committed_read_state(self) -> CommittedReadState:
            return CommittedReadState.SAFE

    class Missing:
        supports_committed_read_guard_v1 = True

    OutboxPublisher._ensure_outside_transaction(Adapter())
    with pytest.raises(EventStoreError, match="verified SQL provider"):
        OutboxPublisher._ensure_outside_transaction(Missing())


def test_async_or_noncallable_hooks_are_rejected_without_invocation() -> None:
    class AsyncAdapter:
        supports_committed_read_guard_v1 = True

        async def committed_read_state(self) -> CommittedReadState:
            pytest.fail("a synchronous inspection must not create a coroutine")

    class NoncallableAdapter:
        supports_committed_read_guard_v1 = True
        committed_read_state = True

    for adapter in (AsyncAdapter(), NoncallableAdapter()):
        with pytest.raises(EventStoreError, match="verified SQL provider"):
            OutboxPublisher._ensure_outside_transaction(adapter)
