"""Domain errors for the multimedia generation subsystem."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class MultimediaError(DomainError):
    """Base exception for all multimedia-generation errors.

    Mirrors ``AIError(DomainError)`` — recoverable, expected failures that
    callers should handle gracefully via ``Result``.
    """

    _code = "QK_ERR_MM_001"

    def __init__(
        self, message: str = "Multimedia generation error", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class BeatAnalysisError(MultimediaError):
    """Base for tempo/beat-detection errors."""

    _code = "QK_ERR_MM_008"


class TTSError(MultimediaError):
    """Base for text-to-speech generation errors."""

    _code = "QK_ERR_MM_002"


class MusicGenerationError(MultimediaError):
    """Base for music/sound generation errors."""

    _code = "QK_ERR_MM_003"


class VideoGenerationError(MultimediaError):
    """Base for video generation errors."""

    _code = "QK_ERR_MM_004"


class ImageGenerationError(MultimediaError):
    """Base for still-image generation errors."""

    _code = "QK_ERR_MM_005"


class ProviderNotInstalledError(MultimediaError):
    """Raised eagerly at DI-resolution time when a configured provider's
    optional extra is not installed. Carries an actionable install hint
    rather than surfacing a bare ImportError later.
    """

    _code = "QK_ERR_MM_006"


class UpscaleError(MultimediaError):
    """Base for image/video super-resolution errors."""

    _code = "QK_ERR_MM_007"


__all__ = [
    "BeatAnalysisError",
    "ImageGenerationError",
    "MultimediaError",
    "MusicGenerationError",
    "ProviderNotInstalledError",
    "TTSError",
    "UpscaleError",
    "VideoGenerationError",
]
