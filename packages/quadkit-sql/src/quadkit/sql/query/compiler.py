"""Filter expression compiler for in-memory predicate evaluation.

Compiles ``FilterExpression`` values from ``quadkit.contracts.data`` into
Python callables so that in-memory repositories can apply the same filter
algebra as database-backed repositories.

The ``PredicateCompiler`` is the primary entry point.  For production backends
(SQL, Elasticsearch, etc.) extension packages implement their own compiler that
targets the query language of the underlying store.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quadkit.contracts.data.protocols import (
    AndExpr,
    FieldEq,
    FieldGt,
    FieldIn,
    FieldLt,
    FilterExpression,
    NotExpr,
    OrExpr,
)
from quadkit.sql.exceptions import DataQueryError as QueryError

Predicate = Callable[[Any], bool]


class PredicateCompiler:
    """Compiles a ``FilterExpression`` into a Python predicate function.

    The compiled predicate accepts a single object and returns ``True`` if it
    satisfies the expression.  Attribute access is performed via
    ``getattr``; missing attributes evaluate to ``None``.

    Example::

        compiler = PredicateCompiler()
        pred = compiler.compile(FieldEq(field="status", value="active"))
        active_users = [u for u in users if pred(u)]
    """

    def compile(self, expression: FilterExpression) -> Predicate:
        """Compile *expression* into a Python predicate.

        Args:
            expression: The filter expression to compile.

        Returns:
            A callable that takes a single entity and returns ``True`` when
            the entity satisfies *expression*.

        Raises:
            QueryError: If *expression* is of an unrecognised type.
        """
        match expression:
            case FieldEq(field=field, value=value):
                return lambda obj, f=field, v=value: getattr(obj, f, None) == v  # type: ignore[misc]
            case FieldGt(field=field, value=value):
                return lambda obj, f=field, v=value: (  # type: ignore[misc]
                    (val := getattr(obj, f, None)) is not None and val > v
                )
            case FieldLt(field=field, value=value):
                return lambda obj, f=field, v=value: (  # type: ignore[misc]
                    (val := getattr(obj, f, None)) is not None and val < v
                )
            case FieldIn(field=field, values=values):
                return lambda obj, f=field, vs=values: getattr(obj, f, None) in vs  # type: ignore[misc]
            case AndExpr(left=left, right=right):
                left_p = self.compile(left)
                right_p = self.compile(right)
                return lambda obj, lp=left_p, rp=right_p: lp(obj) and rp(obj)  # type: ignore[misc]
            case OrExpr(left=left, right=right):
                left_p = self.compile(left)
                right_p = self.compile(right)
                return lambda obj, lp=left_p, rp=right_p: lp(obj) or rp(obj)  # type: ignore[misc]
            case NotExpr(expr=inner):
                inner_p = self.compile(inner)
                return lambda obj, ip=inner_p: not ip(obj)  # type: ignore[misc]
            case _:
                raise QueryError(
                    f"Unsupported filter expression type: {type(expression).__name__}"
                )


__all__ = ["Predicate", "PredicateCompiler"]
