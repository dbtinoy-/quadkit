"""Model manager providers."""

from __future__ import annotations

from quadkit.ai.llm.model_manager.providers.ollama import OllamaModelManager
from quadkit.ai.llm.model_manager.providers.openapi_compatible import (
    LMStudioModelManager,
    OpenAPICompatibleModelManager,
    VLLMModelManager,
)

__all__ = [
    "LMStudioModelManager",
    "OllamaModelManager",
    "OpenAPICompatibleModelManager",
    "VLLMModelManager",
]
