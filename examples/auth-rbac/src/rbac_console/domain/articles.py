"""The protected resource — an in-memory article store.

Quadkit convention: ``domain/`` holds framework-agnostic models and
services.  No framework imports here — just plain dataclasses.  The DI
container treats them like any other service (see ``di/provider.py``),
and swapping this in-memory implementation for Postgres later changes
nothing outside ``di/``.

The RBAC demo needs something to guard.  Articles are the resource every
persona tries to read/create/delete; the permission matrix in
``controllers/api.py`` is exercised entirely against this store.

Deliberately *not* here: authorization checks.  Stores stay dumb —
controllers ask ``AuthorizationService`` before touching them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    """One demo article row.

    Plain dataclass — no framework imports, no Pydantic, no ORM.
    Quadkit convention: domain models are framework-agnostic dataclasses.
    The DI container treats them like any other service.
    """

    id: str
    title: str
    body: str


@dataclass
class ArticleStore:
    """In-memory article fixtures owned by the provider.

    Registered as a singleton, so every controller and the seed service
    share one dictionary for the lifetime of the process.  In production,
    replace this with a Postgres-backed repository — only di/provider.py
    changes.
    """

    _articles: dict[str, Article] = field(default_factory=dict)
    _next: int = 1

    def list(self) -> list[Article]:
        """All articles, insertion order.

        Stores stay dumb — no authorization checks here.  Controllers
        call ``AuthorizationService.authorize()`` before touching these methods.
        """
        return list(self._articles.values())

    def get(self, article_id: str) -> Article | None:
        """Fetch by id; ``None`` when absent (controller maps to 404)."""
        return self._articles.get(article_id)

    def create(self, title: str, body: str) -> Article:
        """Append a new article with an auto-assigned id.

        No Result type here — this is a simple in-memory store.
        Framework services (UserService, AuthorizationService) return
        Result[T, E] because they can fail in expected ways (not found,
        validation error).  Domain stores are simpler.
        """
        article = Article(id=f"a-{self._next}", title=title, body=body)
        self._next += 1
        self._articles[article.id] = article
        return article

    def delete(self, article_id: str) -> bool:
        """Remove by id; ``True`` when something was actually deleted."""
        return self._articles.pop(article_id, None) is not None


__all__ = ["Article", "ArticleStore"]
