"""Exceptions for the catalog module.

Convention followed: **Exception hierarchy** — base domain exceptions live
in ``quadkit-contracts``; leaf exceptions live in the owning module.

```
NotFoundError (quadkit-contracts)
  └── ProductNotFoundError
```
"""

from __future__ import annotations

from quadkit.contracts.exceptions.domain import NotFoundError


class ProductNotFoundError(NotFoundError):
    """Raised when a SKU is not present in the catalog."""


__all__ = ["ProductNotFoundError"]
