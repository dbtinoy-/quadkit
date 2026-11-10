"""Compile explicit scalar target checks for related snapshot writes."""

from collections.abc import Mapping
from dataclasses import dataclass
import math

from quadkit.events.cli.generators.use_case_related_reads import RelatedRead


@dataclass(frozen=True, slots=True)
class RelatedWriteCheck:
    """Validated, data-only target metadata for generated pre-write checks."""

    field: str
    expression: str
    kind: str
    nullable: bool
    min_length: int | None
    max_length: int | None
    minimum: int | float | None
    maximum: int | float | None
    options: tuple[str, ...] | None


def _finite(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def compile_related_write_checks(
    spec: Mapping[str, object], reads: list[RelatedRead]
) -> list[RelatedWriteCheck]:
    """Opt in explicitly; once supplied, cover every related write exactly once.

    Legacy standalone specs without this key remain unchecked. The caller owns
    truth of target metadata; no database discovery or authorization is implied.
    """
    if "related_write_checks" not in spec:
        return []
    raw = spec["related_write_checks"]
    if type(raw) is not list or spec.get("validate_inputs") is not True:
        raise ValueError("related_write_checks requires a list and validate_inputs")
    writes = spec.get("writes") or []
    if not isinstance(writes, (list, tuple)) or any(
        type(w) is not dict for w in writes
    ):
        raise ValueError("related write checks require explicit writes")
    selected = {r.name: r.fields for r in reads}
    sources: dict[str, str] = {}
    for write in writes:
        source = write.get("source")
        if not isinstance(source, str) or not source.startswith("related."):
            continue
        target = write.get("field")
        parts = source.split(".")
        if (
            not isinstance(target, str)
            or sum(w.get("field") == target for w in writes) != 1
            or len(parts) != 3
            or parts[1] not in selected
            or parts[2] not in selected[parts[1]]
        ):
            raise ValueError(
                "related write checks need unique targets and allowlisted sources"
            )
        sources[target] = f"related_rows[{parts[1]!r}][{parts[2]!r}]"
    checks = []
    seen: set[str] = set()
    for item in raw:
        if type(item) is not dict or set(item) - {
            "field",
            "type",
            "nullable",
            "min_length",
            "max_length",
            "minimum",
            "maximum",
            "enum",
        }:
            raise ValueError("malformed related write check")
        field, kind, nullable = (
            item.get("field"),
            item.get("type"),
            item.get("nullable"),
        )
        if (
            not isinstance(field, str)
            or field not in sources
            or field in seen
            or not isinstance(kind, str)
            or kind not in {"str", "int", "float", "bool"}
            or type(nullable) is not bool
        ):
            raise ValueError(
                "related write checks require unique targets, scalar types and explicit nullability"
            )
        low_len, high_len = item.get("min_length"), item.get("max_length")
        low, high, options = item.get("minimum"), item.get("maximum"), item.get("enum")
        if any(
            v is not None and (type(v) is not int or v < 0) for v in (low_len, high_len)
        ) or (low_len is not None and high_len is not None and low_len > high_len):
            raise ValueError(
                "related write length bounds must be nonnegative and ordered"
            )
        if kind != "str" and any(v is not None for v in (low_len, high_len, options)):
            raise ValueError("related write text constraints require str")
        if any(v is not None and not _finite(v) for v in (low, high)) or (
            kind not in {"int", "float"} and any(v is not None for v in (low, high))
        ):
            raise ValueError(
                "related write numeric bounds require finite numeric values"
            )
        if (
            low is not None
            and high is not None
            and (low > high or (kind == "int" and math.ceil(low) > math.floor(high)))
        ):
            raise ValueError("related write numeric bounds have no allowed value")
        if options is not None:
            if (
                type(options) is not list
                or not options
                or any(type(v) is not str or "\x00" in v for v in options)
            ):
                raise ValueError(
                    "related write enum requires nonempty storage-safe strings"
                )
            try:
                for value in options:
                    value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("related write enum requires UTF-8") from exc
        seen.add(field)
        checks.append(
            RelatedWriteCheck(
                field,
                sources[field],
                kind,
                nullable,
                low_len,
                high_len,
                low,
                high,
                tuple(options) if options is not None else None,
            )
        )
    if seen != set(sources):
        raise ValueError("related write checks must cover every related write")
    return checks
