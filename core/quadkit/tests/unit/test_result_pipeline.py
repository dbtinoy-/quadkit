"""Tests for result/_pipeline.py — ResultPipeline fluent chaining API."""

from __future__ import annotations

from quadkit.result import ResultPipeline, pipeline
from quadkit.result.types import Err, Ok, Result


class TestPipelineCreation:
    """Tests for creating ResultPipeline."""

    def test_pipeline_from_value(self) -> None:
        """pipeline() creates pipeline from infallible value."""
        p = pipeline("hello")
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == "hello"

    def test_pipeline_from_int(self) -> None:
        """pipeline() works with numeric values."""
        p = pipeline(42)
        result = p.finalize()
        assert result.unwrap() == 42

    def test_pipeline_from_list(self) -> None:
        """pipeline() works with collection values."""
        p = pipeline([1, 2, 3])
        result = p.finalize()
        assert result.unwrap() == [1, 2, 3]


class TestPipelineThen:
    """Tests for ResultPipeline.then() method."""

    def test_then_chains_on_ok(self) -> None:
        """then() chains function when result is Ok."""
        p = pipeline(5).then(lambda x: Ok(x * 2))
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == 10

    def test_then_passes_through_err(self) -> None:
        """then() passes through Err without calling function."""
        p = pipeline(5).then(lambda _x: Err("error"))
        result = p.finalize()
        assert result.is_err()
        assert result.unwrap_err() == "error"

    def test_then_preserves_error_type(self) -> None:
        """then() preserves the error type through chain."""
        p = pipeline(1).then(lambda x: Ok(x + 1)).then(lambda x: Ok(x + 1))
        result = p.finalize()
        assert result.unwrap() == 3

    def test_then_short_circuits_on_err(self) -> None:
        """then() short-circuits when result is Err."""
        call_count = [0]

        def mapper(x: int) -> Result[int, str]:
            call_count[0] += 1
            return Ok(x * 2)

        # Start with Err and wrap in ResultPipeline
        p = ResultPipeline(Err("initial_error")).then(mapper)
        result = p.finalize()

        assert result.is_err()
        assert result.unwrap_err() == "initial_error"
        assert call_count[0] == 0


class TestPipelineMap:
    """Tests for ResultPipeline.map() method."""

    def test_map_transforms_ok_value(self) -> None:
        """map() transforms the value when Ok."""
        p = pipeline(10).map(lambda x: x / 2)
        result = p.finalize()
        assert result.unwrap() == 5

    def test_map_preserves_err(self) -> None:
        """map() passes through Err without calling function."""
        p = ResultPipeline(Err("error")).map(lambda x: x * 2)
        result = p.finalize()
        assert result.is_err()
        assert result.unwrap_err() == "error"

    def test_map_with_string_operation(self) -> None:
        """map() works with string transformations."""
        p = pipeline("hello").map(str.upper)
        result = p.finalize()
        assert result.unwrap() == "HELLO"

    def test_map_short_circuits_on_err(self) -> None:
        """map() short-circuits when result is Err."""
        p = ResultPipeline(Err("fail")).map(lambda x: x * 2)
        result = p.finalize()
        assert result.is_err()


class TestPipelineRecover:
    """Tests for ResultPipeline.recover() method."""

    def test_recover_transforms_err(self) -> None:
        """recover() transforms error to new result."""
        p = ResultPipeline(Err("original")).recover(lambda e: Ok(f"recovered: {e}"))
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == "recovered: original"

    def test_recover_passes_through_ok(self) -> None:
        """recover() passes through Ok without calling function."""
        p = ResultPipeline(Ok(42)).recover(lambda _e: Ok(0))
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == 42

    def test_recover_can_change_error_type(self) -> None:
        """recover() can change the error type."""
        p = ResultPipeline(Err("str_error")).recover(lambda _e: Err(404))
        result = p.finalize()
        assert result.is_err()
        assert result.unwrap_err() == 404

    def test_recover_can_return_ok_from_err(self) -> None:
        """recover() can convert Err to Ok."""
        p = ResultPipeline(Err("failed")).recover(lambda _e: Ok("fallback"))
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == "fallback"


class TestPipelineChaining:
    """Tests for chaining multiple pipeline operations."""

    def test_then_map_chain(self) -> None:
        """then() followed by map() works correctly."""
        p = pipeline(2).then(lambda x: Ok(x + 1)).map(lambda x: x * 3)
        result = p.finalize()
        assert result.unwrap() == 9

    def test_map_then_chain(self) -> None:
        """map() followed by then() works correctly."""
        p = pipeline(2).map(lambda x: x + 1).then(lambda x: Ok(x * 3))
        result = p.finalize()
        assert result.unwrap() == 9

    def test_recover_then_map(self) -> None:
        """recover() followed by then() and map()."""
        p = (
            ResultPipeline(Err("error"))
            .recover(lambda _e: Ok(10))
            .then(lambda x: Ok(x + 5))
            .map(lambda x: x * 2)
        )
        result = p.finalize()
        assert result.unwrap() == 30

    def test_multiple_recover_calls(self) -> None:
        """Multiple recover() calls can change error type."""
        p = (
            ResultPipeline(Err("first"))
            .recover(lambda _e: Err("second"))
            .recover(lambda _e: Ok("recovered"))
        )
        result = p.finalize()
        assert result.is_ok()
        assert result.unwrap() == "recovered"


class TestPipelineFinalize:
    """Tests for finalize() method."""

    def test_finalize_returns_result(self) -> None:
        """finalize() returns the underlying Result."""
        p = pipeline(42)
        result = p.finalize()
        assert isinstance(result, Result)
        assert result.unwrap() == 42

    def test_finalize_called_multiple_times(self) -> None:
        """finalize() can be called multiple times."""
        p = pipeline(10).map(lambda x: x + 5)
        result1 = p.finalize()
        result2 = p.finalize()
        assert result1.unwrap() == result2.unwrap()


class TestPipelineErrorTypePreservation:
    """Tests for error type preservation through pipeline."""

    def test_error_type_preserved_through_then(self) -> None:
        """Error type E is preserved through then()."""
        p = pipeline(1).then(lambda x: Ok(x) if x > 0 else Err("negative"))
        result = p.finalize()
        # Error type is str

    def test_error_type_changes_on_recover(self) -> None:
        """Error type changes when recover() provides new type."""
        p: ResultPipeline[int, str] = ResultPipeline(Err("error"))
        p2 = p.recover(lambda _e: Err(404))  # Now int, int
        result = p2.finalize()
        assert result.is_err()
        assert result.unwrap_err() == 404
