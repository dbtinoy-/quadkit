"""Runnable companion to docs/guides/error-handling.md.

Three verified error paths, one file: Result-returning routes mapped by
the default error table, a custom ``@error_status`` mapping, and a
directly-raised ``HTTPError``. Every error body is RFC 7807
``application/problem+json``:

    pytest test_error_handling_app.py
"""

from quadkit import Application, Err, Ok, Result
from quadkit.contracts.exceptions import DomainError, NotFoundError
from quadkit.web import Controller, HTTPError, WebModule, error_status, get


class PaymentDeclinedError(DomainError):
    """The card issuer declined this transaction."""


@error_status(PaymentDeclinedError, 402)  # overrides the domain default 400
class BillingController(Controller):
    @get("/price")
    async def price(self) -> Result[dict, DomainError]:
        """``Ok`` unwraps to a 200 JSON body."""
        return Ok({"amount": 25, "currency": "usd"})

    @get("/items/{item_id}/price")
    async def item_price(self, item_id: int) -> Result[dict, DomainError]:
        """``Err(NotFoundError(...))`` maps to 404 via the default table."""
        return Err(NotFoundError(f"no price for item {item_id}"))

    @get("/charge")
    async def charge(self) -> Result[dict, DomainError]:
        """Custom mapping: this domain error answers 402, not 400."""
        return Err(PaymentDeclinedError("issuer said no"))

    @get("/charge-exact")
    async def charge_exact(self) -> dict:
        """Raise an HTTP error directly for exact status/code control."""
        raise HTTPError(status_code=402, detail="card declined",
                        code="payment.declined")


def create_app() -> Application:
    app = Application()
    app.add_modules([WebModule.configure(controllers=[BillingController])])
    return app


app = create_app()
