"""Tests for identity generators (UUID4/UUID7/ULID/prefixed) and the
ambient generator context."""

from __future__ import annotations

import time
from uuid import UUID

import pytest

from quadkit.contracts.core.identity import IdStrategy
from quadkit.identity import ambient
from quadkit.identity.constants import DEFAULT_PREFIX_SEPARATOR, DEFAULT_ULID_LENGTH
from quadkit.identity.generator import (
    PrefixedIdGenerator,
    UlidGenerator,
    Uuid4Generator,
    Uuid7Generator,
)

# ── UUID4 ─────────────────────────────────────────────────────────────────


def test_uuid4_generator() -> None:
    gen = Uuid4Generator()
    assert gen.strategy is IdStrategy.UUID4

    value = gen.generate()
    parsed = UUID(value)
    assert parsed.version == 4
    assert gen.generate_for("User") != gen.generate_for("User")  # random


# ── UUID7 ─────────────────────────────────────────────────────────────────


def test_uuid7_generator_time_ordered() -> None:
    gen = Uuid7Generator()
    assert gen.strategy is IdStrategy.UUID7

    a = UUID(gen.generate())
    assert a.version == 7

    # Time-ordered: a second generated after a short sleep sorts later.
    time.sleep(0.002)
    b = UUID(gen.generate())
    assert b > a

    # generate_for uses the same scheme.
    c = UUID(gen.generate_for("Order"))
    assert c.version == 7


# ── ULID ──────────────────────────────────────────────────────────────────


def test_ulid_generator_shape() -> None:
    gen = UlidGenerator()
    assert gen.strategy is IdStrategy.ULID

    value = gen.generate()
    assert len(value) == DEFAULT_ULID_LENGTH
    # Crockford base32 alphabet (no I, L, O, U).
    assert all(ch in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for ch in value)

    # Timestamp-ordered: monotonic under a short sleep.
    time.sleep(0.002)
    assert gen.generate() > value


# ── Prefixed ──────────────────────────────────────────────────────────────


def test_prefixed_generator_with_map() -> None:
    gen = PrefixedIdGenerator(prefix_map={"user": "usr"})
    assert gen.strategy is IdStrategy.PREFIXED

    value = gen.generate_for("user")
    prefix, _, remainder = value.partition(DEFAULT_PREFIX_SEPARATOR)
    assert prefix == "usr"
    assert len(remainder) == DEFAULT_ULID_LENGTH


def test_prefixed_generator_unmapped_entity() -> None:
    gen = PrefixedIdGenerator()

    value = gen.generate_for("  Order  ")
    prefix, _, remainder = value.partition(DEFAULT_PREFIX_SEPARATOR)
    # Default: first three chars of the stripped, lowercased name.
    assert prefix == "ord"
    assert len(remainder) == DEFAULT_ULID_LENGTH

    # Bare generate() is an unprefixed ULID.
    assert len(gen.generate()) == DEFAULT_ULID_LENGTH


def test_prefixed_generator_custom_separator() -> None:
    gen = PrefixedIdGenerator(prefix_map={"u": "U"}, separator="-")
    assert gen.generate_for("u").startswith("U-")


# ── Ambient context ───────────────────────────────────────────────────────


class _CounterGenerator(Uuid4Generator):
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.calls = 0

    def generate(self) -> str:
        self.calls += 1
        return f"{self.tag}-{super().generate()}"


def test_ambient_install_and_generate_for() -> None:
    original = ambient._ambient.get()  # noqa: SLF001
    try:
        gen = _CounterGenerator("amb")
        ambient.install(gen)
        assert ambient.generate_for("User").startswith("amb-")
        assert ambient.new_uuid().startswith("amb-")
        assert gen.calls == 2
    finally:
        ambient.install(original)


def test_ambient_use_context_stacks() -> None:
    outer = _CounterGenerator("outer")
    inner = _CounterGenerator("inner")

    with ambient.use(outer):
        assert ambient.generate_for("X").startswith("outer-")
        with ambient.use(inner):
            assert ambient.generate_for("X").startswith("inner-")
        # Restored to outer after the inner block exits.
        assert ambient.generate_for("X").startswith("outer-")

    # Restored to the original after the outer block exits.
    assert not ambient.generate_for("X").startswith(("outer-", "inner-"))


# ── What the name promises vs what the call returns ───────────────────────


def test_new_uuid_is_whatever_the_ambient_generator_is() -> None:
    """``new_uuid()`` is not a UUID unless the configured strategy is one.

    The name says UUID4 and the docstring used to agree with it, but the
    call delegates to the installed ``IdGeneratorProtocol``. An application
    that configures ULID for database locality gets a 26-character Crockford
    base32 string out of a function named ``new_uuid`` — so a ``UUID``
    column or a ``uuid.UUID()`` parse on the far end fails at runtime, not
    at boot.
    """
    with ambient.use(UlidGenerator()):
        value = ambient.new_uuid()

    assert len(value) == DEFAULT_ULID_LENGTH
    with pytest.raises(ValueError, match=r"badly formed|invalid"):
        UUID(value)


def test_new_uuid_is_not_guaranteed_unpredictable() -> None:
    """Time-ordered strategies leak their timestamp into the leading bits.

    ``SECURITY.md`` used to describe this call as "uuid4() (random)" under
    the heading *UUID predictability*, which is exactly the claim a reader
    checks before using an id as a secret. Two ULIDs minted a moment apart
    share their timestamp prefix and sort in creation order.
    """
    with ambient.use(UlidGenerator()):
        first = ambient.new_uuid()
        second = ambient.new_uuid()
        time.sleep(0.002)
        later = ambient.new_uuid()

    # Same millisecond: identical timestamp prefix, only the random tail
    # differs (the tail is not monotonic within a tick, so no ordering is
    # asserted there).
    assert first[:6] == second[:6]
    # Across a tick: the value sorts by creation time, which is the property
    # that makes it guessable.
    assert later > first
