"""Bounded counter handlers require CAS and never dispatch invalid arithmetic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from uuid import uuid4

import pytest

from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Err, Ok


def counter(**overrides: object) -> dict[str, object]:
    return {"field": "count", "delta": 1, "minimum": 0, "maximum": 3, **overrides}


def spec(**overrides: object) -> dict[str, object]:
    return {
        "typed_outcomes": True,
        "atomic_transition": True,
        "transition": {"field": "status", "from": "draft", "to": "draft"},
        "counters": [counter()],
        **overrides,
    }


def generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides: object
) -> ModuleType:
    UseCaseGenerator(tmp_path).generate("bump", spec=spec(**overrides))
    name = "counter_" + uuid4().hex
    module_spec = importlib.util.spec_from_file_location(
        name, tmp_path / "bump_use_case.py"
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    monkeypatch.setitem(sys.modules, name, module)
    module_spec.loader.exec_module(module)
    return module


class Repository:
    supports_transition_expected_values_v1 = True

    def __init__(self, row: dict[str, object], *, conflict: bool = False) -> None:
        self.row = row
        self.conflict = conflict
        self.reads = 0
        self.writes: list[tuple[dict[str, object], dict[str, int]]] = []

    async def get_for_transition(self, key: str) -> object:
        self.reads += 1
        return Ok(self.row)

    async def transition_if(
        self,
        key: str,
        field: str,
        expected: str,
        data: dict[str, object],
        *,
        expected_values: dict[str, int] | None = None,
    ) -> object:
        assert expected_values is not None
        self.writes.append((dict(data), dict(expected_values)))
        if self.conflict:
            return Err(ValueError("stale"))
        self.row.update(data)
        return Ok(True)


@pytest.mark.parametrize(
    "item",
    [
        counter(delta=0),
        counter(delta=True),
        counter(delta=1.0),
        counter(delta="1"),
        counter(delta=2**31),
        counter(minimum=None),
        counter(minimum=True),
        counter(minimum=4, maximum=3),
        counter(maximum=2**31),
        counter(minimum=0, maximum=0),
        counter(delta=4),
        counter(field="id"),
        counter(field="updated_at"),
        counter(field="status"),
        counter(field="count + 1"),
        counter(field="__secret"),
        counter(field="class"),
        counter(field="count\npass"),
        counter(field="é"),
        counter(extra="ignored"),
        {"field": "count", "delta": 1},
        "count",
        None,
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_invalid_counter_specs_fail_before_staging(
    tmp_path: Path, item: object, dry_run: bool
) -> None:
    with pytest.raises(ValueError, match="counter"):
        UseCaseGenerator(tmp_path).generate(
            "bump", spec=spec(counters=[item]), dry_run=dry_run
        )
    assert not (tmp_path / "bump_use_case.py").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"atomic_transition": False},
        {"atomic_transition": 1},
        {"transition": None},
        {"transition": {"field": "status", "from": 1, "to": 2}},
        {"counters": "count"},
        {"counters": [counter(), counter()]},
        {"writes": [{"field": "count", "source": "clock"}]},
    ],
)
def test_invalid_context_or_overlapping_writes_fail(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="counter"):
        UseCaseGenerator(tmp_path).generate("bump", spec=spec(**overrides))
    assert not (tmp_path / "bump_use_case.py").exists()


@pytest.mark.parametrize(
    ("old", "delta", "low", "high", "new"),
    [
        (0, 1, 0, 3, 1),
        (3, -1, 0, 3, 2),
        (2**31 - 2, 1, 0, 2**31 - 1, 2**31 - 1),
        (-(2**31) + 1, -1, -(2**31), 0, -(2**31)),
    ],
)
async def test_valid_arithmetic_passes_explicit_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    old: int,
    delta: int,
    low: int,
    high: int,
    new: int,
) -> None:
    module = generate(
        tmp_path,
        monkeypatch,
        counters=[counter(delta=delta, minimum=low, maximum=high)],
        output_fields=[
            {
                "name": "count",
                "type": "int",
                "source": "aggregate.count",
                "required": True,
            }
        ],
    )
    repo = Repository({"status": "draft", "count": old})
    result = await module.BumpHandler(repo).handle(
        module.BumpCommand().for_aggregate(uuid4())
    )
    assert result.success
    assert result.output.count == new
    assert repo.writes == [({"status": "draft", "count": new}, {"count": old})]


@pytest.mark.parametrize("old", [True, 1.0, "1", None, -1, 3, 2**31, float("nan")])
async def test_invalid_snapshot_or_overflow_never_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old: object
) -> None:
    module = generate(tmp_path, monkeypatch)
    row = {"status": "draft", "count": old}
    repo = Repository(row)
    result = await module.BumpHandler(repo).handle(
        module.BumpCommand().for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_counter"
    assert not repo.writes
    assert row["status"] == "draft"
    assert row["count"] is old


@pytest.mark.parametrize("marker", [None, False, 1, "true"])
async def test_legacy_capability_refused_before_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: object
) -> None:
    module = generate(tmp_path, monkeypatch)
    repo = Repository({"status": "draft", "count": 0})
    monkeypatch.setattr(repo, "supports_transition_expected_values_v1", marker)
    result = await module.BumpHandler(repo).handle(
        module.BumpCommand().for_aggregate(uuid4())
    )
    assert result.code == "unsupported_repository"
    assert repo.reads == 0
    assert not repo.writes


async def test_conflict_does_not_retry_or_return_projected_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = generate(
        tmp_path,
        monkeypatch,
        output_fields=[
            {
                "name": "count",
                "type": "int",
                "source": "aggregate.count",
                "required": True,
            }
        ],
    )
    repo = Repository({"status": "draft", "count": 0}, conflict=True)
    result = await module.BumpHandler(repo).handle(
        module.BumpCommand().for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "write_failed"
    assert result.output is None
    assert len(repo.writes) == 1
    assert repo.reads == 1
    assert repo.row == {"status": "draft", "count": 0}


async def test_all_counters_checked_before_any_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = generate(
        tmp_path, monkeypatch, counters=[counter(), counter(field="other")]
    )
    row = {"status": "draft", "count": 0, "other": 3}
    repo = Repository(row)
    result = await module.BumpHandler(repo).handle(
        module.BumpCommand().for_aggregate(uuid4())
    )
    assert result.code == "invalid_counter"
    assert row == {"status": "draft", "count": 0, "other": 3}
    assert not repo.writes
