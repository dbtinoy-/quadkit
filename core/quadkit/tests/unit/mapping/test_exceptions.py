"""Tests for exception wrapping in the mapping subsystem."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.mapping.exceptions import (
    MappingError,
    MappingExecutionError,
    MappingNotFoundError,
)


@dataclass
class _A:
    x: int


@dataclass
class _B:
    x: int


class TestMappingExceptionHierarchy:
    """MappingError is the base; subclasses are specific."""

    def test_mapping_not_found_is_mapping_error(self) -> None:
        exc = MappingNotFoundError(_A, _B)
        assert isinstance(exc, MappingError)

    def test_mapping_execution_is_mapping_error(self) -> None:
        exc = MappingExecutionError("boom")
        assert isinstance(exc, MappingError)

    def test_not_found_exposes_source_and_dest(self) -> None:
        exc = MappingNotFoundError(_A, _B)
        assert exc.source is _A
        assert exc.dest is _B

    def test_not_found_message_contains_type_names(self) -> None:
        exc = MappingNotFoundError(_A, _B)
        assert "_A" in str(exc)
        assert "_B" in str(exc)


class TestMapperExceptionWrapping:
    """Mapper function errors must be wrapped in MappingExecutionError."""

    def test_mapper_raising_value_error_is_wrapped(self) -> None:
        """A mapper that raises ValueError should produce MappingExecutionError."""
        mapper = ObjectMapperImpl()

        def bad_mapper(src: _A) -> _B:
            raise ValueError("something went wrong")

        mapper.register(_A, _B, bad_mapper)
        with pytest.raises(MappingExecutionError) as exc_info:
            mapper.map(_A(x=1), _B)

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_mapper_raising_runtime_error_is_wrapped(self) -> None:
        mapper = ObjectMapperImpl()

        def bad_mapper(src: _A) -> _B:
            raise RuntimeError("runtime failure")

        mapper.register(_A, _B, bad_mapper)
        with pytest.raises(MappingExecutionError) as exc_info:
            mapper.map(_A(x=1), _B)

        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_original_cause_message_is_preserved(self) -> None:
        mapper = ObjectMapperImpl()
        sentinel = ValueError("unique-sentinel-42")

        def bad_mapper(src: _A) -> _B:
            raise sentinel

        mapper.register(_A, _B, bad_mapper)
        with pytest.raises(MappingExecutionError) as exc_info:
            mapper.map(_A(x=10), _B)

        assert exc_info.value.__cause__ is sentinel

    def test_mapping_execution_error_is_not_re_wrapped(self) -> None:
        """MappingExecutionError raised inside a mapper propagates as-is."""
        mapper = ObjectMapperImpl()
        original = MappingExecutionError("already an execution error")

        def bad_mapper(src: _A) -> _B:
            raise original

        mapper.register(_A, _B, bad_mapper)
        with pytest.raises(MappingExecutionError) as exc_info:
            mapper.map(_A(x=1), _B)

        # Should be the exact same instance, not double-wrapped
        assert exc_info.value is original

    def test_no_mapping_raises_mapping_not_found_error(self) -> None:
        mapper = ObjectMapperImpl()
        with pytest.raises(MappingNotFoundError) as exc_info:
            mapper.map(_A(x=1), _B)

        assert exc_info.value.source is _A
        assert exc_info.value.dest is _B

    def test_successful_mapper_does_not_raise(self) -> None:
        mapper = ObjectMapperImpl()
        mapper.register(_A, _B, lambda s: _B(x=s.x * 2))
        result = mapper.map(_A(x=5), _B)
        assert result.x == 10
