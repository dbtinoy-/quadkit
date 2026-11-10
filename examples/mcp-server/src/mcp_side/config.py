"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the MCP Server demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class McpSideConfig(BaseConfig):
    """Demo-owned settings for the MCP bridge handshake."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "mcp_side"
    name: str = "mcp_side"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    client_name: str = Field(
        default="mcp-bridge",
        description="Client identifier sent during the MCP initialize handshake",
    )


__all__ = ["McpSideConfig"]
