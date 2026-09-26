"""Condition evaluators for ABAC Policy Engine."""

from __future__ import annotations

import re
import threading
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.auth.policies.types import Condition


class OperatorHandlerProtocol(Protocol):
    """Protocol for operator handlers."""

    def compare(self, actual: Any, expected: Any) -> bool:
        """Compare actual value against expected."""
        ...


class EqualsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return cast("bool", actual == expected)


class NotEqualsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return cast("bool", actual != expected)


class ContainsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return expected in actual


class NotContainsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return expected not in actual


class InOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual in expected


class NotInOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual not in expected


class MatchesOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return bool(re.match(str(expected), str(actual)))


class GreaterThanOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return cast("bool", actual > expected)
        except TypeError:
            return False


class LessThanOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return cast("bool", actual < expected)
        except TypeError:
            return False


class GreaterThanOrEqualsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return cast("bool", actual >= expected)
        except TypeError:
            return False


class LessThanOrEqualsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return cast("bool", actual <= expected)
        except TypeError:
            return False


class OperatorRegistry:
    """Registry for condition operators."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[str, OperatorHandlerProtocol] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, OperatorHandlerProtocol]:
        """Declare the standard operator handlers."""
        return {
            "equals": EqualsOperator(),
            "not_equals": NotEqualsOperator(),
            "contains": ContainsOperator(),
            "not_contains": NotContainsOperator(),
            "in": InOperator(),
            "not_in": NotInOperator(),
            "matches": MatchesOperator(),
            "greater_than": GreaterThanOperator(),
            "less_than": LessThanOperator(),
            "greater_than_or_equals": GreaterThanOrEqualsOperator(),
            "less_than_or_equals": LessThanOrEqualsOperator(),
        }

    @classmethod
    def with_defaults(cls) -> OperatorRegistry:
        """Create a registry pre-loaded with the standard operator handlers."""
        instance = cls()
        instance._handlers = dict(cls._default_entries())
        return instance

    def register_handler(self, operator: str, handler: OperatorHandlerProtocol) -> None:
        """Register a custom operator handler."""
        with self._lock:
            self._handlers[operator] = handler

    def compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare using the registered handler for the operator."""
        with self._lock:
            handler = self._handlers.get(operator)
        if handler:
            return handler.compare(actual, expected)
        return False


class ConditionEvaluator:
    """Evaluates individual policy conditions against a request context."""

    def __init__(self) -> None:
        self._operator_registry = OperatorRegistry.with_defaults()
        # Cache compiled accessor functions keyed by attribute path string.
        # Each accessor is a Callable[[Any], Any] that traverses the path
        # without re-splitting on every evaluation call.
        self._path_cache: dict[str, Callable[[Any], Any]] = {}

    @staticmethod
    def _compile_path(path: str) -> Callable[[Any], Any]:
        """Compile an attribute path string into a reusable accessor function.

        Args:
            path: Dot-separated attribute path, e.g. ``"user.department"``.

        Returns:
            A callable that accepts a context dict or object and traverses
            the path, returning ``None`` if any segment is absent.
        """
        parts = path.split(".")

        def accessor(obj: Any) -> Any:
            current = obj
            for part in parts:
                if isinstance(current, dict):
                    if part not in current:
                        return None
                    current = current[part]
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return None
            return current

        return accessor

    def evaluate(self, condition: Condition, context: dict[str, Any]) -> bool:
        """Evaluate a single condition against the context."""
        actual_val = self._resolve_attribute(condition.attribute, context)

        # Variable substitution in expected value (e.g., "expected": "${user.id}")
        expected_val = condition.value
        if (
            isinstance(expected_val, str)
            and expected_val.startswith("${")
            and expected_val.endswith("}")
        ):
            var_path = expected_val[2:-1]
            expected_val = self._resolve_attribute(var_path, context)

        return self._operator_registry.compare(
            actual_val,
            condition.operator,
            expected_val,
        )

    def _resolve_attribute(self, path: str, context: dict[str, Any]) -> Any:
        """Resolve a nested attribute from the context using a cached accessor."""
        accessor = self._path_cache.get(path)
        if accessor is None:
            accessor = self._compile_path(path)
            self._path_cache[path] = accessor
        return accessor(context)


__all__ = [
    "ConditionEvaluator",
    "ContainsOperator",
    "EqualsOperator",
    "GreaterThanOperator",
    "GreaterThanOrEqualsOperator",
    "InOperator",
    "LessThanOperator",
    "LessThanOrEqualsOperator",
    "MatchesOperator",
    "NotContainsOperator",
    "NotEqualsOperator",
    "NotInOperator",
    "OperatorHandlerProtocol",
    "OperatorRegistry",
]
