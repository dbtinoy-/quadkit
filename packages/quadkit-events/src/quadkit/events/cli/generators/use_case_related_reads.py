"""Closed related-row reads; repository scope and authorization belong to the app."""

from collections.abc import Mapping
from dataclasses import dataclass
from keyword import iskeyword
import re

from quadkit.codegen import FieldSpec, annotation_for


@dataclass(frozen=True, slots=True)
class RelatedRead:
    """One required key and an explicit allowlist of snapshot fields."""

    name: str
    key: str
    fields: tuple[str, ...]


def _name(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None
        and not iskeyword(value)
    )


def compile_related_reads(
    spec: Mapping[str, object], fields: list[FieldSpec]
) -> list[RelatedRead]:
    """Reject ambiguous lookups before rendering, including during dry runs.

    Only declared required string/UUID inputs may supply keys. No chained reads,
    related writes, implicit relationship discovery or arbitrary expressions.
    """
    raw = spec.get("related_reads")
    if raw is None:
        return []
    if type(raw) is not list:
        raise ValueError("related_reads must be a list")
    if raw and spec.get("validate_inputs") is not True:
        raise ValueError("related reads require validate_inputs")
    inputs = {field.name: field for field in fields}
    reads: list[RelatedRead] = []
    names: set[str] = set()
    for item in raw:
        if type(item) is not dict or set(item) != {"name", "key", "fields"}:
            raise ValueError("related reads require name, key and fields")
        name, key, selected = item["name"], item["key"], item["fields"]
        if not _name(name) or name in names:
            raise ValueError(
                "related read names must be unique public ASCII identifiers"
            )
        if (
            not isinstance(key, str)
            or not key.startswith("input.")
            or not _name(key[6:])
            or key[6:] not in inputs
            or not inputs[key[6:]].required
            or annotation_for(inputs[key[6:]].type) not in {"str", "UUID"}
        ):
            raise ValueError(
                "related key must name a declared required string/UUID input"
            )
        if (
            type(selected) is not list
            or not selected
            or any(not _name(field) for field in selected)
            or len(set(selected)) != len(selected)
        ):
            raise ValueError("related fields require unique public ASCII identifiers")
        names.add(name)
        reads.append(RelatedRead(name, key[6:], tuple(selected)))
    return reads
