"""Testing utilities and helpers."""

from __future__ import annotations

from quadkit.testing.lib.assertions import (
    TestAssertions,
    assert_all_ok,
    assert_err,
    assert_healthy,
    assert_ok,
    assert_result_err,
    assert_result_err_contains,
    assert_result_err_type,
    assert_result_maps_to,
    assert_result_ok,
    assert_result_ok_value,
)
from quadkit.testing.lib.async_helper import AsyncTestHelper
from quadkit.testing.lib.factory import TestDataFactory
from quadkit.testing.lib.smoke import assert_contracts_resolve

# Module-level convenience instances
test_assertions = TestAssertions()
test_data_factory = TestDataFactory()

__all__ = [
    "AsyncTestHelper",
    "TestAssertions",
    "TestDataFactory",
    "assert_all_ok",
    "assert_contracts_resolve",
    "assert_err",
    "assert_healthy",
    "assert_ok",
    "assert_result_err",
    "assert_result_err_contains",
    "assert_result_err_type",
    "assert_result_maps_to",
    "assert_result_ok",
    "assert_result_ok_value",
    "test_assertions",
    "test_data_factory",
]
