"""Real persistence regression for generated services before entity refactoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quadkit.sql.cli.generators import ServiceGenerator
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.asyncio
async def test_generated_service_partial_update_preserves_omitted_fields(
    tmp_path: Path,
) -> None:
    """The UoW row object represents a patch, not a full default-filled model."""
    ServiceGenerator(output_dir=tmp_path).generate(
        "note", fields_str="title:str,body:str,secret:str!writeonly"
    )
    namespace: dict[str, Any] = {}
    source = (tmp_path / "note_service.py").read_text(encoding="utf-8")
    exec(compile(source, "note_service.py", "exec"), namespace)  # noqa: S102

    provider = SQLiteProvider(str(tmp_path / "service.sqlite"))
    await provider.connect()
    try:
        schema = await provider.execute_query(
            "CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "body TEXT NOT NULL, secret TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        assert schema.success
        service = namespace["NoteService"](provider)
        created = await service.create(
            {"title": "Before", "body": "Keep", "secret": "hidden"}
        )
        assert created.is_ok()
        row = created.unwrap()
        assert "secret" not in row
        item_id = row["id"]

        changed = await service.update(item_id, {"title": "After"})
        assert changed.is_ok()
        read = await service.get(item_id)
        assert read.is_ok()
        assert read.unwrap()["title"] == "After"
        assert read.unwrap()["body"] == "Keep"
        assert "secret" not in read.unwrap()
        raw = await provider.execute_query(
            "SELECT secret FROM notes WHERE id = ?", [item_id]
        )
        assert raw.success
        assert raw.rows[0]["secret"] == "hidden"
    finally:
        await provider.disconnect()

    restarted = SQLiteProvider(str(tmp_path / "service.sqlite"))
    await restarted.connect()
    try:
        service = namespace["NoteService"](restarted)
        persisted = await service.get(item_id)
        assert persisted.is_ok()
        assert persisted.unwrap()["body"] == "Keep"
        assert "secret" not in persisted.unwrap()
        assert (await service.delete(item_id)).is_ok()
        assert (await service.get(item_id)).is_err()
    finally:
        await restarted.disconnect()
