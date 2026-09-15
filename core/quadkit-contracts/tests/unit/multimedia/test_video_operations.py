from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.multimedia.types import (
    BurnSubtitles,
    ChangeSpeed,
    ColorFilter,
    ComposeAudioLayer,
    ComposeLayer,
    ComposeVideo,
    Concat,
    Crop,
    EncodeSpec,
    ExtractThumbnail,
    MediaAsset,
    MuxAudio,
    OverlayImage,
    OverlayText,
    RawFilter,
    SubtitleCue,
    ToGif,
    Transcode,
    TransitionSpec,
    Trim,
    VideoOperation,
)


def test_trim_is_frozen_dataclass():
    asset = MediaAsset(mime_type="video/mp4", provider="local-http", uri="a.mp4")
    op = Trim(asset=asset, start=1.0, end=2.0)
    assert op.start == 1.0
    assert op.end == 2.0


def test_concat_accepts_optional_transitions():
    asset = MediaAsset(mime_type="video/mp4", provider="local-http", uri="a.mp4")
    op = Concat(
        assets=[asset, asset],
        transitions=[TransitionSpec(kind="crossfade", duration=0.5)],
    )
    assert len(op.transitions) == 1
    assert op.transitions[0].kind == "crossfade"


def test_overlay_text_position_and_defaults():
    asset = MediaAsset(mime_type="video/mp4", provider="local-http", uri="a.mp4")
    op = OverlayText(asset=asset, text="hi", position="bottom")
    assert op.font_size == 32
    assert op.color == "white"


def test_burn_subtitles_cues():
    asset = MediaAsset(mime_type="video/mp4", provider="local-http", uri="a.mp4")
    op = BurnSubtitles(asset=asset, cues=[SubtitleCue(start=0.0, end=1.0, text="hi")])
    assert op.cues[0].text == "hi"


def test_video_operation_union_matches_all_variants():
    asset = MediaAsset(mime_type="video/mp4", provider="local-http", uri="a.mp4")
    ops: list[VideoOperation] = [
        Trim(asset=asset, start=0.0, end=1.0),
        Concat(assets=[asset]),
        OverlayText(asset=asset, text="hi", position="top"),
        OverlayImage(asset=asset, image_asset=asset, position="top"),
        BurnSubtitles(asset=asset, cues=[]),
        MuxAudio(asset=asset, audio_asset=asset, mode="replace"),
        ExtractThumbnail(asset=asset, timestamp=0.0),
        ToGif(asset=asset),
        Transcode(asset=asset, format="webm"),
        ChangeSpeed(asset=asset, factor=2.0),
        Crop(asset=asset, x=0, y=0, width=10, height=10),
        ColorFilter(asset=asset, preset="grayscale"),
        RawFilter(assets=[asset], filter_complex="null", maps=["0:v"]),
    ]
    for op in ops:
        match op:
            case (
                Trim()
                | Concat()
                | OverlayText()
                | OverlayImage()
                | BurnSubtitles()
                | MuxAudio()
                | ExtractThumbnail()
                | ToGif()
                | Transcode()
                | ChangeSpeed()
                | Crop()
                | ColorFilter()
                | RawFilter()
            ):
                pass
            case _:
                raise AssertionError(f"unmatched: {op}")


def test_compose_layer_defaults():
    asset = MediaAsset(mime_type="video/quicktime", provider="test", uri="l.mov")
    layer = ComposeLayer(asset=asset, start=1.0)
    assert layer.start == 1.0
    assert layer.end is None
    assert layer.fade_in == 0.0
    assert layer.fade_out == 0.0


def test_compose_audio_layer_defaults():
    asset = MediaAsset(mime_type="audio/wav", provider="test", uri="n.wav")
    layer = ComposeAudioLayer(asset=asset, start=2.0)
    assert layer.volume == 1.0


def test_encode_spec_defaults():
    spec = EncodeSpec()
    assert spec.codec == "libx264"
    assert spec.bitrate is None
    assert spec.resolution is None
    assert spec.fps is None


def test_compose_video_holds_layers_audio_fades_encode():
    base = MediaAsset(mime_type="video/mp4", provider="test", uri="b.mp4")
    layer = ComposeLayer(
        asset=MediaAsset(mime_type="video/quicktime", provider="test", uri="l.mov"),
        start=0.0,
        end=3.0,
        fade_in=0.2,
        fade_out=0.3,
    )
    audio = ComposeAudioLayer(
        asset=MediaAsset(mime_type="audio/wav", provider="test", uri="n.wav"),
        start=5.0,
        volume=0.8,
    )
    encode = EncodeSpec(
        codec="hevc_nvenc", bitrate="10M", resolution="1080x1920", fps=30
    )
    op = ComposeVideo(
        asset=base,
        layers=[layer],
        audio_layers=[audio],
        fade_in=0.5,
        fade_out=0.5,
        base_fade_out=0.75,
        encode=encode,
    )
    assert op.layers[0].fade_in == 0.2
    assert op.audio_layers[0].volume == 0.8
    assert op.encode == encode


def test_compose_video_is_frozen():
    base = MediaAsset(mime_type="video/mp4", provider="test", uri="b.mp4")
    op = ComposeVideo(asset=base)
    with pytest.raises(FrozenInstanceError):
        op.asset = MediaAsset(mime_type="video/mp4", provider="test", uri="c.mp4")


def test_compose_video_in_union():
    base = MediaAsset(mime_type="video/mp4", provider="test", uri="b.mp4")
    ops: list[VideoOperation] = [
        ComposeVideo(asset=base),
        Trim(asset=base, start=0.0, end=1.0),
    ]
    for op in ops:
        match op:
            case ComposeVideo():
                assert op.asset is base
            case Trim():
                pass
            case _:
                raise AssertionError(f"unmatched: {op}")
