"""Identity generator implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from secrets import randbits
from uuid import UUID, uuid4

from quadkit.contracts.core.identity import IdStrategy
from quadkit.identity.constants import DEFAULT_PREFIX_SEPARATOR, DEFAULT_ULID_LENGTH
from quadkit.primitives import clock as ambient_clock

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, width: int) -> str:
    chars = ["0"] * width
    current = value
    for index in range(width - 1, -1, -1):
        chars[index] = _CROCKFORD_ALPHABET[current & 0b11111]
        current >>= 5
    return "".join(chars)


def _timestamp_ms() -> int:
    return int(ambient_clock.timestamp() * 1000.0)


class Uuid4Generator:
    """Random UUID4 generator."""

    @property
    def strategy(self) -> IdStrategy:
        return IdStrategy.UUID4

    def generate(self) -> str:
        return str(uuid4())

    def generate_for(self, entity_type: str) -> str:
        return self.generate()


class Uuid7Generator:
    """Time-ordered UUID7 generator."""

    @property
    def strategy(self) -> IdStrategy:
        return IdStrategy.UUID7

    def generate(self) -> str:
        timestamp_ms = _timestamp_ms()
        rand_a = randbits(12)
        rand_b = randbits(62)
        value = (
            (timestamp_ms & ((1 << 48) - 1)) << 80
            | (0x7 << 76)
            | (rand_a << 64)
            | (0b10 << 62)
            | rand_b
        )
        return str(UUID(int=value))

    def generate_for(self, entity_type: str) -> str:
        return self.generate()


class UlidGenerator:
    """ULID generator with Crockford base32 encoding."""

    @property
    def strategy(self) -> IdStrategy:
        return IdStrategy.ULID

    def generate(self) -> str:
        timestamp_ms = _timestamp_ms()
        randomness = randbits(80)
        return _encode_base32(timestamp_ms, 10) + _encode_base32(
            randomness, DEFAULT_ULID_LENGTH - 10
        )

    def generate_for(self, entity_type: str) -> str:
        return self.generate()


@dataclass(slots=True)
class PrefixedIdGenerator:
    """Prefixed ULID generator."""

    prefix_map: dict[str, str] | None = None
    separator: str = DEFAULT_PREFIX_SEPARATOR
    _ulid: UlidGenerator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.prefix_map is None:
            self.prefix_map = {}
        self._ulid = UlidGenerator()

    @property
    def strategy(self) -> IdStrategy:
        return IdStrategy.PREFIXED

    def generate(self) -> str:
        return self._ulid.generate()

    def generate_for(self, entity_type: str) -> str:
        prefix_map = self.prefix_map
        prefix = prefix_map.get(entity_type) if prefix_map else None
        if prefix is None:
            prefix = entity_type.strip().lower()[:3]
        return f"{prefix}{self.separator}{self._ulid.generate()}"


__all__ = [
    "PrefixedIdGenerator",
    "UlidGenerator",
    "Uuid4Generator",
    "Uuid7Generator",
]
