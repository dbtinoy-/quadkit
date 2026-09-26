"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for Artifact Vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class ArtifactVaultConfig(BaseConfig):
    """Demo-owned display settings; BlobStore behavior belongs to Quadkit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "artifact_vault"
    name: str = "artifact_vault"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    seed_welcome_artifact: bool = True


__all__ = ["ArtifactVaultConfig"]
