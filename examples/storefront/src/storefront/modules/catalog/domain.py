"""Domain model for the catalog module.

Convention followed: **Value type** — ``Product`` is a frozen dataclass
carrying no behavior beyond serialization. It crosses the module boundary
freely as a return value of ``ProductCatalogProtocol`` methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    """One catalog entry.

    Attributes:
        sku: Stock-keeping unit — the catalog's primary key.
        name: Display name.
        unit_price: Price per unit.
        stock: Units currently available.
    """

    sku: str
    name: str
    unit_price: Decimal
    stock: int

    def to_payload(self) -> dict[str, object]:
        """Return the JSON-safe representation used by the API layer."""
        return {
            "sku": self.sku,
            "name": self.name,
            "unit_price": str(self.unit_price),
            "stock": self.stock,
        }


__all__ = ["Product"]
