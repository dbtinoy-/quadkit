"""Unit tests for middleware exceptions."""

import pytest

from quadkit.middleware.exceptions import (
    MiddlewareAuthError,
    MiddlewareChainError,
    MiddlewareCircuitOpenError,
    MiddlewareConfigurationError,
    MiddlewareError,
    MiddlewareExecutionError,
    MiddlewarePolicyError,
    MiddlewareRateLimitError,
    MiddlewareTimeoutError,
)


class TestMiddlewareError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareError, Exception)

    def test_code(self) -> None:
        assert MiddlewareError._code == "QK_ERR_MW_002"


class TestMiddlewarePolicyError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewarePolicyError, Exception)

    def test_code(self) -> None:
        assert MiddlewarePolicyError._code == "QK_ERR_MW_003"


class TestMiddlewareExecutionError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareExecutionError, MiddlewareError)

    def test_code(self) -> None:
        assert MiddlewareExecutionError._code == "QK_ERR_MW_004"


class TestMiddlewareConfigurationError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareConfigurationError, MiddlewareError)

    def test_code(self) -> None:
        assert MiddlewareConfigurationError._code == "QK_ERR_MW_005"


class TestMiddlewareChainError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareChainError, MiddlewareError)

    def test_code(self) -> None:
        assert MiddlewareChainError._code == "QK_ERR_MW_006"


class TestMiddlewareTimeoutError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareTimeoutError, MiddlewareError)

    def test_code(self) -> None:
        assert MiddlewareTimeoutError._code == "QK_ERR_MW_007"


class TestMiddlewareAuthError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareAuthError, MiddlewarePolicyError)

    def test_code(self) -> None:
        assert MiddlewareAuthError._code == "QK_ERR_MW_008"


class TestMiddlewareRateLimitError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareRateLimitError, MiddlewarePolicyError)

    def test_code(self) -> None:
        assert MiddlewareRateLimitError._code == "QK_ERR_MW_009"


class TestMiddlewareCircuitOpenError:
    def test_inheritance(self) -> None:
        assert issubclass(MiddlewareCircuitOpenError, MiddlewareError)

    def test_code(self) -> None:
        assert MiddlewareCircuitOpenError._code == "QK_ERR_MW_010"