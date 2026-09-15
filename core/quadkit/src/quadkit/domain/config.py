"""Configuration for the domain subsystem.

Domain primitives (entities, value objects, aggregates) have no
infrastructure dependencies.  :class:`DomainConfig` provides extension
points for future domain-level configuration without breaking the
package root-file contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DomainConfig:
    """Domain subsystem configuration.

    Currently a minimal configuration with no required fields.
    Both fields below are **reserved**: they are accepted for forward
    compatibility but have no runtime effect today (see per-field notes).

    Attributes:
        strict_immutability: Reserved. Value objects are *already* frozen
            dataclasses and raise ``FrozenInstanceError`` on mutation
            unconditionally, so there is nothing for this flag to toggle.
            Kept so a future entity-level strictness knob can land without
            a breaking change.
        id_prefix: Reserved. ID generation (and prefixing) lives in the
            ``quadkit.identity`` subsystem, which has its own
            ``IdentityConfig.prefix_map`` / ``PrefixedIdGenerator``; this
            field is not read by any ID generator. Empty string = disabled.
    """

    strict_immutability: bool = False
    id_prefix: str = ""


__all__ = ["DomainConfig"]
