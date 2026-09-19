"""Configuration for transport-agnostic security primitives.

HTTP-specific configs (``CORSConfig``, ``CSRFConfig``, ``CSPConfig``,
``HSTSConfig``, ``CrossOriginConfig``) live in
``quadkit.web.security.config`` and will be migrated there in a later task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class InputSanitizerConfig(BaseConfig):
    """Configuration for input sanitization.

    Attributes:
        allowed_tags: Set of allowed HTML tags when using sanitization.
            If ``None``, all HTML tags are stripped.
        strip_comments: Whether to strip HTML comments during sanitization.
        default_sanitize_mode: Default sanitization mode
            (``'strip'``, ``'escape'``, or ``'none'``).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    allowed_tags: set[str] | None = Field(default=None)
    strip_comments: bool = Field(default=True)
    default_sanitize_mode: str = "allow"


@dataclass(init=False)
class HashingConfig(BaseConfig):
    """Configuration for core security hashing services."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    default_hasher: str = Field(default="sha256")
    algorithm: str = Field(default="pbkdf2_sha256")
    iterations: int = Field(default=100_000)
    salt_length: int = Field(default=16)
    dklen: int = Field(default=32)
    blake2b_digest_size: int = Field(default=64)


@dataclass(init=False)
class SecurityConfig(BaseConfig):
    """Configuration for the core security subsystem."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "security"
    name: str = "security"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")

    sanitization: InputSanitizerConfig = Field(default_factory=InputSanitizerConfig)
    hashing: HashingConfig = Field(default_factory=HashingConfig)


__all__ = ["HashingConfig", "InputSanitizerConfig", "SecurityConfig"]
