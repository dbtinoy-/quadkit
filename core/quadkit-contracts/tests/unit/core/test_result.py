"""Tests for result module."""

from __future__ import annotations

from quadkit.contracts.core.result import Result


class TestResultProtocol:
    """Tests for Result protocol."""

    def test_is_ok_abstract(self) -> None:
        assert hasattr(Result, "is_ok")

    def test_is_err_abstract(self) -> None:
        assert hasattr(Result, "is_err")

    def test_unwrap_abstract(self) -> None:
        assert hasattr(Result, "unwrap")

    def test_unwrap_err_abstract(self) -> None:
        assert hasattr(Result, "unwrap_err")

    def test_unwrap_or_abstract(self) -> None:
        assert hasattr(Result, "unwrap_or")

    def test_unwrap_or_else_abstract(self) -> None:
        assert hasattr(Result, "unwrap_or_else")

    def test_map_sync_abstract(self) -> None:
        assert hasattr(Result, "map_sync")

    def test_map_err_abstract(self) -> None:
        assert hasattr(Result, "map_err")

    def test_and_then_sync_abstract(self) -> None:
        assert hasattr(Result, "and_then_sync")

    def test_or_else_sync_abstract(self) -> None:
        assert hasattr(Result, "or_else_sync")

    def test_expect_abstract(self) -> None:
        assert hasattr(Result, "expect")

    def test_match_abstract(self) -> None:
        assert hasattr(Result, "match")

    def test_map_async_abstract(self) -> None:
        assert hasattr(Result, "map")

    def test_and_then_async_abstract(self) -> None:
        assert hasattr(Result, "and_then")

    def test_or_else_async_abstract(self) -> None:
        assert hasattr(Result, "or_else")
