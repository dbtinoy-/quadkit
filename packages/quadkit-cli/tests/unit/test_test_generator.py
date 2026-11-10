"""Tests for the generated unit-test scaffold's controller contract."""

from __future__ import annotations

from pathlib import Path

from quadkit.cli.generators.test import TestGenerator as ScaffoldTestGenerator


def test_controller_scaffold_mocks_repository_results(tmp_path: Path) -> None:
    """Generated controller tests speak the same Result contract as handlers."""
    result = ScaffoldTestGenerator(output_dir=tmp_path).generate(
        "Message", test_type="controller", force=True
    )
    path = Path(result.files_created[0])
    content = path.read_text(encoding="utf-8")

    compile(content, str(path), "exec")
    assert "from quadkit.contracts.exceptions import NotFoundError" in content
    assert "from quadkit.result import Err, Ok" in content
    assert "repo.list = AsyncMock(return_value=Ok([]))" in content
    assert 'repo.create = AsyncMock(return_value=Ok({"id": "1"}))' in content
    assert "repo.delete = AsyncMock(return_value=Ok(True))" in content
    assert "return_value=Err(NotFoundError(" in content
    assert "result.is_ok()" in content
    assert "result.is_err()" in content
    assert "result.unwrap_err()" in content
    assert "repo.get = AsyncMock(return_value=None)" not in content
    assert "repo.delete = AsyncMock(return_value=False)" not in content
    assert "pytest.raises(NotFoundError)" not in content
