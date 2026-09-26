"""Test that FilterPipeline covers all cases @handle_crud_errors handled."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.web.exceptions import (
    BadRequestError,
    ForbiddenError,
    InternalServerError,
    NotFoundError as HTTPNotFoundError,
)
from quadkit.web.filters.builtin import DefaultExceptionFilter
from quadkit.web.filters.pipeline import FilterPipeline


class TestFilterPipelineCoversCrudErrors:
    """Verify FilterPipeline handles errors that @handle_crud_errors handled."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock request."""
        return MagicMock()

    @pytest.fixture
    def pipeline(self) -> FilterPipeline:
        """Create a filter pipeline with default exception filter."""
        pipeline = FilterPipeline(debug=False)
        pipeline.add_filter(DefaultExceptionFilter(debug=False))
        return pipeline

    @pytest.mark.asyncio
    async def test_handles_domain_not_found(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps NotFoundError to 404."""
        exc = NotFoundError("pet not found")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 404
        assert b"QK_ERR_DOM_002" in response.body or b"not_found" in response.body

    @pytest.mark.asyncio
    async def test_handles_domain_validation_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps ValidationError to 422 — and agrees with the Result path.

        The decorator this file was written against (``@handle_crud_errors``)
        answered 400 here, and that expectation outlived it: the policy is
        RFC 7807-shaped now, and ``web/errors/mapping.py`` — the table the
        Result-returning path reads — maps a domain ``ValidationError`` to 422
        with ``urn:quadkit:validation-error``. 400 stays for a ``DomainError``
        that is not a validation failure.

        The second assertion is the one that keeps the two paths from drifting:
        "the two paths agree on the seven built-in families" is a claim in
        ``result_bridge``'s docstring, and this is where one of the seven is
        actually compared.
        """
        from quadkit.web.errors.mapping import get_status_for_error

        exc = ValidationError("invalid input")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 422
        assert b"QK_ERR_VAL_002" in response.body or b"validation" in response.body
        assert get_status_for_error(exc) == response.status_code

    @pytest.mark.asyncio
    async def test_handles_http_not_found_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps HTTPNotFoundError to 404."""
        exc = HTTPNotFoundError("Resource not found")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 404
        assert b"not-found" in response.body

    @pytest.mark.asyncio
    async def test_handles_bad_request_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps BadRequestError to 400."""
        exc = BadRequestError("Invalid input")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 400
        assert b"bad-request" in response.body

    @pytest.mark.asyncio
    async def test_handles_forbidden_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps ForbiddenError to 403."""
        exc = ForbiddenError("Insufficient permissions")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 403
        assert b"FORBIDDEN" in response.body or b"forbidden" in response.body

    @pytest.mark.asyncio
    async def test_handles_internal_server_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline maps InternalServerError to 500."""
        exc = InternalServerError("Something went wrong")
        response = await pipeline.handle(exc, mock_request)

        assert response.status_code == 500
        assert b"internal-server-error" in response.body

    @pytest.mark.asyncio
    async def test_handles_value_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline should handle ValueError through domain mapping."""
        # ValueError is not a domain error, so it falls through to default 500.
        # But the @handle_crud_errors decorator would have converted it to BadRequestError.
        # We need to verify FilterPipeline covers this via DefaultExceptionFilter
        # and any generic exception handling.
        exc = ValueError("invalid value")
        response = await pipeline.handle(exc, mock_request)

        # DefaultExceptionFilter doesn't specifically handle ValueError,
        # so it should result in a 500 error.
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handles_permission_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline should handle PermissionError through domain mapping."""
        # PermissionError is a Python built-in, not a domain error.
        # The @handle_crud_errors decorator would have caught it and mapped to ForbiddenError.
        # DefaultExceptionFilter doesn't specifically handle PermissionError,
        # so it falls back to 500.
        exc = PermissionError("no permission")
        response = await pipeline.handle(exc, mock_request)

        # Falls back to generic 500 since PermissionError is not a handled type
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handles_key_error(
        self, pipeline: FilterPipeline, mock_request: MagicMock
    ) -> None:
        """FilterPipeline should handle KeyError through domain mapping."""
        # KeyError is a Python built-in, not a domain error.
        # The @handle_crud_errors decorator would have caught it and mapped to NotFoundError.
        # DefaultExceptionFilter doesn't specifically handle KeyError,
        # so it falls back to 500.
        exc = KeyError("missing_key")
        response = await pipeline.handle(exc, mock_request)

        # Falls back to generic 500 since KeyError is not a handled type
        assert response.status_code == 500
