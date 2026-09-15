"""Tests for ResultResponseMapper backward compatibility.

This file tests that ResultResponseMapper properly replaces the old
result_to_response() function with improved response formatting.
"""
from __future__ import annotations

import json

from quadkit.result import Ok, Err
from quadkit.web.routing.result_bridge import ResultResponseMapper
from quadkit.web.exceptions import NotFoundError


class TestResultResponseMapperBackwardCompatibility:
    """Verify ResultResponseMapper handles all result_to_response patterns."""

    def setup_method(self) -> None:
        """Initialize mapper for each test."""
        self.mapper = ResultResponseMapper()

    def test_ok_result_returns_response_with_data(self) -> None:
        """Ok result should return 200 response with data."""
        result = Ok({"id": 1})
        response = self.mapper.to_response(result)
        assert response.status_code == 200
        body = json.loads(response.body.decode())
        assert body == {"id": 1}

    def test_ok_result_custom_status(self) -> None:
        """Ok result should support custom success_status."""
        result = Ok("created")
        response = self.mapper.to_response(result, success_status=201)
        assert response.status_code == 201

    def test_err_with_http_error(self) -> None:
        """Err with web HTTPError should map to appropriate status."""
        exc = NotFoundError("User not found")
        result = Err(exc)
        response = self.mapper.to_response(result)
        assert response.status_code == 404
        body = json.loads(response.body.decode())
        assert "detail" in body

    def test_err_with_generic_exception(self) -> None:
        """Non-domain exceptions are server faults and default to 500."""
        result = Err(RuntimeError("crash"))
        response = self.mapper.to_response(result)
        assert response.status_code == 500
        body = json.loads(response.body.decode())
        assert "detail" in body

    def test_err_with_string_error(self) -> None:
        """Err with string error should return 400 response."""
        result = Err("something went wrong")
        response = self.mapper.to_response(result)
        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert "detail" in body
