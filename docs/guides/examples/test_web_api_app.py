"""Tests for web_api_app.py — runs from docs/guides/examples in CI."""

import pytest

from quadkit.testing import WebTestBed

from web_api_app import create_app


@pytest.mark.asyncio
async def test_path_and_query_binding():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/notes/1", params={"verbose": "true"})
        response.assert_status(200)
        assert response.json["id"] == 1
        assert response.json["verbose"] is True


@pytest.mark.asyncio
async def test_query_type_conversion_and_listing():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/notes", params={"limit": "5"})
        response.assert_status(200)
        assert response.json["count"] == len(response.json["items"])


@pytest.mark.asyncio
async def test_model_body_validates_and_persists():
    async with WebTestBed(create_app()) as bed:
        created = bed.post("/notes", json={"title": "from test"})
        created.assert_status(201)
        assert created.json["title"] == "from test"

        fetched = bed.get(f"/notes/{created.json['id']}")
        assert fetched.json["title"] == "from test"


@pytest.mark.asyncio
async def test_model_body_validation_errors_are_422():
    async with WebTestBed(create_app()) as bed:
        response = bed.post("/notes", json={"body": "missing the title"})
        response.assert_status(422)
        # RFC 7807 problem body with one entry per invalid field
        errors = response.json["errors"]
        assert errors[0]["field"] == "payload.title"
        assert errors[0]["code"] == "missing"
