"""Persona directory — role-keyed seeded users for the console.

Quadkit convention: ``domain/`` holds framework-agnostic models and
services.  This catalog is plain Python — no framework imports.

Three personas ship with the demo — ``viewer``, ``editor``, ``admin`` —
one per RBAC tier, so every row of the permission matrix can be exercised
by logging in as a different user (see ``data/seed.py`` for how they're
created and ``tests/test_rbac.py`` for the login helper).

Note: personas are *demo scaffolding*, not a framework concept.
In a real app your users come from a database or an identity provider;
the rest of this demo never imports this module except to render the
persona picker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PERSONAS: tuple[str, ...] = ("viewer", "editor", "admin")
# Tuple of persona role names — used by seed.py, controllers, and tests.
# In a real app this comes from a database; here it's demo scaffolding.


@dataclass
class PersonaDirectory:
    """Role-keyed lookup of the seeded persona users.

    Registered as a singleton by ``di/provider.py``; ``RbacSeedService``
    fills it during ``boot()`` and controllers read it to render the
    persona switcher.
    """

    _by_role: dict[str, Any] = field(default_factory=dict)

    def register(self, role: str, user: Any) -> None:
        """Attach one seeded persona user."""
        self._by_role[role] = user

    def get(self, role: str) -> Any | None:
        """Return the persona user for ``role``, or None.

        Uses ``Any`` deliberately — the user type comes from the auth
        module's UserService, which is framework-owned.  Your app can
        use a concrete type if you define your own user model.
        """
        return self._by_role.get(role)

    def roles(self) -> list[str]:
        """Return all registered role names in seed order."""
        return list(self._by_role)


__all__ = ["PERSONAS", "PersonaDirectory"]
