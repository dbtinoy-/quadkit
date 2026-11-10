"""Compile the explicit shared-data permission policy; no expression language."""

from __future__ import annotations

import re

_LITERAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def shared_policy_context(spec: object) -> dict[str, object]:
    """Refuse incomplete/unknown declarations before staging even a dry run."""
    if type(spec) is not dict or set(spec) != {
        "mode",
        "required_permission",
        "resources",
    }:
        raise ValueError(
            "Shared policy requires only mode, required_permission and resources"
        )
    if type(spec["mode"]) is not str or spec["mode"] != "shared_authenticated":
        raise ValueError("Only explicit shared_authenticated policy mode is supported")
    permission = spec["required_permission"]
    resources = spec["resources"]
    if type(permission) is not str or _LITERAL.fullmatch(permission) is None:
        raise ValueError("A literal non-wildcard required permission is required")
    if (
        type(resources) is not list
        or not 1 <= len(resources) <= 32
        or any(
            type(value) is not str or _LITERAL.fullmatch(value) is None
            for value in resources
        )
        or len(set(resources)) != len(resources)
    ):
        raise ValueError("Shared resources must be 1..32 unique literal identifiers")
    return {
        "required_permission": repr(permission),
        "resources": repr(tuple(resources)),
    }
