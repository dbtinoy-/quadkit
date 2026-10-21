"""Dialect reporting for ``DatabaseProviderProtocol`` implementations.

Every framework store that provisions its own tables writes ``?`` placeholders
and translates them per provider (see ``the optional provider module`` and its
siblings in ``quadkit.tasks``/``the optional provider module``/``the optional provider module``). Until now
each store asked the provider for ``name`` — an attribute the contract never
declared — and defaulted to SQLite when it was missing. A provider that
implemented the contract faithfully, exposing only ``database_type``, therefore
looked like SQLite: on Postgres its stores would have sent ``?`` placeholders
to the driver and failed at run time, not at boot.

The rule now lives here, in the contract, so every store asks the same question
the same way — including the driver-declared dialect (``engine`` /
``connection``) that hand-rolled copies in the packages were consulting
separately.
"""

from __future__ import annotations

from typing import Any

__all__ = ["provider_dialect"]

#: Dialect assumed when a provider reports nothing usable. SQLite is the
#: framework's default provider, and an unknown dialect makes the placeholder
#: translators pass the statement through unchanged — which is what SQLite
#: wants.
_DEFAULT_DIALECT = "sqlite"

#: Attributes consulted, in order. ``database_type`` is the contract's own
#: name for this; ``name`` is the historical attribute the SQL providers still
#: carry (and which also serves as a DI provider name, hence second).
_DIALECT_ATTRIBUTES = ("database_type", "name")

#: Where a driver that reports nothing else keeps its dialect. A provider built
#: on SQLAlchemy exposes ``engine`` (or ``connection``) whose ``dialect.name``
#: is the truth for the connection actually in use, which is why it ranks
#: above the default: an application provider that never declared a dialect
#: still gets placeholder translation right.
_DIALECT_PATHS = (("engine",), ("connection",))


def provider_dialect(provider: Any) -> str:
    """Return the dialect name a provider reports (e.g. ``"postgres"``).

    Args:
        provider: Any ``DatabaseProviderProtocol`` implementation.

    Returns:
        The provider's dialect name, or ``"sqlite"`` when it reports none.
    """
    for attribute in _DIALECT_ATTRIBUTES:
        value = getattr(provider, attribute, None)
        if isinstance(value, str) and value:
            return value

    for path in _DIALECT_PATHS:
        holder: Any = provider
        for attribute in path:
            holder = getattr(holder, attribute, None)
            if holder is None:
                break
        engine = getattr(holder, "sync_engine", holder)
        dialect = getattr(getattr(engine, "dialect", None), "name", None)
        if isinstance(dialect, str) and dialect:
            return dialect

    return _DEFAULT_DIALECT
