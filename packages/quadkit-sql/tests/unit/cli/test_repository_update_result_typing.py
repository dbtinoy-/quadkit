"""Generated update must widen read outcomes without changing Result variance."""

from pathlib import Path

import pytest

from quadkit.sql.cli.generators.database_repository import DatabaseRepositoryGenerator


@pytest.mark.parametrize("custom_error", [False, True])
def test_update_reboxes_narrow_read_outcome(tmp_path: Path, custom_error: bool) -> None:
    options = (
        {"not_found_error": "OrderNotFoundError", "exceptions_module": "shop.errors"}
        if custom_error
        else {}
    )
    DatabaseRepositoryGenerator(output_dir=tmp_path).generate(
        "Order", fields_str="total:float", **options
    )
    source = (tmp_path / "order_repository.py").read_text()
    update = source.split("    async def update(", 1)[1].split(
        "    async def delete(", 1
    )[0]
    assert "return await self.get(key)" not in update
    assert "result = await self.get(key)" in update
    assert "if result.is_err():\n            return Err(result.unwrap_err())" in update
    assert "return Ok(result.unwrap())" in update
