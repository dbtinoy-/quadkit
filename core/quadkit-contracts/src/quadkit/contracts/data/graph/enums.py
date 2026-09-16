"""Graph store enumerations."""

from __future__ import annotations

from enum import StrEnum


class EdgeDirection(StrEnum):
    """Direction for edge traversal."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class ReturnType(StrEnum):
    """What a traversal query returns."""

    NODES = "nodes"
    EDGES = "edges"
    PATHS = "paths"
    COUNT = "count"


class IndexKind(StrEnum):
    """Type of graph index."""

    BTREE = "btree"
    FULLTEXT = "fulltext"
    RANGE = "range"
    POINT = "point"
    TEXT = "text"
    VECTOR = "vector"


class ConstraintKind(StrEnum):
    """Type of graph schema constraint."""

    UNIQUE = "unique"
    EXISTS = "exists"
    NODE_KEY = "node_key"


class MergeAction(StrEnum):
    """Behavior when a merge finds an existing node/edge."""

    CREATE = "create"
    MATCH = "match"
    MERGE = "merge"


__all__ = [
    "ConstraintKind",
    "EdgeDirection",
    "IndexKind",
    "MergeAction",
    "ReturnType",
]
