import pytest

from quadkit.contracts.multimedia.types import (
    BeatAnalysisRequest,
    BeatAnalysisResult,
    ImageRequest,
    InterpolationRequest,
    MediaAsset,
    MusicRequest,
    TTSRequest,
    UpscaleRequest,
    VideoMode,
    VideoRequest,
)


def test_media_asset_with_bytes_has_no_uri() -> None:
    asset = MediaAsset(mime_type="audio/mpeg", provider="local-http", bytes_data=b"abc")
    assert asset.has_bytes is True
    assert asset.has_uri is False


def test_media_asset_with_uri_has_no_bytes() -> None:
    asset = MediaAsset(mime_type="audio/mpeg", provider="elevenlabs", uri="https://example/x.mp3")
    assert asset.has_uri is True
    assert asset.has_bytes is False


def test_media_asset_is_frozen() -> None:
    asset = MediaAsset(mime_type="audio/mpeg", provider="local-http", bytes_data=b"abc")
    with pytest.raises(Exception):  # noqa: B017 — frozen dataclass raises FrozenInstanceError
        asset.provider = "other"  # type: ignore[misc]


def test_tts_request_defaults() -> None:
    req = TTSRequest(text="hello")
    assert req.voice is None
    assert req.format == "mp3"
    assert req.reference_audio_uri is None
    assert req.emotion is None


def test_tts_request_accepts_reference_audio_and_emotion() -> None:
    req = TTSRequest(
        text="hello",
        voice="longxiaoxia_v3",
        reference_audio_uri="https://cdn.example.com/ref.wav",
        emotion="excited",
        extra={"quality": "high"},
    )
    assert req.reference_audio_uri == "https://cdn.example.com/ref.wav"
    assert req.emotion == "excited"
    assert req.extra == {"quality": "high"}


def test_music_request_defaults() -> None:
    req = MusicRequest(prompt="lofi beat")
    assert req.duration_seconds == 30.0


def test_video_request_defaults() -> None:
    req = VideoRequest(prompt="a cat")
    assert req.duration_seconds == 4.0
    assert req.resolution == "1280x720"
    assert req.model is None
    assert req.mode is None
    assert req.last_frame_image is None
    assert req.reference_images == []
    assert req.reference_videos == []
    assert req.reference_audios == []
    assert req.generate_audio is False
    assert req.return_last_frame is False
    assert req.ratio is None
    assert req.seed is None


def test_video_request_accepts_multimodal_fields() -> None:
    req = VideoRequest(
        prompt="镜头跟随主角",
        model="seedance-2.0",
        mode=VideoMode.MULTIMODAL_REFERENCE,
        reference_images=["https://oss.example/a/1.png", "https://oss.example/a/2.png"],
        reference_videos=["https://oss.example/a/c.mp4"],
        reference_audios=["https://oss.example/a/v.wav"],
        generate_audio=True,
        return_last_frame=True,
        ratio="9:16",
        seed=42,
    )
    assert req.model == "seedance-2.0"
    assert req.mode is VideoMode.MULTIMODAL_REFERENCE
    assert req.reference_images == [
        "https://oss.example/a/1.png",
        "https://oss.example/a/2.png",
    ]
    assert req.reference_videos == ["https://oss.example/a/c.mp4"]
    assert req.reference_audios == ["https://oss.example/a/v.wav"]
    assert req.generate_audio is True
    assert req.return_last_frame is True
    assert req.ratio == "9:16"
    assert req.seed == 42


def test_image_request_defaults() -> None:
    req = ImageRequest(prompt="a cat")
    assert req.width == 1024
    assert req.height == 1024
    assert req.reference_image is None
    assert req.reference_mime_type is None


def test_image_request_accepts_reference_image() -> None:
    req = ImageRequest(
        prompt="a cat wearing the same red hat",
        reference_image=b"\x89PNG...",
        reference_mime_type="image/png",
    )
    assert req.reference_image == b"\x89PNG..."
    assert req.reference_mime_type == "image/png"


def test_upscale_request_defaults() -> None:
    asset = MediaAsset(mime_type="image/png", provider="test", bytes_data=b"x")
    req = UpscaleRequest(asset=asset)
    assert req.scale_factor == 4
    assert req.extra == {}


def test_interpolation_request_has_no_factor_field() -> None:
    frame_a = MediaAsset(mime_type="image/png", provider="test", bytes_data=b"a")
    frame_b = MediaAsset(mime_type="image/png", provider="test", bytes_data=b"b")
    req = InterpolationRequest(frame_a=frame_a, frame_b=frame_b)
    assert req.frame_a is frame_a
    assert req.frame_b is frame_b
    assert req.extra == {}
    assert not hasattr(req, "factor")


def test_beat_analysis_request_defaults() -> None:
    asset = MediaAsset(mime_type="audio/mpeg", provider="test", bytes_data=b"audio")
    req = BeatAnalysisRequest(asset=asset)
    assert req.asset is asset
    assert req.extra == {}


def test_beat_analysis_result_is_not_a_media_asset() -> None:
    result = BeatAnalysisResult(tempo_bpm=120.0, beat_timestamps=[0.5, 1.0, 1.5])
    assert result.tempo_bpm == 120.0
    assert result.beat_timestamps == [0.5, 1.0, 1.5]
    assert not hasattr(result, "bytes_data")
    assert not hasattr(result, "uri")
