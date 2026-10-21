"""An unstamped database reports every revision as pending.

Regression: ``SchemaIntrospector.get_status`` only computed pending revisions
when the database already carried an ``alembic_version`` row, so a database
that had never been migrated reported **zero pending** migrations. Anything
reading that status — the admin migration-status widget, a deploy gate, an
operator looking at the dashboard — saw "0 pending" for a database with the
entire migration chain outstanding.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from quadkit.sql.migrations.introspector import SchemaIntrospector

_FIRST = '''
"""first"""

revision = "aaa1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''

_SECOND = '''
"""second"""

revision = "bbb2"
down_revision = "aaa1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    """A two-revision alembic script directory (``aaa1`` → ``bbb2``)."""
    root = tmp_path / "migrations"
    versions = root / "versions"
    versions.mkdir(parents=True)
    (root / "env.py").write_text("")
    (root / "script.py.mako").write_text("")
    (versions / "aaa1_first.py").write_text(_FIRST)
    (versions / "bbb2_second.py").write_text(_SECOND)
    return root


def _config(migrations_dir: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("version_locations", str(migrations_dir / "versions"))
    config.set_main_option("path_separator", "os")
    return config


async def test_unstamped_database_reports_every_revision_pending(
    migrations_dir: Path, tmp_path: Path
) -> None:
    """No ``alembic_version`` row means the whole chain is outstanding."""
    db_path = tmp_path / "unstamped.db"
    sqlite3.connect(db_path).close()

    introspector = SchemaIntrospector(_config(migrations_dir), f"sqlite:///{db_path}")
    status = await introspector.get_status()

    assert status.current_revision is None
    assert status.is_up_to_date is False
    assert {info.revision for info in status.pending_migrations} == {"aaa1", "bbb2"}


async def test_stamped_database_reports_no_pending_migrations(
    migrations_dir: Path, tmp_path: Path
) -> None:
    """A database stamped at head is up to date."""
    db_path = tmp_path / "stamped.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    connection.execute("INSERT INTO alembic_version VALUES ('bbb2')")
    connection.commit()
    connection.close()

    introspector = SchemaIntrospector(_config(migrations_dir), f"sqlite:///{db_path}")
    status = await introspector.get_status()

    assert status.current_revision == "bbb2"
    assert status.is_up_to_date is True
    assert status.pending_migrations == []


async def test_partially_migrated_database_reports_the_remainder(
    migrations_dir: Path, tmp_path: Path
) -> None:
    """A database stamped behind head reports only the missing revisions."""
    db_path = tmp_path / "partial.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    connection.execute("INSERT INTO alembic_version VALUES ('aaa1')")
    connection.commit()
    connection.close()

    introspector = SchemaIntrospector(_config(migrations_dir), f"sqlite:///{db_path}")
    status = await introspector.get_status()

    assert status.current_revision == "aaa1"
    assert [info.revision for info in status.pending_migrations] == ["bbb2"]
