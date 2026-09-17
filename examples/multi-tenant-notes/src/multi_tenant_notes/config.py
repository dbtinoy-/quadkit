"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Multi-Tenant Notes demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class MultiTenantNotesConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    ``max_notes_per_tenant`` caps how many notes one tenant may store;
    ``0`` disables the cap (the default, preserving the original
    unbounded behaviour). Isolation itself is by construction — every
    store operation is keyed by tenant — not a config knob.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "multi_tenant_notes"
    name: str = "multi_tenant_notes"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    max_notes_per_tenant: int = Field(
        default=0,
        description="Max notes one tenant may store; 0 = unlimited",
    )


__all__ = ["MultiTenantNotesConfig"]
