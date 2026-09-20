"""Feature tour: domain errors become HTTP responses — no try/except.

A handler returns ``Result[T, DomainError]`` and the request pipeline does
the mapping: ``Ok`` serializes to JSON, ``Err`` flows through the
``ResultResponseMapper`` registry — ``NotFoundError`` → 404, any other
``DomainError`` → 400. One decorator, ``@error_status(PaymentDeclinedError, 402)``,
teaches the registry a custom status. The controller never touches
response plumbing.
"""

import pytest

from quadkit import Application, DomainError, Err, NotFoundError, Ok, Result
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, error_status, get


class PaymentDeclinedError(DomainError):
    """Domain-specific failure — the registry knows where it goes."""


class AmountOutOfRangeError(DomainError):
    """No registration: lands on the DomainError default (400)."""


@error_status(PaymentDeclinedError, 402)
class BillingController(Controller):
    @get("/invoices/{invoice_id}")
    async def invoice(self, invoice_id: str) -> Result[dict, DomainError]:
        if invoice_id == "missing":
            return Err(NotFoundError("no such invoice"))
        if invoice_id == "declined":
            return Err(PaymentDeclinedError("card refused"))
        if invoice_id == "oversized":
            return Err(AmountOutOfRangeError("exceeds limit"))
        return Ok({"id": invoice_id, "total": 42})


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[BillingController]))
    return app


@pytest.mark.asyncio
async def test_result_mapping_end_to_end() -> None:
    async with WebTestBed(create_app()) as bed:
        ok = bed.get("/invoices/inv-7")
        assert ok.status_code == 200
        assert ok.json == {"id": "inv-7", "total": 42}

        missing = bed.get("/invoices/missing")
        assert missing.status_code == 404  # NotFoundError, registry default

        declined = bed.get("/invoices/declined")
        assert declined.status_code == 402  # PaymentDeclinedError, via @error_status

        oversized = bed.get("/invoices/oversized")
        assert oversized.status_code == 400  # AmountOutOfRangeError → base default
