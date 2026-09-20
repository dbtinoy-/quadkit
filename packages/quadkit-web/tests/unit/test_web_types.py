"""Tests for web types enums."""

import pytest
from quadkit.web.types import HTTPMethod, ContentType, StatusCode


class TestHTTPMethod:
    def test_get(self) -> None:
        assert HTTPMethod.GET == "GET"

    def test_post(self) -> None:
        assert HTTPMethod.POST == "POST"

    def test_put(self) -> None:
        assert HTTPMethod.PUT == "PUT"

    def test_delete(self) -> None:
        assert HTTPMethod.DELETE == "DELETE"

    def test_patch(self) -> None:
        assert HTTPMethod.PATCH == "PATCH"

    def test_head(self) -> None:
        assert HTTPMethod.HEAD == "HEAD"

    def test_options(self) -> None:
        assert HTTPMethod.OPTIONS == "OPTIONS"

    def test_trace(self) -> None:
        assert HTTPMethod.TRACE == "TRACE"


class TestContentType:
    def test_json(self) -> None:
        assert ContentType.JSON == "application/json"

    def test_form(self) -> None:
        assert ContentType.FORM == "application/x-www-form-urlencoded"

    def test_multipart(self) -> None:
        assert ContentType.MULTIPART == "multipart/form-data"

    def test_text(self) -> None:
        assert ContentType.TEXT == "text/plain"

    def test_html(self) -> None:
        assert ContentType.HTML == "text/html"

    def test_xml(self) -> None:
        assert ContentType.XML == "application/xml"


class TestStatusCode:
    def test_ok(self) -> None:
        assert StatusCode.OK == 200

    def test_created(self) -> None:
        assert StatusCode.CREATED == 201

    def test_accepted(self) -> None:
        assert StatusCode.ACCEPTED == 202

    def test_no_content(self) -> None:
        assert StatusCode.NO_CONTENT == 204

    def test_bad_request(self) -> None:
        assert StatusCode.BAD_REQUEST == 400

    def test_unauthorized(self) -> None:
        assert StatusCode.UNAUTHORIZED == 401

    def test_forbidden(self) -> None:
        assert StatusCode.FORBIDDEN == 403

    def test_not_found(self) -> None:
        assert StatusCode.NOT_FOUND == 404

    def test_internal_server_error(self) -> None:
        assert StatusCode.INTERNAL_SERVER_ERROR == 500
