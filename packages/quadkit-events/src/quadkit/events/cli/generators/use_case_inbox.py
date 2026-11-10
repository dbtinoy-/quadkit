"""Compile an explicit fixed-account, transactional inbox intent.

No recipient/expression language: the host supplies the native channel, and the
SQL repository must implement the separately advertised atomic enqueue seam.
"""

from __future__ import annotations

from keyword import iskeyword
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quadkit.codegen import FieldSpec


def compile_inbox_notification(
    spec: dict[str, Any], fields: Sequence[FieldSpec]
) -> dict[str, str] | None:
    """Reject incomplete or ambiguous opt-ins, including during dry runs."""
    raw = spec.get("inbox_notification")
    if raw is None:
        return None
    if type(raw) is not dict or set(raw) != {"title", "body_field"}:
        raise ValueError("inbox_notification requires only title and body_field")
    title, body_field = raw["title"], raw["body_field"]
    if (
        type(title) is not str
        or not title.strip()
        or len(title) > 120
        or "\x00" in title
    ):
        raise ValueError(
            "inbox_notification title must be nonempty storage text <=120 characters"
        )
    try:
        title.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("inbox_notification title must be UTF-8 text") from exc
    if (
        type(body_field) is not str
        or not body_field.isascii()
        or not body_field.isidentifier()
        or iskeyword(body_field)
        or body_field.startswith("_")
    ):
        raise ValueError(
            "inbox_notification body_field must be an aggregate field identifier"
        )
    # Copy a value that this same conditional update actually persists. A
    # pre-read-only snapshot could become stale before the state CAS succeeds.
    writes = spec.get("writes")
    if not isinstance(writes, (list, tuple)) or not any(
        type(write) is dict
        and write.get("field") == body_field
        and any(
            write.get("source") == f"input.{field.name}"
            and field.type == "str"
            and field.required
            for field in fields
        )
        for write in writes
    ):
        raise ValueError(
            "inbox_notification body_field requires a required string input write"
        )
    if not all(
        spec.get(key) is True
        for key in (
            "atomic_transition",
            "principal_required",
            "validate_inputs",
            "typed_outcomes",
        )
    ) or not spec.get("transition"):
        raise ValueError(
            "inbox_notification requires a validated, principal-bound typed atomic transition"
        )
    if any(
        spec.get(key)
        for key in ("stages", "enqueues", "related_reads", "counters", "custom_steps")
    ):
        raise ValueError(
            "inbox_notification does not compose other effects, counters or custom work"
        )
    return {"title": title, "body_field": body_field}
