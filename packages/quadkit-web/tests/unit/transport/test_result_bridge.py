"""Tests for ResultResponseMapper covering all result_to_response cases."""
from __future__ import annotations

import pytest

from quadkit.contracts.exceptions.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from quadkit.result import Err, Ok
from quadkit.web.exceptions import HTTPError, NotFoundError as WebNotFoundError
from quadkit.web.routing.result_bridge import ResultResponseMapper
from quadkit.web.transport.responses import JSONResponse


class TestResultResponseMapperToResponse:
    """Test ResultResponseMapper.to_response() covers all result_to_response cases."""

    def setup_method(self) -> None:
        """Reset registry before each test."""
        self.mapper = ResultResponseMapper()

    def test_ok_result_returns_200_with_data(self) -> None:
        """Ok result should return 200 with data wrapped in response."""
        result = Ok({"id": 1, "name": "test"})
        response = self.mapper.to_response(result)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

    def test_ok_result_custom_status(self) -> None:
        """Ok result should support custom success_status."""
        result = Ok("created")
        response = self.mapper.to_response(result, success_status=201)

        assert response.status_code == 201

    def test_not_found_error_returns_404(self) -> None:
        """NotFoundError should map to 404."""
        result = Err(NotFoundError("User not found"))
        response = self.mapper.to_response(result)

        assert response.status_code == 404

    def test_validation_error_returns_422(self) -> None:
        """ValidationError should map to 422."""
        result = Err(ValidationError("Invalid input"))
        response = self.mapper.to_response(result)

        assert response.status_code == 422

    def test_authentication_error_returns_401(self) -> None:
        """AuthenticationError should map to 401."""
        result = Err(AuthenticationError("Invalid credentials"))
        response = self.mapper.to_response(result)

        assert response.status_code == 401

    def test_authorization_error_returns_403(self) -> None:
        """AuthorizationError should map to 403."""
        result = Err(AuthorizationError("Forbidden"))
        response = self.mapper.to_response(result)

        assert response.status_code == 403

    def test_permission_denied_error_returns_403(self) -> None:
        """PermissionDeniedError should map to 403."""
        result = Err(PermissionDeniedError("Permission denied"))
        response = self.mapper.to_response(result)

        assert response.status_code == 403

    def test_conflict_error_returns_409(self) -> None:
        """ConflictError should map to 409."""
        result = Err(ConflictError("Resource conflict"))
        response = self.mapper.to_response(result)

        assert response.status_code == 409

    def test_rate_limit_error_returns_429(self) -> None:
        """RateLimitError should map to 429."""
        result = Err(RateLimitError("Rate limit exceeded"))
        response = self.mapper.to_response(result)

        assert response.status_code == 429

    def test_generic_domain_error_returns_400(self) -> None:
        """Generic DomainError should map to 400."""
        result = Err(DomainError("Something went wrong"))
        response = self.mapper.to_response(result)

        assert response.status_code == 400

    def test_mro_aware_matching_prefers_specific_type(self) -> None:
        """Should use MRO-aware matching for subclass errors."""
        # NotFoundError extends DomainError, should match 404, not 400
        result = Err(NotFoundError("not found"))
        response = self.mapper.to_response(result)

        assert response.status_code == 404

    def test_unknown_exception_returns_500(self) -> None:
        """Non-domain exceptions are server faults and default to 500."""
        result = Err(ValueError("some error"))
        response = self.mapper.to_response(result)

        assert response.status_code == 500

    def test_unregistered_domain_error_returns_400(self) -> None:
        """DomainErrors outside the registry are client faults (400)."""
        from quadkit.contracts.exceptions.domain import WebError

        result = Err(WebError("routing"))
        response = self.mapper.to_response(result)

        assert response.status_code == 400

    def test_custom_registered_error_type(self) -> None:
        """Custom registered error types should use registered status code."""
        class CustomError(Exception):
            pass

        ResultResponseMapper.register(CustomError, 418)
        result = Err(CustomError("I'm a teapot"))
        response = self.mapper.to_response(result)

        assert response.status_code == 418

    def test_response_includes_detail_field(self) -> None:
        """Response body must contain RFC 7807 'detail' field with message."""
        result = Err(NotFoundError("User not found"))
        response = self.mapper.to_response(result)

        import json
        body = json.loads(response.body.decode())
        assert "detail" in body
        assert "User not found" in body["detail"]

    def test_response_is_rfc7807_format(self) -> None:
        """Response body must include all RFC 7807 required fields."""
        result = Err(NotFoundError("User not found"))
        response = self.mapper.to_response(result)

        import json
        body = json.loads(response.body.decode())
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body

    def test_non_exception_error_returns_400(self) -> None:
        """Non-exception error values should default to 400."""
        result = Err("just a string error")
        response = self.mapper.to_response(result)

        assert response.status_code == 400


class TestErrorToResponse:
    """Test ResultResponseMapper.error_to_response() directly."""

    def test_error_to_response_not_found(self) -> None:
        """error_to_response should convert NotFoundError to 404 response."""
        error = NotFoundError("not found")
        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 404

    def test_error_to_response_validation_error(self) -> None:
        """error_to_response should convert ValidationError to 422 response."""
        error = ValidationError("invalid")
        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 422

    def test_error_to_response_with_details(self) -> None:
        """error_to_response should produce RFC 7807 format body."""
        error = ValidationError("validation failed")
        response = ResultResponseMapper.error_to_response(error)

        import json
        body = json.loads(response.body.decode())
        assert "type" in body
        assert "detail" in body
        assert "validation failed" in body["detail"]

    def test_error_to_response_non_exception(self) -> None:
        """error_to_response should handle non-exception values."""
        response = ResultResponseMapper.error_to_response("some error message")

        assert response.status_code == 400


class TestResultBridgeCompatibilityWithMapping:
    """Verify ResultResponseMapper covers all result_to_response patterns."""

    def test_mapper_handles_all_result_to_response_cases(self) -> None:
        """Verify mapper handles tuple patterns that result_to_response handled."""
        # Case 1: Ok with default status
        result1 = Ok({"id": 1})
        response1 = self.mapper.to_response(result1)
        assert response1.status_code == 200

        # Case 2: Ok with custom status
        result2 = Ok("created")
        response2 = self.mapper.to_response(result2, success_status=201)
        assert response2.status_code == 201

        # Case 3: Err with contracts NotFoundError
        result3 = Err(NotFoundError("not found"))
        response3 = self.mapper.to_response(result3)
        assert response3.status_code == 404

        # Case 4: Err with generic exception
        result4 = Err(RuntimeError("crash"))
        response4 = self.mapper.to_response(result4)
        # RuntimeError is not a DomainError — server fault
        assert response4.status_code == 500

        # Case 5: Err with string
        result5 = Err("string error")
        response5 = self.mapper.to_response(result5)
        assert response5.status_code == 400
        
        # Case 6: Err with web HTTPError (should use status_code from error)
        result6 = Err(WebNotFoundError("not found"))
        response6 = self.mapper.to_response(result6)
        # Web's NotFoundError extends HTTPError with status_code=404
        # The mapper checks for Exception instance, so it should recognize it
        assert response6.status_code == 404

    def setup_method(self) -> None:
        """Setup mapper for tests."""
        self.mapper = ResultResponseMapper()
