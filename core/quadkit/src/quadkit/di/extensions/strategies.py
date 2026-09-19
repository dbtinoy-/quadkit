"""Resolution strategies for dependency injection.

This module provides pluggable strategies for resolving parameters
in the call() method. Each strategy can provide values for specific
parameter types, allowing the container to handle web parameters,
environment variables, configuration, and more alongside DI services.

Example:
    Create a custom strategy::

        from quadkit.di.strategies import ResolutionStrategy

        class ConfigStrategy(ResolutionStrategy):
            def __init__(self, config: dict):
                self._config = config

            async def resolve(self, param_name, param_type, default):
                if param_name in self._config:
                    return True, self._config[param_name]
                return False, None

        # Use in call()
        strategy = ConfigStrategy({"debug": True})
        await container.call(handler, strategies=[strategy])
"""

from __future__ import annotations

from typing import Any


class ResolutionStrategy:
    """Pluggable parameter resolution for call().

    The container tries each strategy in order. The first one that
    returns a value wins. This is how quadkit-web injects path
    params, query strings, and request objects alongside DI services.
    """

    async def resolve(
        self,
        param_name: str,
        param_type: type,
        default: Any,
    ) -> tuple[bool, Any]:
        """Try to resolve a parameter.

        Returns:
            (True, value) if this strategy can provide the value.
            (False, None) if this strategy cannot — try the next one.
        """
        return False, None


__all__ = [
    "ResolutionStrategy",
]
