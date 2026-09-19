from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from quadkit.di.context import (
    ModuleContextTokens,
    check_visibility,
    clear_module_context,
    get_current_module,
    set_module_context,
    _current_module,
    _module_graph,
)


@pytest.fixture(autouse=True)
def _reset_module_context():
    """Guarantee clean ContextVar state before and after every test."""
    tok_m = _current_module.set(None)
    tok_g = _module_graph.set(None)
    yield
    _current_module.reset(tok_m)
    _module_graph.reset(tok_g)


class TestModuleContext:
    def test_no_context_returns_true(self) -> None:
        """No module context = standalone, no restrictions."""
        assert check_visibility(str) is True

    def test_set_and_get_module(self) -> None:
        class FakeModule:
            pass

        tokens = set_module_context(FakeModule, None)
        try:
            assert get_current_module() is FakeModule
        finally:
            clear_module_context(tokens)

    def test_check_visibility_with_graph(self) -> None:
        class FakeModule:
            pass

        mock_graph = MagicMock()
        mock_graph.is_visible.return_value = True
        tokens = set_module_context(FakeModule, mock_graph)
        try:
            result = check_visibility(str)
            assert result is True
            mock_graph.is_visible.assert_called_once_with(FakeModule, str)
        finally:
            clear_module_context(tokens)

    def test_check_visibility_returns_false(self) -> None:
        class FakeModule:
            pass

        mock_graph = MagicMock()
        mock_graph.is_visible.return_value = False
        tokens = set_module_context(FakeModule, mock_graph)
        try:
            result = check_visibility(str)
            assert result is False
        finally:
            clear_module_context(tokens)

    def test_module_without_graph_returns_true(self) -> None:
        """Module set but graph None = treat as standalone (half-init state)."""

        class FakeModule:
            pass

        tokens = set_module_context(FakeModule, None)
        try:
            assert check_visibility(str) is True
        finally:
            clear_module_context(tokens)

    def test_set_returns_tokens(self) -> None:
        """set_module_context returns ModuleContextTokens."""
        tokens = set_module_context(None, None)
        assert isinstance(tokens, ModuleContextTokens)
        clear_module_context(tokens)
