"""`provider_dialect` — how the framework asks a provider what it speaks.

Framework stores write `?` placeholders and translate them per provider
(notification, tasks, audit, tenancy all carry the same translator). They used
to read `name`, an attribute the contract never declared: a provider that
implemented `DatabaseProviderProtocol` faithfully exposes `database_type`, so
every such provider looked like SQLite and its stores would have sent `?` to a
Postgres driver. The helper is the one place that decides.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.data.sql.database import provider_dialect


class _ContractOnly:
    """A provider that exposes exactly what the protocol declares."""

    database_type = "postgres"


class _Historical:
    """A provider from before `database_type` existed."""

    name = "mysql"


class _Both:
    """Both attributes, disagreeing: the contract's own wins."""

    database_type = "postgres"
    name = "my-pool"


class _Silent:
    """A provider that reports nothing."""


class _Blank:
    """A provider whose attribute is an empty string."""

    database_type = ""


class _NotAString:
    """A provider whose attribute is not even a string."""

    database_type = None
    name = 42


def test_contract_attribute_is_read() -> None:
    assert provider_dialect(_ContractOnly()) == "postgres"


def test_historical_name_is_still_read() -> None:
    assert provider_dialect(_Historical()) == "mysql"


def test_contract_attribute_wins_over_name() -> None:
    """`name` doubles as a DI provider name, so it cannot be authoritative."""
    assert provider_dialect(_Both()) == "postgres"


def test_defaults_to_sqlite_when_nothing_is_reported() -> None:
    assert provider_dialect(_Silent()) == "sqlite"
    assert provider_dialect(_Blank()) == "sqlite"
    assert provider_dialect(_NotAString()) == "sqlite"


def test_accepts_any_object_without_raising() -> None:
    """Stores call it on whatever the container handed them."""
    assert provider_dialect(object()) == "sqlite"
    typed_any: Any = type("_P", (), {"database_type": "sqlite"})()
    assert provider_dialect(typed_any) == "sqlite"
