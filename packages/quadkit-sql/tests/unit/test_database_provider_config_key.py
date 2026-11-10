"""Unit tests for configurable config_key on DatabaseProvider and DatabaseModule."""

from __future__ import annotations

from quadkit.sql import DatabaseModule, DatabaseProvider


def test_database_provider_default_and_custom_config_key() -> None:
    default_provider = DatabaseProvider()
    assert default_provider.config_key == "sql"

    custom_provider = DatabaseProvider(config_key="db")
    assert custom_provider.config_key == "db"


def test_database_module_configure_passes_config_key() -> None:
    dyn = DatabaseModule.configure(config_key="db")
    assert len(dyn.providers) == 1
    provider = dyn.providers[0]
    assert isinstance(provider, DatabaseProvider)
    assert provider.config_key == "db"
