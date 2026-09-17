# Error handling

Quadkit has one response format for every failure: an
RFC 7807 *problem details* body
(`Content-Type: application/problem+json`) with `type`, `title`,
`status`, and `detail` — plus an `errors` list of per-field entries on
validation failures. Your job is choosing *how to signal* the error;
the format is handled everywhere.

The example below is `docs/guides/examples/error_handling_app.py`,
kept byte-identical with this page and executed in CI.

<!-- snippet: examples/error_handling_app.py -->
```python
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
```

## Two ways to signal an error

**Return a `Result`** (the declarative way). Annotate the route as
returning `Result[T, E]` and return `Ok(value)` / `Err(domain_error)`.
`Ok` unwraps straight to the JSON body with the success status; `Err`
maps the error through a status table. Failures stay in the type
signature — excellent for expected business failures.

**Raise `HTTPError`** (the direct way) for exact control of status,
`detail`, and a machine-readable `code`, which the response repeats in
its `type` URN:

```json
{"type": "urn:quadkit:payment.declined", "title": "card declined",
 "status": 402, "detail": "card declined"}
```

Both produce problem bodies; pick per route. `Result` communicates
intent in the signature, `HTTPError` is the escape hatch anywhere in
the code path.

## The default mapping table

`Err()`-wrapped errors map through these defaults:

| Error type (from `quadkit.contracts.exceptions`) | Status |
| --- | --- |
| `NotFoundError` | 404 |
| `ValidationError` | 422 |
| `AuthenticationError` | 401 |
| `AuthorizationError`, `PermissionDeniedError` | 403 |
| `ConflictError` | 409 |
| `RateLimitError` | 429 |
| `DomainError` (and any unmapped subclass) | 400 |

`@error_status(MyError, 400)` on the controller class overrides a
specific mapping — custom registrations take precedence over defaults,
as the example's 402 demonstrates. Problem `type` URNs derive from the
error class name (`PaymentDeclinedError` → `urn:quadkit:payment-declined`).

## Raised exceptions still produce problem bodies

Throwing out of a controller instead of returning `Err` is not a
loophole: a raised `quadkit.web.NotFoundError` answers `404` with the
same problem body, and a raised unmapped domain exception answers `400`.
Unexpected exceptions are contained rather than exposed: they answer
`500` with a minimal body —
`{"success": false, "error": {"type": "internal_server_error", ...}}` —
that deliberately reveals nothing about the internals. (In tests,
`WebTestBed(..., raise_server_exceptions=True)` — the default — re-raises
unexpected exceptions so you see the original traceback; the error
expectations above are unaffected.)

**Validation is automatic**: a request body that fails pydantic
validation returns `422` with an `errors` list naming every bad field,
before your route runs at all.

## Next steps

- [Web API guide](./web-api.md) — the input binding that produces the
  422 shape.
- [Contracts](../concepts/contracts.md) — the `Result` type and the
  exception taxonomy.
