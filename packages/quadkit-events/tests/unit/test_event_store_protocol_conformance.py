"""Signature conformance between EventStoreProtocol and every shipped store.

The DI container only checks member *presence* when binding, so a protocol
whose method signature disagrees with its implementations binds cleanly and
never fails at startup. That is how slice S23 stayed open: the protocol said
``read(stream_id, start, count)`` while all eight stores said
``read(stream_id, from_version, to_version, limit)``, and the only symptom in
the whole tree was a ``type: ignore[call-arg]`` at a call site.

These tests make that class of drift a test failure instead of a silent bind.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from quadkit.contracts.events.protocols import EventStoreProtocol
from quadkit.events.stores.base import AbstractEventStore
from quadkit.events.stores.memory import InMemoryEventStore
from quadkit.events.stores.mongodb.event_store import MongoDBEventStore
from quadkit.events.stores.outbox import OutboxEventStore
from quadkit.events.stores.postgres.event_store import PostgresEventStore
from quadkit.events.stores.redis import RedisEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.stores.streaming import StreamingEventStore

STORES: tuple[tuple[str, type[Any]], ...] = (
    ("AbstractEventStore", AbstractEventStore),
    ("InMemoryEventStore", InMemoryEventStore),
    ("MongoDBEventStore", MongoDBEventStore),
    ("OutboxEventStore", OutboxEventStore),
    ("PostgresEventStore", PostgresEventStore),
    ("RedisEventStore", RedisEventStore),
    ("SqliteEventStore", SqliteEventStore),
    ("StreamingEventStore", StreamingEventStore),
)


def _protocol_methods() -> dict[str, inspect.Signature]:
    """Public coroutine members declared by EventStoreProtocol."""
    out: dict[str, inspect.Signature] = {}
    for name in dir(EventStoreProtocol):
        if name.startswith("_"):
            continue
        member = getattr(EventStoreProtocol, name, None)
        if not inspect.iscoroutinefunction(member):
            continue
        sig = inspect.signature(member)
        out[name] = sig
    return out


def _params(sig: inspect.Signature) -> list[str]:
    """Positional-or-keyword parameter names, excluding ``self``."""
    return [
        p.name
        for p in sig.parameters.values()
        if p.name != "self" and p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]


def _defaults(sig: inspect.Signature) -> dict[str, Any]:
    return {
        p.name: p.default
        for p in sig.parameters.values()
        if p.default is not inspect.Parameter.empty
    }


@pytest.fixture
def protocol_methods() -> dict[str, inspect.Signature]:
    return _protocol_methods()


@pytest.mark.parametrize(
    ("store_name", "store_cls"), STORES, ids=[n for n, _ in STORES]
)
def test_every_store_exposes_every_protocol_member(
    store_name: str,
    store_cls: type[Any],
    protocol_methods: dict[str, inspect.Signature],
) -> None:
    """No store may be missing a member the protocol promises."""
    for name in protocol_methods:
        assert hasattr(store_cls, name), f"{store_name} is missing {name}()"


@pytest.mark.parametrize(
    ("store_name", "store_cls"), STORES, ids=[n for n, _ in STORES]
)
def test_parameter_names_match_the_protocol(
    store_name: str,
    store_cls: type[Any],
    protocol_methods: dict[str, inspect.Signature],
) -> None:
    """A keyword call that binds against the protocol must bind on the store.

    The protocol's parameter names are the contract. If a store renames one, a
    caller written against the protocol raises ``TypeError`` at runtime -- and
    the container never notices.
    """
    failures: list[str] = []
    for name, proto_sig in protocol_methods.items():
        impl = getattr(store_cls, name, None)
        if impl is None or not callable(impl):
            continue
        impl_sig = inspect.signature(impl)
        impl_params = _params(impl_sig)
        for wanted in _params(proto_sig):
            if wanted in impl_params:
                continue
            # ``**kwargs`` is an acceptable escape hatch: anything binds.
            if any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                for p in impl_sig.parameters.values()
            ):
                continue
            failures.append(
                f"{store_name}.{name}() has no parameter '{wanted}' "
                f"(it takes: {impl_params})"
            )
    assert not failures, (
        "protocol/implementation signature drift (the S23 defect class):\n  "
        + "\n  ".join(failures)
    )


@pytest.mark.parametrize(
    ("store_name", "store_cls"), STORES, ids=[n for n, _ in STORES]
)
def test_protocol_defaults_are_accepted_by_every_store(
    store_name: str,
    store_cls: type[Any],
    protocol_methods: dict[str, inspect.Signature],
) -> None:
    """A call that binds against the protocol must not fail on a missing arg.

    The defect worth catching is one-directional: the protocol says a parameter
    is optional, but the store requires it. A parameter that is required in
    *both* is perfectly consistent and must not be reported.
    """
    failures: list[str] = []
    for name, proto_sig in protocol_methods.items():
        impl = getattr(store_cls, name, None)
        if impl is None or not callable(impl):
            continue
        impl_sig = inspect.signature(impl)
        impl_defaults = _defaults(impl_sig)
        impl_params = _params(impl_sig)
        proto_params = _params(proto_sig)
        proto_defaults = _defaults(proto_sig)
        if any(
            p.kind is inspect.Parameter.VAR_KEYWORD
            for p in impl_sig.parameters.values()
        ):
            continue
        for param in impl_params:
            if param in impl_defaults:
                continue  # store tolerates omission
            if param not in proto_params:
                failures.append(
                    f"{store_name}.{name}() requires '{param}', which the protocol "
                    "does not declare at all"
                )
            elif param in proto_defaults:
                failures.append(
                    f"{store_name}.{name}() requires '{param}', but the protocol "
                    f"declares it optional (default={proto_defaults[param]!r})"
                )
    assert not failures, (
        "protocol/implementation arity drift (the S23 defect class):\n  "
        + "\n  ".join(failures)
    )


def test_read_uses_the_canonical_version_names() -> None:
    """Pin the canonical ``read`` signature explicitly.

    Eight implementations agree on these names; this keeps the protocol the odd
    one out from ever happening again.
    """
    params = _params(inspect.signature(EventStoreProtocol.read))
    assert params == ["stream_id", "from_version", "to_version", "limit"], params


def test_no_caller_in_the_tree_suppresses_a_signature_error() -> None:
    """The S23 symptom was ``type: ignore[call-arg]`` hiding at a call site."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    offenders = [
        f"{path.relative_to(root)}:{no}: {line.strip()}"
        for path in sorted(root.rglob("*.py"))
        for no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if "type: ignore[call-arg]" in line and "_event_store.read(" in line
    ]
    assert not offenders, (
        "an event-store read() call is silencing a signature mismatch:\n  "
        + "\n  ".join(offenders)
    )
