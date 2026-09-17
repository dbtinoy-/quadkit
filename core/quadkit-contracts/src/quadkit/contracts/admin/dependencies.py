"""Dependency metadata and topological sort for admin contributors."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar


class ContributorDependencyError(ValueError):
    """Contributor dependency graph is invalid."""


class ContributorWithDependenciesProtocol(Protocol):
    name: str
    depends_on: tuple[str, ...]


T = TypeVar("T", bound=ContributorWithDependenciesProtocol)


def sort_contributors(contributors: Iterable[T]) -> list[T]:
    by_name = {c.name: c for c in contributors}
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[T] = []

    def visit(name: str, trail: Sequence[str]) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ContributorDependencyError(
                "contributor dependency cycle: " + " -> ".join([*trail, name])
            )
        if name not in by_name:
            raise ContributorDependencyError(f"missing dependency: {name}")
        visiting.add(name)
        contributor = by_name[name]
        for dep in contributor.depends_on:
            visit(dep, [*trail, name])
        visiting.remove(name)
        visited.add(name)
        ordered.append(contributor)

    for contributor_name in by_name:
        visit(contributor_name, [])
    return ordered


__all__ = [
    "ContributorDependencyError",
    "ContributorWithDependenciesProtocol",
    "sort_contributors",
]
