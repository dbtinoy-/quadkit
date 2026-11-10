"""Cron validation errors must not echo untrusted expression details."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import quadkit.tasks.scheduling.cron as cron_module
from quadkit.tasks.scheduling.cron import CronExpression


def test_invalid_cron_expression_does_not_echo_private_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = "PRIVATE_CRON_SENTINEL /srv/private/users/42"

    def reject(_expression: str) -> None:
        raise ValueError(private)

    monkeypatch.setattr(cron_module, "HAS_CRONITER", True)
    monkeypatch.setattr(
        cron_module,
        "croniter",
        SimpleNamespace(croniter=reject),
    )

    with pytest.raises(ValueError) as excinfo:
        CronExpression(private)

    assert str(excinfo.value) == "Invalid cron expression"
    assert excinfo.value.__cause__ is None
    assert private not in str(excinfo.value)
