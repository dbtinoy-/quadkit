"""Tests for error_handling_app.py — runs from docs/guides/examples in CI."""

import pytest

from quadkit.testing import WebTestBed

from error_handling_app import create_app


@pytest.mark.asyncio
async def test_ok_unwraps_to_200():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/price")
        response.assert_status(200)
        assert response.json == {"amount": 25, "currency": "usd"}


@pytest.mark.asyncio
async def test_default_mapping_not_found_is_404():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/items/7/price")
        response.assert_status(404)
        assert response.json["type"] == "urn:quadkit:not-found"
        assert response.json["status"] == 404


@pytest.mark.asyncio
async def test_custom_error_status_mapping():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/charge")
        assert response.status_code == 402
        assert response.json["type"] == "urn:quadkit:payment-declined"


@pytest.mark.asyncio
async def test_http_error_direct_control():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/charge-exact")
        assert response.status_code == 402
        assert response.json["type"] == "urn:quadkit:payment.declined"
        assert response.json["detail"] == "card declined"
