"""Result type: Ok/Err variant behaviour across the full API surface."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.result import Err, Ok, Result, UnwrapError


class TestOk:
    def test_identity_and_variants(self) -> None:
        r = Ok(5)
        assert r.is_ok()
        assert not r.is_err()
        assert r.unwrap() == 5
        with pytest.raises(UnwrapError, match="unwrap_err on Ok"):
            r.unwrap_err()
        assert r.unwrap_or(9) == 5
        assert r.unwrap_or_else(lambda _e: 9) == 5
        assert r.expect("nope") == 5

    def test_map_and_chain(self) -> None:
        assert Ok(2).map_sync(lambda v: v * 10) == Ok(20)
        assert Ok(2).map_err(lambda e: e).unwrap() == 2
        assert Ok(3).and_then_sync(lambda v: Ok(v + 1)) == Ok(4)
        assert Ok(3).or_else_sync(lambda _e: Err(3)).unwrap() == 3

    async def test_async_map_and_chain(self) -> None:
        async def triple(v: int) -> int:
            return v * 3

        async def inc(v: int) -> Ok[int, str]:
            return Ok(v + 1)

        async def noop(e: str) -> Err[int, str]:
            return Err(e)

        assert await Ok(2).map(triple) == Ok(6)
        assert await Ok(2).async_map(triple) == Ok(6)
        assert await Ok(2).and_then(inc) == Ok(3)
        assert (await Ok(2).or_else(noop)).unwrap() == 2

    def test_match_expect_filter(self) -> None:
        assert Ok("a").match(lambda v: "ok:" + v, lambda _e: "err") == "ok:a"
        assert Ok("a").filter(lambda v: v == "a", "no").unwrap() == "a"
        assert Ok("a").filter(lambda v: v == "b", "nope").is_err()

    def test_flatten(self) -> None:
        assert Ok(Ok(1)).flatten().unwrap() == 1
        assert Ok(7).flatten().unwrap() == 7

    def test_ok_or_and_optional(self) -> None:
        assert Ok(1).ok_or(9) == 1
        assert Ok(1).to_optional() == 1

    def test_inspect(self) -> None:
        seen: list[int] = []
        assert Ok(5).inspect(seen.append) == Ok(5)
        assert seen == [5]

    def test_inspect_err_noop_on_ok(self) -> None:
        seen: list[object] = []
        Ok(5).inspect_err(seen.append)
        assert seen == []

    def test_equality_hash_repr(self) -> None:
        assert Ok(1) == Ok(1)
        assert Ok(1) != Ok(2)
        assert Ok(1) != Err(1)
        assert hash(Ok(1)) == hash(Ok(1))
        assert repr(Ok(1)) == "Ok(1)"

    def test_from_exception(self) -> None:
        exc = ValueError("boom")
        r = Result.from_exception(exc)
        assert r.is_err()
        assert r.unwrap_err() is exc


class TestErr:
    def test_identity_and_variants(self) -> None:
        r = Err("bad")
        assert r.is_err()
        assert not r.is_ok()
        assert r.unwrap_err() == "bad"
        with pytest.raises(UnwrapError, match="unwrap on Err") as ei:
            r.unwrap()
        # result is attached for debugging
        assert ei.value.result is r
        assert r.unwrap_or(9) == 9
        assert r.unwrap_or_else(lambda e: "e:" + e) == "e:bad"

    def test_expect_raises(self) -> None:
        with pytest.raises(UnwrapError, match="custom msg"):
            Err("bad").expect("custom msg")

    def test_map_and_chain(self) -> None:
        assert Err("e").map_sync(lambda _v: 1).unwrap_err() == "e"
        assert Err("e").map_err(lambda e: e.upper()).unwrap_err() == "E"
        assert Err("e").and_then_sync(lambda _v: Ok(1)).unwrap_err() == "e"
        assert Err("e").or_else_sync(lambda _e: Ok("fixed")).unwrap() == "fixed"

    async def test_async_map_and_chain(self) -> None:
        async def ident(v: str) -> str:
            return v

        async def to_ok(v: str) -> Ok[str, str]:
            return Ok(v)

        async def fix(e: str) -> Ok[str, str]:
            return Ok(e.upper())

        assert (await Err("e").map(ident)).unwrap_err() == "e"
        assert (await Err("e").async_map(ident)).unwrap_err() == "e"
        assert (await Err("e").and_then(to_ok)).unwrap_err() == "e"
        assert (await Err("e").or_else(fix)).unwrap() == "E"

    def test_match_filter_flatten(self) -> None:
        assert Err("e").match(lambda _v: "ok", lambda e: "err:" + e) == "err:e"
        assert Err("e").filter(lambda v: v == "nope", "x").unwrap_err() == "e"
        assert Err("nested").flatten().unwrap_err() == "nested"

    def test_ok_or_and_optional(self) -> None:
        assert Err("e").ok_or(9) == 9
        assert Err("e").to_optional() is None

    def test_inspect_err(self) -> None:
        seen: list[str] = []
        assert Err("e").inspect_err(seen.append) == Err("e")
        assert seen == ["e"]

    def test_inspect_noop_on_err(self) -> None:
        seen: list[object] = []
        Err("e").inspect(seen.append)
        assert seen == []

    def test_equality_hash_repr(self) -> None:
        assert Err(1) == Err(1)
        assert Err(1) != Err(2)
        assert Err(1) != Ok(1)
        assert repr(Err("x")) == "Err('x')"


class TestUnwrapError:
    def test_attributes(self) -> None:
        r = Err("e")
        err = UnwrapError("msg", result=r)
        assert err.result is r
        assert UnwrapError._code == "QK_ERR_RESULT_002"
        assert str(err) == "msg"
