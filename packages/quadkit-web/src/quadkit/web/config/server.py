"""Web server configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.validation import ConfigDict, Field, model_validator
from quadkit.web import constants as const


@dataclass(init=False)
class ServerConfig(BaseConfig):
    """Server configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    backend: str = Field(
        default=const.DEFAULT_BACKEND,
        description="ASGI server backend (granian | uvicorn | hypercorn | gunicorn)",
    )
    host: str = Field(default=const.DEFAULT_HOST, description="Bind host")
    port: int = Field(default=const.DEFAULT_PORT, description="Bind port")
    workers: int = Field(default=const.DEFAULT_WORKERS, description="Number of workers")
    reload: bool = Field(default=const.DEFAULT_RELOAD, description="Enable auto-reload")
    debug: bool = Field(default=False, description="Enable debug mode")

    @model_validator(mode="after")
    def validate_server(self) -> ServerConfig:
        """Validate server host and port."""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port: {self.port}. Must be between 1 and 65535.")
        if not self.host:
            raise ValueError("Server host cannot be empty.")
        return self


__all__ = [
    "ServerConfig",
]
