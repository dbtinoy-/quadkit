"""Tests for CLI module."""

import pytest
from quadkit.cli import CLIModule
from quadkit.di.module import DynamicModule


class TestCLIModule:
    def test_cli_module_exists(self) -> None:
        assert CLIModule is not None

    def test_configure_returns_dynamic_module(self) -> None:
        result = CLIModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is CLIModule
