"""Compile bounded integer deltas, never executable arithmetic expressions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from keyword import iskeyword


@dataclass(frozen=True, slots=True)
class Counter:
    """A closed, SQL Integer-compatible update owned by one aggregate."""

    field: str
    delta: int
    minimum: int
    maximum: int


def _identifier(value: object) -> bool:
    return (
        type(value) is str
        and value.isascii()
        and value.isidentifier()
        and not value.startswith("_")
        and not iskeyword(value)
    )


def compile_counters(spec: Mapping[str, object]) -> list[Counter]:
    """Validate a standalone counter spec before rendering or staging files.

    The caller still owns aggregate field visibility/type/assignment validation.
    Counter handlers require explicit repository CAS capability at runtime.
    """
    raw = spec.get("counters")
    if raw is None:
        return []
    if type(raw) is not list:
        raise ValueError("use_case counters must be a list")
    if not raw:
        return []
    transition = spec.get("transition")
    if (
        spec.get("atomic_transition") is not True
        or not isinstance(transition, dict)
        or not _identifier(transition.get("field"))
        or type(transition.get("from")) is not str
        or type(transition.get("to")) is not str
    ):
        raise ValueError(
            "use_case counters require an explicit atomic string transition"
        )
    occupied = {"id", "created_at", "updated_at", "deleted_at", transition["field"]}
    writes = spec.get("writes") or ()
    if not isinstance(writes, (list, tuple)):
        raise TypeError("use_case counters require a list of non-overlapping writes")
    for write in writes:
        if not isinstance(write, dict) or type(write.get("field")) is not str:
            raise ValueError("use_case counters require named, non-overlapping writes")
        occupied.add(write["field"])
    counters: list[Counter] = []
    for item in raw:
        if type(item) is not dict or set(item) != {
            "field",
            "delta",
            "minimum",
            "maximum",
        }:
            raise ValueError(
                "use_case counter requires only field, delta, minimum, maximum"
            )
        name, delta, low, high = (
            item[k] for k in ("field", "delta", "minimum", "maximum")
        )
        if not _identifier(name) or name in occupied:
            raise ValueError(
                "use_case counter field must be public, unique and not overlap writes or state"
            )
        if any(
            type(value) is not int or not -(2**31) <= value < 2**31
            for value in (delta, low, high)
        ):
            raise ValueError(
                "use_case counter delta and bounds must be signed32-bit integers"
            )
        if delta == 0 or low > high or abs(delta) > high - low:
            raise ValueError(
                "use_case counter must have a nonzero delta and reachable bounds"
            )
        occupied.add(name)
        counters.append(Counter(name, delta, low, high))
    return sorted(counters, key=lambda counter: counter.field)
