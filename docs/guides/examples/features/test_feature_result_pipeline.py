"""Feature tour: Result pipelines — composition without try/except.

`pipeline(value)` starts a fluent chain from an infallible value, and
`ResultPipeline(result)` lifts a service's `Result` into the same
machinery. `then` chains steps that can fail (short-circuiting on the
first `Err`), `map` applies infallible transforms, `recover` swaps a
failure for a fallback plan, and `finalize` hands back the typed
`Result[T, E]`. The error type is carried through the whole chain, so
the type checker can audit every step.
"""

import pytest

from quadkit import DomainError, Err, Ok, Result, ResultPipeline
from quadkit.result import pipeline

Stock = dict[str, int]
NOT_FOUND = DomainError("not_found")
EMPTY = DomainError("empty")


def check_stock(sku: str) -> Result[str, DomainError]:
    return Ok(sku) if sku in {"mug", "book"} else Err(NOT_FOUND)


def require_nonempty(cart: list[str]) -> Result[list[str], DomainError]:
    return Ok(cart) if cart else Err(EMPTY)


def test_pipeline_chains_until_the_first_failure() -> None:
    steps: list[str] = []

    def seen(label: str):
        def _step(value: str) -> Result[str, DomainError]:
            steps.append(label)
            return Ok(f"{value}>{label}")

        return _step

    happy = (
        pipeline("start")
        .then(seen("first"))
        .then(seen("second"))
        .map(str.upper)
        .finalize()
    )
    assert happy == Ok("START>FIRST>SECOND")
    assert steps == ["first", "second"]

    steps.clear()
    stopped = (
        pipeline("start")
        .then(seen("first"))
        .then(lambda _: Err(EMPTY))
        .then(seen("unreachable"))
        .map(str.upper)
        .finalize()
    )
    assert stopped == Err(EMPTY)
    assert steps == ["first"]  # everything after the failure was skipped


def test_recover_swaps_failure_for_a_fallback_plan() -> None:
    order = (
        ResultPipeline(check_stock("kettle"))  # lift a fallible service result
        .then(lambda sku: Ok({"sku": sku, "price": 1200}))
        .recover(lambda _err: Ok({"sku": "mug", "price": 700, "substituted": True}))
        .finalize()
    )
    assert order == Ok({"sku": "mug", "price": 700, "substituted": True})

    in_stock = (
        ResultPipeline(check_stock("book"))
        .then(lambda sku: Ok({"sku": sku, "price": 2500}))
        .recover(lambda _err: Ok({"substituted": True}))
        .finalize()
    )
    assert in_stock == Ok({"sku": "book", "price": 2500})  # no substitution


def test_recover_only_fires_on_failure_and_can_refuse() -> None:
    kept = (
        ResultPipeline(require_nonempty(["mug"]))
        .recover(lambda _err: Ok(["fallback"]))
        .finalize()
    )
    assert kept == Ok(["mug"])

    refused = (
        ResultPipeline(require_nonempty([]))
        .map(lambda cart: cart + ["extra"])
        .recover(lambda err: Err(err))  # recovery may decline
        .finalize()
    )
    assert refused == Err(EMPTY)
