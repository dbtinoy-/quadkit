from quadkit.contracts.exceptions.domain import DomainError
from quadkit.contracts.multimedia.exceptions import (
    BeatAnalysisError,
    ImageGenerationError,
    MultimediaError,
    MusicGenerationError,
    ProviderNotInstalledError,
    TTSError,
    UpscaleError,
    VideoGenerationError,
)


def test_multimedia_error_extends_domain_error() -> None:
    assert issubclass(MultimediaError, DomainError)


def test_media_type_errors_extend_multimedia_error() -> None:
    for exc_cls in (TTSError, MusicGenerationError, VideoGenerationError, ImageGenerationError, UpscaleError, BeatAnalysisError):
        assert issubclass(exc_cls, MultimediaError)


def test_provider_not_installed_error_has_actionable_message() -> None:
    err = ProviderNotInstalledError(
        "pip install quadkit-multimedia-tts[elevenlabs]"
    )
    assert "pip install" in err.message
