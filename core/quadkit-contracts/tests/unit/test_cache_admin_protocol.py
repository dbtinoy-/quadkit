"""Tests for the optional cache operations contract."""

from __future__ import annotations

from quadkit.contracts.infra.cache import CacheAdminProtocol


class TestCacheAdminProtocol:
    """The operational cache seam is structural and data-plane safe."""

    def test_plain_inspectable_backend_matches_protocol(self) -> None:
        """A backend can expose stats and reset without inheriting a base class."""

        class Backend:
            def get_stats(self) -> dict[str, int]:
                return {"hits": 2}

            def reset_stats(self) -> None:
                pass

        backend = Backend()
        assert isinstance(backend, CacheAdminProtocol)
        assert backend.get_stats() == {"hits": 2}

    def test_protocol_is_optional_for_data_plane_backends(self) -> None:
        """A normal cache backend need not expose operator counters."""

        class DataPlaneOnly:
            pass

        assert not isinstance(DataPlaneOnly(), CacheAdminProtocol)
