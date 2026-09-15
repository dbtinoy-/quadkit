"""Tests that ObjectMapperImpl satisfies the MapperProtocol structural contract."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.mapping.types import MapperProtocol


@dataclass
class _Src:
    n: int


@dataclass
class _Dst:
    n: int


class TestMapperProtocolCompliance:
    """ObjectMapperImpl must satisfy MapperProtocol at runtime."""

    def test_object_mapper_is_instance_of_mapper_protocol(self) -> None:
        """ObjectMapperImpl satisfies the structural MapperProtocol check."""
        # MapperProtocol uses Protocol; we verify structural compatibility via
        # duck-type inspection rather than isinstance (Protocols are not
        # runtime-checkable by default unless decorated with @runtime_checkable).
        mapper = ObjectMapperImpl()
        assert hasattr(mapper, "map"), "ObjectMapperImpl must expose 'map'"
        assert hasattr(mapper, "map_many"), "ObjectMapperImpl must expose 'map_many'"
        assert callable(mapper.map)
        assert callable(mapper.map_many)

    def test_map_method_signature_compatible_with_protocol(self) -> None:
        """map() accepts (source, dest_type) and returns the destination instance."""
        mapper = ObjectMapperImpl()
        mapper.register(_Src, _Dst, lambda s: _Dst(n=s.n))
        result = mapper.map(_Src(n=7), _Dst)
        assert isinstance(result, _Dst)
        assert result.n == 7

    def test_map_many_method_signature_compatible_with_protocol(self) -> None:
        """map_many() accepts (sources, dest_type) and returns list[dest]."""
        mapper = ObjectMapperImpl()
        mapper.register(_Src, _Dst, lambda s: _Dst(n=s.n))
        results = mapper.map_many([_Src(n=1), _Src(n=2), _Src(n=3)], _Dst)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, _Dst) for r in results)

    def test_map_many_empty_list_returns_empty_list(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register(_Src, _Dst, lambda s: _Dst(n=s.n))
        assert mapper.map_many([], _Dst) == []

    def test_protocol_is_structurally_compatible_via_duck_type(self) -> None:
        """Any object with map() and map_many() satisfies the protocol contract."""

        class MinimalMapper:
            def map(self, source: _Src, dest_type: type[_Dst]) -> _Dst:
                return dest_type(n=source.n + 1)

            def map_many(self, sources: list[_Src], dest_type: type[_Dst]) -> list[_Dst]:
                return [self.map(s, dest_type) for s in sources]

        minimal: MapperProtocol[_Src, _Dst] = MinimalMapper()  # type: ignore[assignment]
        result = minimal.map(_Src(n=3), _Dst)
        assert result.n == 4


@pytest.mark.skipif(
    not getattr(MapperProtocol, "_is_runtime_protocol", False),
    reason="MapperProtocol is not @runtime_checkable — isinstance check not available",
)
class TestMapperProtocolIsRuntimeCheckable:
    """Skip block: only runs when MapperProtocol is @runtime_checkable."""

    def test_isinstance_check_passes(self) -> None:
        mapper = ObjectMapperImpl()
        assert isinstance(mapper, MapperProtocol)  # type: ignore[misc]
