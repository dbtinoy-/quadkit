"""Unit tests for metric label cardinality validator."""

from quadkit.monitor.metrics.validator import (
    OVERFLOW_LABEL_VALUE,
    CardinalityValidator,
)


def test_validator_collapses_excess_label_values_to_sentinel_bucket() -> None:
    """Excess unique labels are collapsed into a sentinel value."""
    validator = CardinalityValidator(max_cardinality=2)

    labels_1 = validator.validate_labels("requests_total", {"user_id": "u1"})
    labels_2 = validator.validate_labels("requests_total", {"user_id": "u2"})
    labels_3 = validator.validate_labels("requests_total", {"user_id": "u3"})
    labels_4 = validator.validate_labels("requests_total", {"user_id": "u4"})

    assert labels_1["user_id"] == "u1"
    assert labels_2["user_id"] == "u2"
    assert labels_3["user_id"] == OVERFLOW_LABEL_VALUE
    assert labels_4["user_id"] == OVERFLOW_LABEL_VALUE
    assert validator.get_cardinality("requests_total", "user_id") == 3


def test_validator_mutates_input_labels_for_fire_and_forget_usage() -> None:
    """Normalization updates caller labels even when return value is ignored."""
    validator = CardinalityValidator(max_cardinality=1)

    validator.validate_labels("requests_total", {"user_id": "u1"})

    labels = {"user_id": "u2"}
    validator.validate_labels("requests_total", labels)

    assert labels["user_id"] == OVERFLOW_LABEL_VALUE


def test_validator_does_not_collapse_existing_label_values() -> None:
    """Previously tracked labels keep their original values."""
    validator = CardinalityValidator(max_cardinality=1)

    first = validator.validate_labels("jobs_total", {"job": "daily_sync"})
    second = validator.validate_labels("jobs_total", {"job": "hourly_sync"})
    third = validator.validate_labels("jobs_total", {"job": "daily_sync"})

    assert first["job"] == "daily_sync"
    assert second["job"] == OVERFLOW_LABEL_VALUE
    assert third["job"] == "daily_sync"


def test_validator_collapses_excess_label_combinations() -> None:
    """Distinct label combinations beyond cap use sentinel labels."""
    validator = CardinalityValidator(max_cardinality=2)

    labels_1 = validator.validate_labels(
        "http_requests_total",
        {"method": "GET", "status": "200"},
    )
    labels_2 = validator.validate_labels(
        "http_requests_total",
        {"method": "POST", "status": "200"},
    )
    labels_3 = validator.validate_labels(
        "http_requests_total",
        {"method": "GET", "status": "500"},
    )

    assert labels_1 == {"method": "GET", "status": "200"}
    assert labels_2 == {"method": "POST", "status": "200"}
    assert labels_3 == {"method": OVERFLOW_LABEL_VALUE, "status": OVERFLOW_LABEL_VALUE}
