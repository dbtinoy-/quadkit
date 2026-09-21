"""Exceptions for the orders module.

Convention followed: **Exception hierarchy** — base domain exceptions live
in ``quadkit-contracts``; leaf exceptions live in the owning module.

```
DomainError (quadkit-contracts)
  └── OrderError
        ├── UnknownProductError   — order line names a SKU catalog does not have
        └── InsufficientStockError — catalog could not reserve the requested qty
NotFoundError (quadkit-contracts)
  └── OrderNotFoundError
```
"""

from __future__ import annotations

from quadkit.contracts.exceptions.domain import DomainError, NotFoundError


class OrderError(DomainError):
    """Base class for orders-module domain errors."""


class UnknownProductError(OrderError):
    """Raised when an order line references a SKU the catalog does not have."""


class InsufficientStockError(OrderError):
    """Raised when the catalog cannot reserve the requested quantity."""


class OrderNotFoundError(NotFoundError):
    """Raised when an order id does not exist."""


__all__ = [
    "InsufficientStockError",
    "OrderError",
    "OrderNotFoundError",
    "UnknownProductError",
]
