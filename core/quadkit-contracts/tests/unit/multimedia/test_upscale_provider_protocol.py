from quadkit.contracts.core.result import Ok, Result
from quadkit.contracts.multimedia.exceptions import MultimediaError
from quadkit.contracts.multimedia.protocols import UpscaleProvider
from quadkit.contracts.multimedia.types import MediaAsset, UpscaleRequest


class _FakeUpscaleProvider:
    async def upscale(self, request):
        asset = MediaAsset(mime_type="image/png", provider="test", bytes_data=b"x")
        return Ok(asset)


async def test_fake_provider_satisfies_protocol() -> None:
    provider: UpscaleProvider = _FakeUpscaleProvider()
    asset = MediaAsset(mime_type="image/png", provider="test", bytes_data=b"y")
    result: Result[MediaAsset, MultimediaError] = await provider.upscale(
        UpscaleRequest(asset=asset)
    )
    assert result.is_ok()


def test_isinstance_check_via_runtime_checkable() -> None:
    assert isinstance(_FakeUpscaleProvider(), UpscaleProvider)
