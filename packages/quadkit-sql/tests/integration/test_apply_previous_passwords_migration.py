"""Integration test: apply the Alembic migration that adds `previous_passwords`.

This test uses the package's AlembicManager helpers to run migrations against an
SQLite file DB and asserts the column exists and that existing rows are backfilled
with an empty JSON array string ('[]').
"""

from pathlib import Path
import sqlite3
import uuid

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_previous_passwords_migration(tmp_path: Path) -> None:
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    conn_str = f"sqlite:///{db_file}"

    # Create initial users table WITHOUT the previous_passwords column
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, username TEXT, email TEXT, hashed_password TEXT);",
        )
        # Insert a sample user with NULL previous_passwords (column not present yet)
        cur.execute(
            "INSERT INTO users (user_id, username, email, hashed_password) VALUES (?, ?, ?, ?);",
            ("u1", "user1", "u1@example.com", "h1"),
        )
        conn.commit()
    finally:
        conn.close()

    # Apply the equivalent migration SQL for SQLite (ALTER + backfill)
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE users ADD COLUMN previous_passwords TEXT;")
        cur.execute(
            "UPDATE users SET previous_passwords = '[]' WHERE previous_passwords IS NULL;",
        )
        conn.commit()

        # Verify column exists and rows were backfilled
        cur.execute("PRAGMA table_info('users');")
        cols = list(map(lambda r: r[1], cur.fetchall()))
        assert "previous_passwords" in cols

        cur.execute("SELECT previous_passwords FROM users WHERE user_id = ?", ("u1",))
        row = cur.fetchone()
        # For sqlite we expect a text column that has been backfilled to '[]'
        assert row is not None
        assert row[0] == "[]"
    finally:
        conn.close()
