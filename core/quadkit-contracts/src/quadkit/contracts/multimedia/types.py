"""Value objects for the multimedia generation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


@dataclass(frozen=True)
class MediaAsset:
    """Result of a generation call — carries either raw bytes or a URI, never both.

    Several v1 providers (ElevenLabs, OpenAI TTS, Stability) return raw bytes
    in the response body with no hosted URL, so callers must check
    :attr:`has_bytes`/:attr:`has_uri` rather than assuming a shape.
    """

    mime_type: str
    provider: str
    bytes_data: bytes | None = None
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_bytes(self) -> bool:
        return self.bytes_data is not None

    @property
    def has_uri(self) -> bool:
        return self.uri is not None


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str | None = None
    format: str = "mp3"
    reference_audio_uri: str | None = None
    emotion: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MusicRequest:
    prompt: str
    duration_seconds: float = 30.0
    format: str = "mp3"
    extra: dict[str, Any] = field(default_factory=dict)


class VideoMode(str, Enum):
    """Reference-input mode for a video generation request.

    ``None`` on the request means the provider derives the mode from which
    fields are set (see ``OpenAIVideoProvider._derive_mode``).
    """

    TEXT_TO_VIDEO = "text_to_video"
    FIRST_FRAME = "first_frame"
    FIRST_LAST_FRAME = "first_last_frame"
    MULTIMODAL_REFERENCE = "multimodal_reference"


@dataclass(frozen=True)
class VideoRequest:
    prompt: str
    duration_seconds: float = 4.0
    resolution: str = "1280x720"
    image_uri: str | None = None
    format: str = "mp4"
    model: str | None = None
    mode: VideoMode | None = None
    last_frame_image: str | None = None
    reference_images: list[str] = field(default_factory=list)
    reference_videos: list[str] = field(default_factory=list)
    reference_audios: list[str] = field(default_factory=list)
    generate_audio: bool = False
    return_last_frame: bool = False
    ratio: str | None = None
    seed: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    width: int = 1024
    height: int = 1024
    format: str = "png"
    reference_image: bytes | None = None
    reference_mime_type: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterpolationRequest:
    frame_a: MediaAsset
    frame_b: MediaAsset
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpscaleRequest:
    asset: MediaAsset
    scale_factor: Literal[2, 4] = 4
    extra: dict[str, Any] = field(default_factory=dict)


OverlayPosition = Literal[
    "top",
    "bottom",
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
]


@dataclass(frozen=True)
class TransitionSpec:
    kind: Literal["cut", "crossfade"]
    duration: float = 0.5


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Trim:
    asset: MediaAsset
    start: float
    end: float


@dataclass(frozen=True)
class Concat:
    assets: list[MediaAsset]
    transitions: list[TransitionSpec] | None = None


@dataclass(frozen=True)
class OverlayText:
    asset: MediaAsset
    text: str
    position: OverlayPosition
    start: float | None = None
    end: float | None = None
    font_size: int = 32
    color: str = "white"


@dataclass(frozen=True)
class OverlayImage:
    asset: MediaAsset
    image_asset: MediaAsset
    position: OverlayPosition
    opacity: float = 1.0
    start: float | None = None
    end: float | None = None


@dataclass(frozen=True)
class ComposeLayer:
    """A full-canvas transparent overlay placed on the base at a time offset.

    `start`/`end` are seconds on the composed timeline. `fade_in`/`fade_out`
    are durations in seconds on the layer's own timeline (fade-in starts when
    the layer appears; fade-out ends at the layer's end).
    """

    asset: MediaAsset
    start: float = 0.0
    end: float | None = None
    fade_in: float = 0.0
    fade_out: float = 0.0


@dataclass(frozen=True)
class ComposeAudioLayer:
    """An audio input placed at a time offset on the composed timeline."""

    asset: MediaAsset
    start: float = 0.0
    volume: float = 1.0


@dataclass(frozen=True)
class EncodeSpec:
    """Output encoding parameters for the finished composition."""

    codec: str = "libx264"
    bitrate: str | None = None
    resolution: str | None = None
    fps: int | None = None


@dataclass(frozen=True)
class ComposeVideo:
    """Compose a base video with timed overlays, fades, and audio layers.

    Semantics:
    - Output duration == base asset duration.
    - The base's audio is dropped unless `audio_layers` is non-empty.
    - `fade_in`/`fade_out` fade the whole composition from/to black.
    - `base_fade_out` fades the BASE stream to black before its end (e.g. a CTA
      lead-in) while later overlay layers keep compositing on top.
    - `layers` composite over the base in list order (later layers on top) and
      are only visible within their `[start, end)` window.
    """

    asset: MediaAsset
    layers: list[ComposeLayer] = field(default_factory=list)
    audio_layers: list[ComposeAudioLayer] = field(default_factory=list)
    fade_in: float = 0.0
    fade_out: float = 0.0
    base_fade_out: float = 0.0
    encode: EncodeSpec | None = None


@dataclass(frozen=True)
class BeatAnalysisRequest:
    asset: MediaAsset
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BeatAnalysisResult:
    tempo_bpm: float
    beat_timestamps: list[float]


@dataclass(frozen=True)
class BurnSubtitles:
    asset: MediaAsset
    cues: list[SubtitleCue]


@dataclass(frozen=True)
class MuxAudio:
    asset: MediaAsset
    audio_asset: MediaAsset
    mode: Literal["replace", "mix"]
    music_volume: float = 1.0
    duck_under_existing: bool = False


@dataclass(frozen=True)
class ExtractThumbnail:
    asset: MediaAsset
    timestamp: float


@dataclass(frozen=True)
class ToGif:
    asset: MediaAsset
    start: float | None = None
    end: float | None = None
    fps: int = 10
    width: int = 480


@dataclass(frozen=True)
class Transcode:
    asset: MediaAsset
    format: str
    codec: str | None = None
    resolution: str | None = None
    bitrate: str | None = None


@dataclass(frozen=True)
class ChangeSpeed:
    asset: MediaAsset
    factor: float


@dataclass(frozen=True)
class Crop:
    asset: MediaAsset
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ColorFilter:
    asset: MediaAsset
    preset: Literal["none", "grayscale", "sepia", "vintage"] | None = None
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0


@dataclass(frozen=True)
class RawFilter:
    assets: list[MediaAsset]
    filter_complex: str
    maps: list[str]
    extra_args: list[str] = field(default_factory=list)


VideoOperation = (
    Trim
    | Concat
    | OverlayText
    | OverlayImage
    | ComposeVideo
    | BurnSubtitles
    | MuxAudio
    | ExtractThumbnail
    | ToGif
    | Transcode
    | ChangeSpeed
    | Crop
    | ColorFilter
    | RawFilter
)


__all__ = [
    "BeatAnalysisRequest",
    "BeatAnalysisResult",
    "BurnSubtitles",
    "ChangeSpeed",
    "ColorFilter",
    "ComposeAudioLayer",
    "ComposeLayer",
    "ComposeVideo",
    "Concat",
    "Crop",
    "EncodeSpec",
    "ExtractThumbnail",
    "ImageRequest",
    "InterpolationRequest",
    "MediaAsset",
    "MusicRequest",
    "MuxAudio",
    "OverlayImage",
    "OverlayPosition",
    "OverlayText",
    "RawFilter",
    "SubtitleCue",
    "TTSRequest",
    "ToGif",
    "Transcode",
    "TransitionSpec",
    "Trim",
    "UpscaleRequest",
    "VideoMode",
    "VideoOperation",
    "VideoRequest",
]
