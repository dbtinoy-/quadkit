"""Tests for database module."""

import pytest
from quadkit.sql import DatabaseModule
from quadkit.di.module import DynamicModule


class TestDatabaseModule:
    def test_database_module_exists(self) -> None:
        assert DatabaseModule is not None

    def test_configure_returns_dynamic_module(self) -> None:
        result = DatabaseModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is DatabaseModule
