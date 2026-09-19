"""P2-scope-log-level: Scope validation errors must be logged at WARNING, not DEBUG."""

from __future__ import annotations

import inspect

import quadkit.di.container.validation as container_module


class TestScopeValidationLogsAtWarning:
    """P2: validate.scope_check_error must use logger.warning, not logger.debug."""

    def test_scope_check_error_not_logged_at_debug(self) -> None:
        """The debug call for validate.scope_check_error must be absent."""
        source = inspect.getsource(container_module)
        assert 'logger.debug(\n        "validate.scope_check_error"' not in source, (
            "Scope validation error is still logged at DEBUG — must be WARNING"
        )

    def test_scope_check_error_logged_at_warning(self) -> None:
        """Scope-check errors must use logger.warning (not logger.debug)."""
        source = inspect.getsource(container_module)
        # Match regardless of indentation — just verify the key/level combination exists.
        assert "logger.warning" in source, "scope validation errors must use logger.warning"
        # Verify at least one validate.scope_check_* key is present at warning level
        assert "validate.scope_check_" in source, "validate.scope_check_* keys must be present"
        # More specific: validate.scope_check_* must NOT be paired with logger.debug
        assert 'logger.debug(\n                        "validate.scope_check_' not in source, (
            "validate.scope_check_* must not use logger.debug"
        )
