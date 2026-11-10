"""Seeded offline fixtures for the support desk tools.

These are plain data structures — no framework imports, no I/O.
They represent the "database" that the three tools query:

- ``ORDERS`` — three sample orders in various states
- ``KB``     — six FAQ snippets covering refunds, shipping, tracking, etc.

In a real application these would come from a database or external API.
For the demo, hardcoded dicts keep the focus on agent behavior rather
than data access.
"""

from __future__ import annotations

ORDERS: dict[str, dict] = {
    "A-100": {
        "status": "shipped",
        "items": ["Desk Lamp", "USB-C Cable"],
        "total": 59.98,
        "carrier": "FastShip",
        "tracking": "FS123456789",
    },
    "A-101": {
        "status": "processing",
        "items": ["Mechanical Keyboard"],
        "total": 129.00,
        "carrier": None,
        "tracking": None,
    },
    "A-102": {
        "status": "delivered",
        "items": ["Monitor Arm"],
        "total": 74.50,
        "carrier": "FastShip",
        "tracking": "FS987654321",
    },
}

KB: list[dict[str, str]] = [
    {
        "title": "Refunds",
        "snippet": "Full refund within 7 days of delivery. Half refund within 30 days.",
    },
    {
        "title": "Shipping",
        "snippet": "Standard shipping takes 3-5 business days with FastShip carrier.",
    },
    {
        "title": "Tracking",
        "snippet": "Track your parcel using the tracking id in your shipment email.",
    },
    {
        "title": "Returns",
        "snippet": "Start a return from your account page before requesting a refund.",
    },
    {
        "title": "Warranty",
        "snippet": "All products include a 24 month limited warranty.",
    },
    {
        "title": "Payments",
        "snippet": "We accept major cards and wallet payments; cards are charged at dispatch.",
    },
]
