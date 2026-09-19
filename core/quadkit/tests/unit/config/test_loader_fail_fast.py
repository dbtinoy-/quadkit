"""Tests that ConfigLoader fails fast on malformed config content.

A broken config file must NOT be silently skipped: booting an app on
partial defaults because ``application.json`` had a syntax error (or
PyYAML was missing) is far worse than an explicit startup failure.

Genuinely optional sources (custom sources raising ``OSError``) may
still be skipped with a log — that behaviour is asserted too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quadkit.config.lib import ConfigLoader
from quadkit.config.lib.sources import ConfigSource, FileConfigSource
from quadkit.contracts.exceptions import ConfigurationError


class _OSErrorSource(ConfigSource):
    """A source that fails like a transiently unavailable optional source."""

    pre_interpolated = True

    def load_sync(self) -> dict:
        raise OSError("source temporarily unreachable")

    def get_name(self) -> str:
        return "optional-oserror"


class TestLoaderFailFast:
    """Malformed config content is a hard error."""

    def test_broken_json_is_fatal(self, tmp_path: Path):
        broken = tmp_path / "config.json"
        broken.write_text("{not valid json!!", encoding="utf-8")

        loader = ConfigLoader()
        loader.add_source(FileConfigSource(broken))
        with pytest.raises((json.JSONDecodeError, ConfigurationError)):
            loader.load_sync(dict)

    async def test_broken_json_is_fatal_async(self, tmp_path: Path):
        broken = tmp_path / "config.json"
        broken.write_text("{not valid json!!", encoding="utf-8")

        loader = ConfigLoader()
        loader.add_source(FileConfigSource(broken))
        with pytest.raises((json.JSONDecodeError, ConfigurationError)):
            await loader.load(dict)

    def test_configuration_error_is_fatal(self, tmp_path: Path):
        class _FailingSource(ConfigSource):
            pre_interpolated = True

            def load_sync(self) -> dict:
                raise ConfigurationError("simulated hard failure")

            def get_name(self) -> str:
                return "failing"

        loader = ConfigLoader()
        loader.add_source(_FailingSource())
        with pytest.raises(ConfigurationError, match="simulated hard failure"):
            loader.load_sync(dict)

    def test_omittable_oserror_source_still_skipped(self):
        """Optional sources raising OSError are skipped, not fatal."""

        class _GoodSource(ConfigSource):
            pre_interpolated = True

            def load_sync(self) -> dict:
                return {"ok": 1}

            def get_name(self) -> str:
                return "good"

        loader = ConfigLoader()
        loader.add_source(_OSErrorSource())
        loader.add_source(_GoodSource())
        merged = loader._collect_sync(None)
        assert merged == {"ok": 1}
