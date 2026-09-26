"""P2-oauth2-status: QuadkitConnectResponse.status_code must raise on unknown response."""

from __future__ import annotations

import pytest

from quadkit.auth.authn.oauth2 import QuadkitConnectResponse


class TestOAuth2StatusCodeRaisesOnUnknown:
    """P2: status_code must raise AttributeError, not return 0, for unknown responses."""

    def test_status_code_raises_attribute_error_when_no_status_attr(self) -> None:
        """Response object with no status_code or status raises AttributeError."""

        class NoStatusResponse:
            headers: dict = {}

        wrapper = QuadkitConnectResponse(NoStatusResponse())
        with pytest.raises(AttributeError, match="NoStatusResponse"):
            _ = wrapper.status_code

    def test_status_code_returns_int_when_status_code_present(self) -> None:
        """Sanity: a real status_code attribute is still returned."""

        class HttpxLike:
            status_code = 200
            headers: dict = {}

        wrapper = QuadkitConnectResponse(HttpxLike())
        assert wrapper.status_code == 200

    def test_status_code_returns_int_when_status_present(self) -> None:
        """Sanity: aiohttp-style .status attribute is still returned."""

        class AiohttpLike:
            status = 404
            headers: dict = {}

        wrapper = QuadkitConnectResponse(AiohttpLike())
        assert wrapper.status_code == 404
