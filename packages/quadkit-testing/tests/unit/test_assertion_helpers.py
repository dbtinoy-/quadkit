"""Tests for Result assertion helpers in quadkit.testing.lib.assertions.

Covers both the full-name helpers (assert_result_ok, assert_result_err*) and
the short-form aliases (assert_ok, assert_err).
"""

import pytest

from quadkit.result import Err, Ok
from quadkit.testing.lib.assertions import (
    assert_all_ok,
    assert_err,
    assert_ok,
    assert_result_err,
    assert_result_err_contains,
    assert_result_err_type,
    assert_result_maps_to,
    assert_result_ok,
    assert_result_ok_value,
)


class _SomeError(Exception):
    """Sentinel error class for test isolation."""


class _OtherError(Exception):
    """A different error class so we can test type mismatches."""


# ---------------------------------------------------------------------------
# assert_result_ok / assert_ok
# ---------------------------------------------------------------------------


class TestAssertResultOk:
    def test_returns_unwrapped_value_for_ok(self) -> None:
        result = Ok(42)
        value = assert_result_ok(result)
        assert value == 42

    def test_raises_for_err(self) -> None:
        result = Err(_SomeError("boom"))
        with pytest.raises(AssertionError, match="Expected Ok but got Err"):
            assert_result_ok(result)


class TestAssertOkAlias:
    def test_returns_unwrapped_value_for_ok(self) -> None:
        result = Ok("hello")
        value = assert_ok(result)
        assert value == "hello"

    def test_raises_for_err(self) -> None:
        result = Err(_SomeError("oops"))
        with pytest.raises(AssertionError, match="Expected Ok but got Err"):
            assert_ok(result)

    def test_delegates_to_assert_result_ok(self) -> None:
        """assert_ok must behave identically to assert_result_ok."""
        ok_result = Ok(99)
        err_result = Err(_SomeError("e"))
        assert assert_ok(ok_result) == assert_result_ok(ok_result)
        with pytest.raises(AssertionError):
            assert_ok(err_result)


# ---------------------------------------------------------------------------
# assert_result_err / assert_err (no type check)
# ---------------------------------------------------------------------------


class TestAssertResultErr:
    def test_returns_unwrapped_error_for_err(self) -> None:
        error = _SomeError("bad")
        result = Err(error)
        returned = assert_result_err(result)
        assert returned is error

    def test_raises_for_ok(self) -> None:
        result = Ok("value")
        with pytest.raises(AssertionError, match="Expected Err but got Ok"):
            assert_result_err(result)


class TestAssertErrAliasNoTypeCheck:
    def test_returns_errvalue_when_no_type_given(self) -> None:
        error = _SomeError("e")
        result = Err(error)
        returned = assert_err(result)
        assert returned is error

    def test_raises_for_ok(self) -> None:
        result = Ok("x")
        with pytest.raises(AssertionError, match="Expected Err but got Ok"):
            assert_err(result)


# ---------------------------------------------------------------------------
# assert_err with error_type argument
# ---------------------------------------------------------------------------


class TestAssertErrWithTypeCheck:
    def test_passes_when_error_matches_type(self) -> None:
        error = _SomeError("e")
        result = Err(error)
        returned = assert_err(result, _SomeError)
        assert returned is error

    def test_raises_when_error_type_mismatches(self) -> None:
        result = Err(_OtherError("other"))
        with pytest.raises(AssertionError, match="_SomeError"):
            assert_err(result, _SomeError)

    def test_returns_error_only_when_wrong_ok(self) -> None:
        result = Ok("value")
        with pytest.raises(AssertionError, match="Expected Err but got Ok"):
            assert_err(result, _SomeError)


# ---------------------------------------------------------------------------
# assert_result_err_type
# ---------------------------------------------------------------------------


class TestAssertResultErrType:
    def test_passes_for_correct_type(self) -> None:
        result = Err(_SomeError("e"))
        assert_result_err_type(result, _SomeError)  # should not raise

    def test_raises_for_wrong_type(self) -> None:
        result = Err(_OtherError("o"))
        with pytest.raises(AssertionError, match="_SomeError"):
            assert_result_err_type(result, _SomeError)

    def test_raises_for_ok(self) -> None:
        result = Ok("fine")
        with pytest.raises(AssertionError, match="Expected Err"):
            assert_result_err_type(result, _SomeError)


# ---------------------------------------------------------------------------
# assert_result_err_contains
# ---------------------------------------------------------------------------


class TestAssertResultErrContains:
    def test_passes_when_substring_present(self) -> None:
        result = Err(ValueError("user not found"))
        assert_result_err_contains(result, "not found")  # should not raise

    def test_raises_when_substring_absent(self) -> None:
        result = Err(ValueError("other message"))
        with pytest.raises(AssertionError, match="not found"):
            assert_result_err_contains(result, "not found")

    def test_raises_when_ok(self) -> None:
        result = Ok("ok")
        with pytest.raises(AssertionError, match="Expected Err"):
            assert_result_err_contains(result, "anything")


# ---------------------------------------------------------------------------
# assert_result_ok_value
# ---------------------------------------------------------------------------


class TestAssertResultOkValue:
    def test_passes_for_matching_value(self) -> None:
        result = Ok("expected")
        assert_result_ok_value(result, "expected")  # should not raise

    def test_raises_for_wrong_value(self) -> None:
        result = Ok("actual")
        with pytest.raises(AssertionError, match="expected"):
            assert_result_ok_value(result, "expected")

    def test_raises_for_err(self) -> None:
        result = Err(_SomeError("e"))
        with pytest.raises(AssertionError, match="Expected Ok"):
            assert_result_ok_value(result, "value")


# ---------------------------------------------------------------------------
# assert_all_ok
# ---------------------------------------------------------------------------


class TestAssertAllOk:
    def test_returns_all_values_when_all_ok(self) -> None:
        results = [Ok(1), Ok(2), Ok(3)]
        values = assert_all_ok(results)
        assert values == [1, 2, 3]

    def test_raises_on_first_err(self) -> None:
        results = [Ok(1), Err(_SomeError("e")), Ok(3)]
        with pytest.raises(AssertionError, match=r"Result\[1\]"):
            assert_all_ok(results)

    def test_empty_list_returns_empty(self) -> None:
        assert assert_all_ok([]) == []


# ---------------------------------------------------------------------------
# assert_result_maps_to
# ---------------------------------------------------------------------------


class TestAssertResultMapsTo:
    def test_passes_when_mapper_matches(self) -> None:
        result = Ok({"name": "Alice"})
        assert_result_maps_to(result, lambda d: d["name"], "Alice")

    def test_raises_when_mapper_gives_wrong_value(self) -> None:
        result = Ok({"name": "Alice"})
        with pytest.raises(AssertionError, match="Bob"):
            assert_result_maps_to(result, lambda d: d["name"], "Bob")

    def test_raises_for_err_result(self) -> None:
        result = Err(_SomeError("e"))
        with pytest.raises(AssertionError, match="Expected Ok"):
            assert_result_maps_to(result, lambda x: x, "anything")


# ---------------------------------------------------------------------------
# Top-level import convenience
# ---------------------------------------------------------------------------


class TestTopLevelImport:
    """Verify assert_ok / assert_err are importable from quadkit.testing."""

    def test_assert_ok_importable(self) -> None:
        from quadkit.testing import assert_ok as top_assert_ok  # noqa: PLC0415

        assert callable(top_assert_ok)

    def test_assert_err_importable(self) -> None:
        from quadkit.testing import assert_err as top_assert_err  # noqa: PLC0415

        assert callable(top_assert_err)
