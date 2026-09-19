"""Provider dependency graph utilities.

Handles topological sorting and parallel boot-level computation
for the provider lifecycle orchestrator.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.di.provider import Provider


class ProviderGraph:
    """Computes provider ordering and parallel boot levels.

    Accepts a live reference to the providers dict so that additions made
    after construction are automatically reflected in subsequent calls.

    Args:
        providers: Mapping of provider name → Provider instance, shared
            by reference with the calling orchestrator.
    """

    def __init__(self, providers: dict[str, Provider]) -> None:
        self._providers = providers

    def topological_sort(self) -> list[Provider]:
        """Sort providers by dependencies then priority.

        Hard dependencies (``provider.dependencies``) must all be registered;
        a missing hard dependency raises :exc:`ValueError`.  Soft dependencies
        (``provider.optional_dependencies``) only affect ordering when the
        named provider is present — absent optional deps are silently ignored.
        """
        graph: dict[str, list[str]] = {n: [] for n in self._providers}
        in_degree: dict[str, int] = dict.fromkeys(self._providers, 0)

        for name, provider in self._providers.items():
            for dep in provider.dependencies:
                if dep not in self._providers:
                    raise ValueError(
                        f"Provider {name!r} depends on {dep!r}, "
                        f"which is not registered. "
                        f"Available: {sorted(self._providers.keys())}",
                    )
                graph[dep].append(name)
                in_degree[name] += 1

            # Optional dependencies: only add edge when the dep is registered.
            for opt_dep in getattr(provider, "optional_dependencies", ()):
                if opt_dep in self._providers:
                    graph[opt_dep].append(name)
                    in_degree[name] += 1

        # Use deque for O(1) popleft instead of list.pop(0)
        queue: deque[str] = deque(
            sorted(
                (n for n, d in in_degree.items() if d == 0),
                key=lambda n: (self._providers[n].priority, n),
            ),
        )

        result: list[Provider] = []
        while queue:
            name = queue.popleft()
            result.append(self._providers[name])

            for dependent in sorted(
                graph[name],
                key=lambda n: (self._providers[n].priority, n),
            ):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._providers):
            placed = {p.name for p in result}
            missing = set(self._providers) - placed
            raise ValueError(f"Circular dependency among providers: {missing}")

        return result

    def compute_boot_levels(self, ordered: list[Provider]) -> list[list[Provider]]:
        """Group providers into parallel boot levels.

        Both hard dependencies and optional dependencies (when the provider
        is registered) are respected for level placement. Within each wave,
        only the lowest ready priority bucket may boot in parallel so provider
        priority remains a real lifecycle ordering constraint.

        Args:
            ordered: Providers in topologically sorted order.

        Returns:
            List of levels where each level's providers can boot in parallel.
        """
        levels: list[list[Provider]] = []
        placed: set[str] = set()
        registered = set(self._providers)

        remaining = list(ordered)
        while remaining:
            ready = [
                p
                for p in remaining
                if all(dep in placed for dep in p.dependencies)
                and all(
                    dep in placed
                    for dep in getattr(p, "optional_dependencies", ())
                    if dep in registered
                )
            ]
            if not ready:
                raise RuntimeError("Cannot compute boot levels — cycle")

            next_priority = min(provider.priority for provider in ready)
            level = [
                provider for provider in ready if provider.priority == next_priority
            ]

            levels.append(level)
            for p in level:
                placed.add(p.name)
                remaining.remove(p)

        return levels


__all__ = ["ProviderGraph"]
