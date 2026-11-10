"""Model management for LLM providers.

This module provides model loading, unloading, and switching capabilities
for different LLM providers like Ollama and LM Studio.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from quadkit.ai.llm.model_manager.base import AbstractModelManager
from quadkit.ai.llm.model_manager.manager import LLMModelManager
from quadkit.ai.llm.model_manager.providers import (
    LMStudioModelManager,
    OllamaModelManager,
    VLLMModelManager,
)
from quadkit.ai.llm.model_manager.types import (
    ModelLoadError,
    ModelLoadResult,
    ModelManagerError,
    ModelNotFoundError,
    ModelUnloadError,
    ProviderConnectionError,
)

try:
    __version__ = version("quadkit-ai-llm")
except PackageNotFoundError:
    __version__ = "0.0.0"


__all__ = [
    "AbstractModelManager",
    "LLMModelManager",
    "LMStudioModelManager",
    "ModelLoadError",
    "ModelLoadResult",
    "ModelManagerError",
    "ModelNotFoundError",
    "ModelUnloadError",
    "OllamaModelManager",
    "ProviderConnectionError",
    "VLLMModelManager",
]
