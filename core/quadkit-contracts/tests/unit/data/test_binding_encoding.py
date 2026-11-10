"""Bind-value encoding: what a provider is allowed to hand a driver.

The two rules here are the ones a raw-SQL path cannot get right on its own,
because a text statement carries no column type to normalise through: JSON
payloads have to become text, and an aware datetime has to become the naive UTC
value the framework stores.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from quadkit.contracts.data.sql.database._binding import encode_bind_value, encode_bind_values


class TestBindValueEncoding:
    def test_dict_becomes_compact_json(self) -> None:
        assert encode_bind_value({"order_id": "7", "n": 1}) == '{"order_id":"7","n":1}'

    def test_list_becomes_json(self) -> None:
        assert encode_bind_value([1, 2]) == "[1,2]"

    def test_nested_payload_encodes_once(self) -> None:
        encoded = encode_bind_value({"tags": ["a"]})
        assert encoded == '{"tags":["a"]}'

    def test_scalars_pass_through(self) -> None:
        for value in (None, 0, 1.5, True, "text"):
            assert encode_bind_value(value) is value

    def test_naive_datetime_is_unchanged(self) -> None:
        value = datetime(2026, 1, 1, 9, 30, 15, 123456)
        assert encode_bind_value(value) is value

    def test_aware_datetime_normalises_to_naive_utc(self) -> None:
        """An aware value binds as the naive UTC the ORM mapping would store."""
        value = datetime(2026, 1, 1, 9, 30, 15, 123456, tzinfo=UTC)
        bound = encode_bind_value(value)
        assert bound == datetime(2026, 1, 1, 9, 30, 15, 123456)
        assert bound.tzinfo is None

    def test_non_utc_offset_is_converted_not_relabelled(self) -> None:
        tokyo = timezone(timedelta(hours=9))
        value = datetime(2026, 1, 1, 18, 30, tzinfo=tokyo)
        assert encode_bind_value(value) == datetime(2026, 1, 1, 9, 30)

    def test_list_helper_encodes_every_element(self) -> None:
        values = encode_bind_values([{"a": 1}, datetime(2026, 1, 1, tzinfo=UTC), "plain"])
        assert values == ['{"a":1}', datetime(2026, 1, 1), "plain"]

    def test_list_helper_handles_none(self) -> None:
        assert encode_bind_values(None) == []
