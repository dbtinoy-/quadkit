"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Auth Tokens demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field, SecretStr


@dataclass(init=False)
class AuthTokensConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    ``token_secret`` is the HMAC key for bearer-token signing. The
    default is a well-known dev value so the template runs out of the
    box; production sets ``QK_AUTH_TOKENS__TOKEN_SECRET`` (or the yaml
    key) to a real secret — never commit a real secret to the yaml.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "auth_tokens"
    name: str = "auth_tokens"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    token_secret: SecretStr = Field(
        default=SecretStr("dev-secret"),
        description="HMAC secret used to sign bearer tokens",
    )


__all__ = ["AuthTokensConfig"]
