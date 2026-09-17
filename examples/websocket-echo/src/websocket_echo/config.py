"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the WebSocket Echo demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class WebSocketEchoConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    ``max_room_members`` caps how many sockets may join one room before
    new connections are politely refused (accept, one error event, close).
    ``0`` disables the cap — the default, which preserves the classic
    unbounded-rooms behaviour of the original template.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "websocket_echo"
    name: str = "websocket_echo"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    max_room_members: int = Field(
        default=0,
        description="Max concurrent connections per room; 0 = unlimited",
    )


__all__ = ["WebSocketEchoConfig"]
