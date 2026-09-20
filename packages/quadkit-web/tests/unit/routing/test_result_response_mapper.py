"""Unit tests for ResultResponseMapper and the error_status decorator.

Verifies that domain errors are converted to the correct HTTP status codes
and that custom mappings registered via ``error_status`` take precedence
over the defaults.
"""

from __future__ import annotations

from quadkit import serialization as json
from typing import Any

import pytest

from quadkit.contracts.exceptions.domain import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from quadkit.web.routing.result_bridge import (
    _ERROR_STATUS_REGISTRY,
    ResultResponseMapper,
    error_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_registry() -> Any:
    """Snapshot the registry before each test and restore it afterwards.

    This prevents custom registrations from leaking between tests since
    ``_ERROR_STATUS_REGISTRY`` is a module-level mutable list.
    """
    snapshot = list(_ERROR_STATUS_REGISTRY)
    yield
    _ERROR_STATUS_REGISTRY.clear()
    _ERROR_STATUS_REGISTRY.extend(snapshot)


# ---------------------------------------------------------------------------
# Custom error type used in custom-mapping tests
# ---------------------------------------------------------------------------


class _PaymentDeclinedError(Exception):
    """Fictitious domain error used only in these tests."""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResultResponseMapperDefaults:
    def test_not_found_error_maps_to_404(self) -> None:
        error = NotFoundError("User not found")

        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 404

    def test_validation_error_maps_to_422(self) -> None:
        error = ValidationError("Invalid payload")

        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 422

    def test_permission_denied_error_maps_to_403(self) -> None:
        error = PermissionDeniedError("Access denied")

        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 403

    def test_response_body_contains_error_message(self) -> None:
        error = NotFoundError("Widget 99 not found")

        response = ResultResponseMapper.error_to_response(error)

        body = json.loads(response.body)
        assert "Widget 99 not found" in body["detail"]

    def test_response_body_includes_error_code(self) -> None:
        error = NotFoundError("Missing resource")

        response = ResultResponseMapper.error_to_response(error)

        body = json.loads(response.body)
        assert "not-found" in body["type"]

    def test_unknown_exception_falls_back_to_500(self) -> None:
        """Non-domain errors are server faults, not client errors."""
        error = ValueError("something unexpected")

        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 500

    def test_unregistered_domain_error_falls_back_to_400(self) -> None:
        """DomainErrors not in the registry are client faults."""
        from quadkit.contracts.exceptions.domain import WebError

        response = ResultResponseMapper.error_to_response(WebError("routing"))

        assert response.status_code == 400

    def test_non_exception_value_maps_to_400(self) -> None:
        """A non-exception Err value (e.g. a string) must default to 400."""
        response = ResultResponseMapper.error_to_response("raw error string")

        assert response.status_code == 400


class TestResultResponseMapperCustomRegistration:
    def test_register_adds_custom_mapping(self) -> None:
        ResultResponseMapper.register(_PaymentDeclinedError, 402)

        response = ResultResponseMapper.error_to_response(
            _PaymentDeclinedError("card declined")
        )

        assert response.status_code == 402

    def test_custom_mapping_takes_precedence_over_defaults(self) -> None:
        """Registrations are inserted at the front, so they win over built-ins."""
        # Register NotFoundError with a non-standard code to test precedence
        ResultResponseMapper.register(NotFoundError, 410)

        response = ResultResponseMapper.error_to_response(NotFoundError("gone"))

        assert response.status_code == 410

    def test_error_status_decorator_registers_mapping(self) -> None:
        """``@error_status(Err, code)`` must wire the mapping for the given error."""

        @error_status(_PaymentDeclinedError, 409)
        class _BillingController:
            pass

        # Decorator returns the class unchanged
        assert _BillingController is not None

        response = ResultResponseMapper.error_to_response(
            _PaymentDeclinedError("payment declined")
        )
        assert response.status_code == 409

    def test_error_status_decorator_preserves_decorated_class(self) -> None:
        """The ``@error_status`` decorator must return the class, not None."""

        @error_status(_PaymentDeclinedError, 402)
        class _SomeController:
            pass

        assert _SomeController.__name__ == "_SomeController"

    def test_validation_error_details_included_in_response_body(self) -> None:
        """ValidationError field errors must be serialised into the response body."""
        error = ValidationError("Bad input")
        error.add_error("email", "must be a valid email", "invalid_email")

        response = ResultResponseMapper.error_to_response(error)

        assert response.status_code == 422
        body = json.loads(response.body)
        # Details key should be present with field errors
        errors = body["errors"]
        assert len(errors) == 1
        assert errors[0]["field"] == "email"
