"""Tests for ProblemDetail RFC 7807 error model."""
from __future__ import annotations

import pytest

from quadkit.web.errors.problem_detail import ProblemDetail


class TestProblemDetailToDict:
    """Tests for ProblemDetail.to_dict()."""

    def test_minimal_to_dict(self) -> None:
        pd = ProblemDetail(title="Oops", status=400, detail="Bad input")
        result = pd.to_dict()
        assert result["title"] == "Oops"
        assert result["status"] == 400
        assert result["detail"] == "Bad input"
        assert result["type"] == "about:blank"
        assert "instance" not in result
        assert "errors" not in result

    def test_instance_included_when_set(self) -> None:
        pd = ProblemDetail(status=404, title="NF", detail="d", instance="/users/99")
        result = pd.to_dict()
        assert result["instance"] == "/users/99"

    def test_errors_included_when_set(self) -> None:
        errors = [{"field": "email", "msg": "invalid"}]
        pd = ProblemDetail(status=400, title="Validation", detail="d", errors=errors)
        result = pd.to_dict()
        assert result["errors"] == errors

    def test_empty_errors_not_included(self) -> None:
        pd = ProblemDetail(status=400, title="X", detail="d", errors=[])
        result = pd.to_dict()
        assert "errors" not in result


class TestProblemDetailFromException:
    """Tests for ProblemDetail.from_exception() factory."""

    def test_detail_is_exception_message_for_4xx(self) -> None:
        exc = ValueError("bad value")
        pd = ProblemDetail.from_exception(exc, status=400)
        assert pd.detail == "bad value"
        assert pd.status == 400

    def test_detail_hidden_for_5xx_when_not_debug(self) -> None:
        exc = RuntimeError("internal secret")
        pd = ProblemDetail.from_exception(exc, status=500, debug=False)
        assert "internal secret" not in pd.detail
        assert pd.detail == "An unexpected error occurred"

    def test_detail_exposed_for_5xx_when_debug(self) -> None:
        exc = RuntimeError("internal secret")
        pd = ProblemDetail.from_exception(exc, status=500, debug=True)
        assert pd.detail == "internal secret"

    def test_extra_kwargs_forwarded(self) -> None:
        exc = ValueError("x")
        pd = ProblemDetail.from_exception(exc, status=400, title="Custom Title")
        assert pd.title == "Custom Title"


class TestProblemDetailFactories:
    """Tests for the named factory class-methods."""

    def test_validation_error(self) -> None:
        errors = [{"field": "name"}]
        pd = ProblemDetail.validation_error(errors)
        assert pd.status == 400
        assert pd.type == "urn:quadkit:validation-error"
        assert pd.errors == errors

    def test_validation_error_custom_detail(self) -> None:
        pd = ProblemDetail.validation_error([], detail="Custom message")
        assert pd.detail == "Custom message"

    def test_not_found(self) -> None:
        pd = ProblemDetail.not_found("User")
        assert pd.status == 404
        assert "User" in pd.detail
        assert pd.type == "urn:quadkit:not-found"

    def test_not_found_with_identifier(self) -> None:
        pd = ProblemDetail.not_found("User", identifier="42")
        assert "42" in pd.detail

    def test_bad_request(self) -> None:
        pd = ProblemDetail.bad_request("Invalid email")
        assert pd.status == 400
        assert pd.detail == "Invalid email"
        assert pd.type == "urn:quadkit:bad-request"

    def test_bad_request_with_errors(self) -> None:
        errors = [{"field": "email"}]
        pd = ProblemDetail.bad_request("x", errors=errors)
        assert pd.errors == errors

    def test_internal_error(self) -> None:
        pd = ProblemDetail.internal_error()
        assert pd.status == 500
        assert pd.type == "urn:quadkit:internal-error"

    def test_internal_error_custom_detail(self) -> None:
        pd = ProblemDetail.internal_error(detail="DB down")
        assert pd.detail == "DB down"
