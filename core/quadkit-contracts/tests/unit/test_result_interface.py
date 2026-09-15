"""Tests for Result protocol in quadkit-contracts.

Note: This tests the protocol/interface definitions, not implementations.
The concrete implementations (Ok, Err, Result) are in quadkit.contracts.core.result.
"""


import pytest
from quadkit.contracts.core.result import Ok, Err, Result


class TestResultProtocol:
    """Tests for Result protocol."""

    def test_result_is_concrete_class(self) -> None:
        """Test Result is a concrete class with expected methods."""
        assert hasattr(Result, "is_ok")
        assert hasattr(Result, "is_err")
        assert hasattr(Result, "unwrap")
        assert hasattr(Result, "unwrap_err")
        assert hasattr(Result, "map_sync")
        assert hasattr(Result, "map")
        assert hasattr(Result, "and_then")
        assert hasattr(Result, "or_else")

    def test_result_has_is_ok_method(self) -> None:
        """Test Result has is_ok method."""
        assert hasattr(Result, "is_ok")
        assert callable(Result.is_ok)

    def test_result_has_is_err_method(self) -> None:
        """Test Result has is_err method."""
        assert hasattr(Result, "is_err")
        assert callable(Result.is_err)

    def test_result_has_unwrap_method(self) -> None:
        """Test Result has unwrap method."""
        assert hasattr(Result, "unwrap")
        assert callable(Result.unwrap)

    def test_result_has_unwrap_err_method(self) -> None:
        """Test Result has unwrap_err method."""
        assert hasattr(Result, "unwrap_err")
        assert callable(Result.unwrap_err)

    def test_ok_instantiation(self) -> None:
        """Test Ok can be instantiated."""
        ok = Ok(42)
        assert ok.is_ok() is True
        assert ok.is_err() is False
        assert ok.unwrap() == 42

    def test_err_instantiation(self) -> None:
        """Test Err can be instantiated."""
        err = Err("error")
        assert err.is_ok() is False
        assert err.is_err() is True
        assert err.unwrap_err() == "error"


class TestResultTypeVars:
    """Tests for Result type variables."""

    def test_result_is_generic(self) -> None:
        """Test Result is a Generic type."""
        # Result should be generic over T (value) and E (error)
        assert hasattr(Result, "__orig_bases__")