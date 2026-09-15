"""Unit tests for BaseConfig.from_yaml() profile overlay feature.

Verifies that when ``QK_PROFILE`` is set, values from
``application.<profile>.yaml`` are merged on top of the base YAML values.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from quadkit.config.base import BaseConfig

# ---------------------------------------------------------------------------
# Shared config model
# ---------------------------------------------------------------------------


@dataclass(init=False)
class _AppConfig(BaseConfig):
    """Minimal config model used across all profile overlay tests."""

    app_name: str = "default"
    debug: bool = False
    log_level: str = "info"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_yaml(tmp_path: Path) -> Path:
    """Write a base ``application.yaml`` and return its path."""
    path = tmp_path / "application.yaml"
    path.write_text(
        "app_name: base_app\ndebug: false\nlog_level: warning\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfileOverlay:
    def test_no_profile_loads_base_yaml_only(
        self,
        base_yaml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With no QK_PROFILE set, only the base YAML is loaded."""
        monkeypatch.delenv("QK_PROFILE", raising=False)

        config = _AppConfig.from_yaml(base_yaml, env_override=False)

        assert config.app_name == "base_app"
        assert config.debug is False
        assert config.log_level == "warning"

    def test_profile_overlay_merges_values_over_base(
        self,
        base_yaml: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With QK_PROFILE=test, ``application.test.yaml`` overlays the base."""
        profile_yaml = tmp_path / "application.test.yaml"
        profile_yaml.write_text(
            "app_name: test_app\ndebug: true\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("QK_PROFILE", "test")

        config = _AppConfig.from_yaml(base_yaml, env_override=False)

        # profile overrides these two
        assert config.app_name == "test_app"
        assert config.debug is True
        # log_level is only in base — must survive overlay
        assert config.log_level == "warning"

    def test_profile_overlay_missing_file_falls_back_to_base(
        self,
        base_yaml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the profile YAML does not exist, the base config is used as-is."""
        monkeypatch.setenv("QK_PROFILE", "nonexistent_profile_xyz")

        config = _AppConfig.from_yaml(base_yaml, env_override=False)

        # No crash — values come from base only
        assert config.app_name == "base_app"
        assert config.debug is False

    def test_profile_overlay_partial_keys_preserve_base_values(
        self,
        base_yaml: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Profile YAML with partial keys must not wipe unrelated base keys."""
        profile_yaml = tmp_path / "application.staging.yaml"
        # Only override log_level; leave app_name and debug from base
        profile_yaml.write_text("log_level: debug\n", encoding="utf-8")
        monkeypatch.setenv("QK_PROFILE", "staging")

        config = _AppConfig.from_yaml(base_yaml, env_override=False)

        assert config.log_level == "debug"  # overridden by profile
        assert config.app_name == "base_app"  # preserved from base
        assert config.debug is False  # preserved from base

    def test_no_base_yaml_with_profile_still_loads_profile(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When no base YAML exists, values come from the profile file alone."""
        # No application.yaml written intentionally
        profile_yaml = tmp_path / "application.ci.yaml"
        profile_yaml.write_text("app_name: ci_app\ndebug: true\n", encoding="utf-8")
        monkeypatch.setenv("QK_PROFILE", "ci")

        # Point to the nonexistent base path in tmp_path
        base_path = tmp_path / "application.yaml"
        config = _AppConfig.from_yaml(base_path, env_override=False)

        assert config.app_name == "ci_app"
        assert config.debug is True
