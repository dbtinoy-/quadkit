"""The single role model shared by quadkit-auth and quadkit-admin."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoleDefinition:
    """A named collection of permissions.

    The one role model in the framework (spec D2). Permission entries are
    strings in ``"resource.action"`` form, optionally scoped as
    ``"resource.action:scope"`` (``scope`` in {"self", "team", "all"},
    carried forward from the former ``rbac.Permission.scope`` field —
    evaluation of scope by the PDP is deferred, spec §7).
    """

    name: str
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    is_system: bool = False
