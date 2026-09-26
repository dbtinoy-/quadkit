"""P2 hook surface import verification for quadkit-sql."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_sql_hooks_root_module_exists() -> None:
    import quadkit.sql
    from quadkit.sql.hooks import (
        SQLConnectionReadyHook,
        SQLTransactionBegunHook,
        SQLTransactionEndedHook,
    )

    assert SQLConnectionReadyHook.__name__ == "SQLConnectionReadyHook"
    assert SQLTransactionBegunHook.__name__ == "SQLTransactionBegunHook"
    assert SQLTransactionEndedHook.__name__ == "SQLTransactionEndedHook"
    assert quadkit.sql.SQLConnectionReadyHook is SQLConnectionReadyHook
    assert quadkit.sql.SQLTransactionBegunHook is SQLTransactionBegunHook
    assert quadkit.sql.SQLTransactionEndedHook is SQLTransactionEndedHook
    assert "SQLConnectionReadyHook" in quadkit.sql.__all__
    assert "SQLTransactionBegunHook" in quadkit.sql.__all__
    assert "SQLTransactionEndedHook" in quadkit.sql.__all__


def test_sql_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.sql.hooks import SQLConnectionReadyHook, SQLTransactionEndedHook

    ready = SQLConnectionReadyHook(backend="postgresql")
    ended = SQLTransactionEndedHook(committed=True)

    assert is_dataclass(ready)
    assert is_dataclass(ended)

    with pytest.raises(TypeError):
        SQLConnectionReadyHook("postgresql")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        ready.backend = "mysql"  # type: ignore[misc]


def test_sql_transaction_begun_hook_has_no_required_fields() -> None:
    from quadkit.sql.hooks import SQLTransactionBegunHook

    hook = SQLTransactionBegunHook()
    assert is_dataclass(hook)
