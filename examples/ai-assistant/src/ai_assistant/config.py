"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply
(the old ``AI_GATEWAY_URL``/``AI_API_KEY``/``AI_MODEL`` env vars are gone).

Typed configuration for the AI Assistant demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field, SecretStr


@dataclass(init=False)
class AIAssistantConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    The gateway settings describe any OpenAI-compatible chat endpoint;
    the demo never calls out by default — tests inject a fake client
    through the same provider seam production code uses.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "ai_assistant"
    name: str = "ai_assistant"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    gateway_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible gateway base URL",
    )
    api_key: SecretStr = Field(
        default=SecretStr("set-me"),
        description="Gateway bearer credential; redacted in logs and dumps",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Chat model name sent to the gateway",
    )


__all__ = ["AIAssistantConfig"]
