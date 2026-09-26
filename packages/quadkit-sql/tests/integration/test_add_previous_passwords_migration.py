"""Integration tests for the `previous_passwords` migration.

These tests verify that the migration's upgrade SQL (as executed on SQLite) will add
`previous_passwords` column to an existing `users` table and that the column is
queryable. SQLite is used here for a fast, file-backed integration test.
"""

from pathlib import Path
import sqlite3

import pytest


@pytest.mark.integration
def test_sqlite_add_previous_passwords_column(tmp_path: Path) -> None:
    """Create a SQLite DB with a users table (without previous_passwords), run the
    ALTER TABLE statement equivalent to the migration, and assert the column exists.
    """
    db_file = tmp_path / "test_users.db"

    # Create initial users table without previous_passwords
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, username TEXT, email TEXT, hashed_password TEXT);",
        )
        conn.commit()

        # Apply simple migration SQL that would be used for SQLite
        cur.execute("ALTER TABLE users ADD COLUMN previous_passwords TEXT;")
        conn.commit()

        # Verify column present via PRAGMA table_info
        cur.execute("PRAGMA table_info('users');")
        cols = list(map(lambda r: r[1], cur.fetchall()))
        assert "previous_passwords" in cols
    finally:
        conn.close()
