"""Type definitions and exceptions for model management."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.ai.llm.exceptions import (
    LLMError,
)
from quadkit.ai.llm.exceptions import (
    ModelNotFoundError as BaseModelNotFoundError,
)
from quadkit.ai.llm.exceptions import (
    ProviderConnectionError as BaseProviderConnectionError,
)


class ModelManagerError(LLMError):
    """Base exception for model manager errors."""

    _code: str = "QK_ERR_LLM_020"


class ModelNotFoundError(ModelManagerError, BaseModelNotFoundError):
    """Raised when a requested model is not found."""

    _code: str = "QK_ERR_LLM_021"


class ModelLoadError(ModelManagerError):
    """Raised when a model fails to load."""

    _code: str = "QK_ERR_LLM_022"


class ModelUnloadError(ModelManagerError):
    """Raised when a model fails to unload."""

    _code: str = "QK_ERR_LLM_023"


class ProviderConnectionError(ModelManagerError, BaseProviderConnectionError):
    """Raised when connection to provider fails."""

    _code: str = "QK_ERR_LLM_024"


@dataclass
class ModelLoadResult:
    """Result of a model load operation."""

    success: bool
    model_name: str
    error: str | None = None
    retryable: bool = False
