"""P2-jwt-hash: JWT verification cache key must use full 64-char SHA-256 hex digest."""

from __future__ import annotations

import inspect

import quadkit.auth.authn.jwt as jwt_module


class TestJwtTokenHashUsesFullSha256:
    """P2: token_hash must not truncate the SHA-256 hexdigest to 16 chars."""

    def test_source_does_not_truncate_hexdigest(self) -> None:
        """Ensure the [:16] slice is absent from the jwt module source."""
        source = inspect.getsource(jwt_module)
        assert "hexdigest()[:16]" not in source, (
            "JWT token_hash truncates SHA-256 to 16 hex chars — "
            "must use full hexdigest() for collision resistance"
        )
