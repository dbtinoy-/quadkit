"""Feature tour: logging discipline as configuration, not code.

`configure_logging` builds a structured pipeline where two worries stop
being application concerns: **redaction** — fields like `password` and
`token` are masked in every event, including nested containers — and
**sampling** — high-frequency noise is dropped deterministically while
named business events always get through. `reset_logging` returns the
process to defaults, which the teardown uses so other tests are untouched.
"""

import json

import pytest

from quadkit.logging import (
    configure_logging,
    get_logger,
    reset_logging,
)


@pytest.fixture(autouse=True)
def _restore_logging_defaults():
    yield
    reset_logging()


def test_redaction_masks_secret_fields_everywhere(capsys) -> None:
    configure_logging(level="INFO", json_format=True, redaction_enabled=True)
    logger = get_logger("billing")

    logger.info(
        "payment.captured",
        order_id="ord-9",
        password="hunter2",
        nested={"profile": {"token": "tok-abc"}},
    )

    out_lines = [
        line for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    event = json.loads(out_lines[-1])
    assert event["event"] == "payment.captured"
    assert event["order_id"] == "ord-9"
    assert event["password"] == "<redacted>"
    assert event["nested"] == {"profile": {"token": "<redacted>"}}


def test_sampling_is_deterministic_and_named_rules_win(capsys) -> None:
    configure_logging(
        level="INFO",
        json_format=True,
        sampling_enabled=True,
        sampling_default_rate=0.0,
        sampling_rules={"order.placed": 1.0},
    )
    logger = get_logger("orders")

    for _ in range(3):
        logger.info("order.placed", order_id="ord-1")
    for _ in range(3):
        logger.info("cache.warmed")

    events = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    raised = [e["event"] for e in events]
    assert raised == ["order.placed"] * 3  # named rule keeps every event
    assert "cache.warmed" not in raised    # default 0.0 drops them all
