from __future__ import annotations

from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.contracts.exceptions.infra import InfrastructureError
from quadkit.middleware.core.exception_filters import (
    InfrastructureExceptionFilter,
    NotFoundExceptionFilter,
    ValidationExceptionFilter,
)


class TestValidationExceptionFilter:
    def test_can_handle_validation_error(self) -> None:
        f = ValidationExceptionFilter()
        assert f.can_handle(ValidationError("bad input")) is True

    def test_cannot_handle_other_errors(self) -> None:
        f = ValidationExceptionFilter()
        assert f.can_handle(ValueError("unrelated")) is False

    def test_handle_returns_structured_error(self) -> None:
        f = ValidationExceptionFilter()
        exc = ValidationError("field 'email' is required")
        result = f.handle(exc, {"path": "/api/users"})
        assert result["error"] == "validation_error"
        assert result["status"] == 422
        assert "email" in result["details"]


class TestNotFoundExceptionFilter:
    def test_can_handle_not_found_error(self) -> None:
        f = NotFoundExceptionFilter()
        assert f.can_handle(NotFoundError("User not found")) is True

    def test_cannot_handle_other_errors(self) -> None:
        f = NotFoundExceptionFilter()
        assert f.can_handle(ValueError("unrelated")) is False

    def test_handle_returns_404(self) -> None:
        f = NotFoundExceptionFilter()
        result = f.handle(NotFoundError("User 123 not found"), {})
        assert result["status"] == 404
        assert result["error"] == "not_found"


class TestInfrastructureExceptionFilter:
    def test_can_handle_infrastructure_error(self) -> None:
        f = InfrastructureExceptionFilter()
        assert f.can_handle(InfrastructureError("db down")) is True

    def test_cannot_handle_domain_errors(self) -> None:
        f = InfrastructureExceptionFilter()
        assert f.can_handle(ValidationError("bad")) is False

    def test_handle_returns_500(self) -> None:
        f = InfrastructureExceptionFilter()
        result = f.handle(InfrastructureError("connection refused"), {})
        assert result["status"] == 500
        assert result["error"] == "internal_error"
