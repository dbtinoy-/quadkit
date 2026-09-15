"""Structural protocols for multimedia generation providers.

Four separate Protocols rather than one shared base class — Python's
structural typing makes a base class unnecessary, and each media type's
request/response shape differs enough that a shared abstract method
signature would need to be typed loosely (``Any``) to fit all four.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.multimedia.exceptions import (
        MultimediaError,
        VideoGenerationError,
    )
    from quadkit.contracts.multimedia.types import (
        BeatAnalysisRequest,
        BeatAnalysisResult,
        ImageRequest,
        InterpolationRequest,
        MediaAsset,
        MusicRequest,
        TTSRequest,
        UpscaleRequest,
        VideoOperation,
        VideoRequest,
    )


@runtime_checkable
class TTSProvider(Protocol):
    """Protocol for text-to-speech generation backends."""

    async def generate(
        self, request: TTSRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


@runtime_checkable
class InterpolationProvider(Protocol):
    """Protocol for two-frame midpoint interpolation backends."""

    async def interpolate(
        self, request: InterpolationRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


@runtime_checkable
class MusicProvider(Protocol):
    """Protocol for music/sound generation backends."""

    async def generate(
        self, request: MusicRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


@runtime_checkable
class VideoProvider(Protocol):
    """Protocol for video generation backends."""

    async def generate(
        self, request: VideoRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


@runtime_checkable
class VideoProcessor(Protocol):
    """Protocol for ffmpeg-backed video processing/editing backends.

    `progress_callback` receives `0.0 <= pct <= 1.0`; implementations
    should emit `1.0` exactly once when processing finishes successfully.
    """

    async def process(
        self,
        operation: VideoOperation,
        *,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Result[MediaAsset, VideoGenerationError]: ...

    async def extract_frames(
        self, asset: MediaAsset, *, fps: float | None = None
    ) -> Result[list[MediaAsset], VideoGenerationError]: ...

    async def assemble_frames(
        self, frames: list[MediaAsset], *, fps: float
    ) -> Result[MediaAsset, VideoGenerationError]: ...


@runtime_checkable
class BeatAnalysisProvider(Protocol):
    """Protocol for audio tempo/beat-detection backends."""

    async def analyze(
        self, request: BeatAnalysisRequest
    ) -> Result[BeatAnalysisResult, MultimediaError]: ...


@runtime_checkable
class ImageProvider(Protocol):
    """Protocol for still-image generation backends."""

    async def generate(
        self, request: ImageRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


@runtime_checkable
class UpscaleProvider(Protocol):
    """Protocol for single-image super-resolution backends."""

    async def upscale(
        self, request: UpscaleRequest
    ) -> Result[MediaAsset, MultimediaError]: ...


__all__ = [
    "BeatAnalysisProvider",
    "ImageProvider",
    "InterpolationProvider",
    "MusicProvider",
    "TTSProvider",
    "UpscaleProvider",
    "VideoProcessor",
    "VideoProvider",
]
