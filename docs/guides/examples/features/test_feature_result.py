"""Feature tour: the Result pattern.

Errors are values. A function returns `Result[T, E]` — callers compose
with `map_sync`/`and_then_sync`, recover with `or_else_sync`, and branch
with `match`. No `try/except` scaffolding in domain code: `as_result`
lifts raising functions into `Result`, and `collect`/`partition` fold
whole collections. Async chains use the same verbs — `map`, `and_then`
— awaited step by step.
"""

import asyncio

from quadkit import (
    Err,
    Ok,
    Result,
    as_result,
    collect,
    partition,
    try_catch,
)
from quadkit.result import as_result_sync


class InvalidAmountError(Exception):
    pass


def parse_amount(raw: str) -> Result[int, InvalidAmountError]:
    """Validation expressed as values, not exceptions."""
    try:
        amount = int(raw)
    except ValueError:
        return Err(InvalidAmountError(raw))
    if amount <= 0:
        return Err(InvalidAmountError(f"must be positive, got {amount}"))
    return Ok(amount)


def test_sync_chaining_and_recovery() -> None:
    total = (
        parse_amount("21")
        .map_sync(lambda a: a * 2)                        # Ok(21) -> Ok(42)
        .and_then_sync(lambda a: parse_amount(str(a)))    # stays Ok(42)
        .map_err(str)                                     # error -> message
    )
    assert total.unwrap() == 42

    recovered = parse_amount("nope").or_else_sync(lambda _err: Ok(0))
    assert recovered.unwrap() == 0


def test_match_branches_without_exceptions() -> None:
    def describe(result: Result[int, InvalidAmountError]) -> str:
        return result.match(
            lambda amount: f"charged {amount}",
            lambda err: f"declined: {err}",
        )

    assert describe(Ok(25)) == "charged 25"
    assert describe(Err(InvalidAmountError("-3"))) == "declined: -3"


def test_async_chain_composes_step_by_step() -> None:
    async def double(value: int) -> int:
        return value * 2

    async def reparse(value: int) -> Result[int, InvalidAmountError]:
        return parse_amount(str(value))

    async def run() -> None:
        chained = parse_amount("21").map(double)          # ok async op
        assert (await chained).unwrap() == 42
        deep = await parse_amount("21").map(double)
        assert (await deep.and_then(reparse)).unwrap() == 42

    asyncio.run(run())


def test_as_result_lifts_raisers() -> None:
    @as_result(ZeroDivisionError)
    async def ratio(a: int, b: int) -> float:
        return a / b

    @as_result_sync(ValueError)
    def to_int(raw: str) -> int:
        return int(raw)

    async def run() -> None:
        good = await ratio(10, 5)
        bad = await ratio(1, 0)
        assert good.is_ok()
        assert good.unwrap() == 2.0
        assert bad.is_err()
        assert isinstance(bad.unwrap_err(), ZeroDivisionError)

    asyncio.run(run())
    assert to_int("41").map_sync(lambda v: v + 1).unwrap() == 42
    assert to_int("x").is_err()


def test_try_catch_wraps_async_io() -> None:
    async def flaky() -> str:
        raise ConnectionError("dropped")

    async def run() -> None:
        result = await try_catch((ConnectionError,), flaky)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ConnectionError)

    asyncio.run(run())


def test_collect_and_partition() -> None:
    parsed = [parse_amount(x) for x in ("5", "nope", "10", "-1")]

    ok_values, err_values = partition(parsed)
    assert ok_values == [5, 10]
    assert [type(e) for e in err_values] == [InvalidAmountError, InvalidAmountError]

    all_good = collect([parse_amount("1"), parse_amount("2")])
    assert all_good.unwrap() == [1, 2]

    first_bad = collect([parse_amount("1"), parse_amount("bad")])
    assert first_bad.is_err()
