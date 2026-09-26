from quadkit.events import (
    EventBusImpl,
    EventBusProtocol,
    AbstractEventStore,
    EventStoreProtocol,
    AbstractRepository,
    RepositoryProtocol,
)


def test_protocol_aliases_available():
    # Concrete class names and protocol aliases should both be importable
    assert EventBusImpl is not None
    assert EventBusProtocol is not None
    assert AbstractEventStore is not None
    assert EventStoreProtocol is not None
    assert AbstractRepository is not None
    assert RepositoryProtocol is not None
