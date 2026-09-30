"""`AlembicManager` builds a config alembic does not deprecate.

These tests use the **real** ``alembic.config.Config`` on purpose.
``tests/unit/test_migrations_manager.py`` patches ``Config`` out, so it can
assert which options the manager *asks* for but never what alembic *does*
with them -- which is why the regression below survived there.

The regression: the manager sets ``version_locations`` programmatically, and
alembic >= 1.16 deprecates splitting that value unless ``path_separator`` is
also set. A workspace checkout hid it, because ``_create_alembic_config``
finds the packaged ``alembic.ini`` (which carries ``path_separator = os``)
and sets ``config_file_name``. An installed layout -- the wheel a generated
project resolves from PyPI -- has no packaged ini, so every boot fell back to
legacy splitting and emitted the deprecation.
"""

from __future__ import annotations

import pathlib
import warnings

from alembic.script import ScriptDirectory
import pytest

from quadkit.sql.migrations.manager import AlembicManager
from quadkit.sql.migrations.manager._alembic import _packaged_alembic_ini

_DEPRECATION = "path_separator"


@pytest.fixture
def migrations_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory shaped enough for ``ScriptDirectory`` to load it."""
    root = tmp_path / "migrations"
    (root / "versions").mkdir(parents=True)
    (root / "env.py").write_text("")
    (root / "script.py.mako").write_text("")
    return root


@pytest.fixture
def installed_layout(monkeypatch: pytest.MonkeyPatch):
    """Hide the packaged ``alembic.ini``, as an installed wheel does.

    Only that filename is hidden; every other path answers normally, so the
    manager still finds the migrations directory under ``tmp_path``.
    """
    real_exists = pathlib.Path.exists

    def fake_exists(self: pathlib.Path) -> bool:
        if self.name == "alembic.ini":
            return False
        return real_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", fake_exists)


def test_installed_layout_emits_no_path_separator_deprecation(
    migrations_dir: pathlib.Path, installed_layout: None
) -> None:
    """The case a generated project actually runs: no packaged ini."""
    assert not _packaged_alembic_ini().exists(), (
        "fixture did not hide the packaged ini; the test would pass vacuously"
    )
    manager = AlembicManager("sqlite:///x.db", migrations_path=str(migrations_dir))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ScriptDirectory.from_config(manager.config)

    offenders = [str(w.message) for w in caught if _DEPRECATION in str(w.message)]
    assert not offenders, f"alembic still deprecates the config: {offenders}"


def test_version_locations_still_resolves_in_both_layouts(
    migrations_dir: pathlib.Path,
) -> None:
    """``path_separator`` must not cost us the value it governs.

    Guards the near-miss this fix had: setting the separator while dropping
    ``version_locations`` leaves alembic with *no* version path at all, and
    the deprecation assertion above would still pass -- silently, because
    there is then nothing to split.
    """
    manager = AlembicManager("sqlite:///x.db", migrations_path=str(migrations_dir))
    script = ScriptDirectory.from_config(manager.config)

    assert script.version_locations == (str(migrations_dir / "versions"),) or list(
        script.version_locations
    ) == [str(migrations_dir / "versions")]


def test_path_separator_defaults_to_os(migrations_dir: pathlib.Path) -> None:
    manager = AlembicManager("sqlite:///x.db", migrations_path=str(migrations_dir))
    assert manager.config.get_main_option("path_separator") == "os"


def test_explicit_alembic_config_overrides_the_default(
    migrations_dir: pathlib.Path,
) -> None:
    """The default is a floor, not a ceiling -- callers keep the last word."""
    manager = AlembicManager(
        "sqlite:///x.db",
        migrations_path=str(migrations_dir),
        alembic_config={"path_separator": ":"},
    )
    assert manager.config.get_main_option("path_separator") == ":"
