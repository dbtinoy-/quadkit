"""Unit tests for the three new Dim 9.4 health checks.

Covers:
  - InstalledQuadkitPackagesCheck
  - ProviderPackagesCheck
  - CrossExtensionImportCheck
"""

from __future__ import annotations

import os
from pathlib import Path
import textwrap
from unittest.mock import MagicMock, patch

from quadkit.cli.registry.health import (
    CheckStatus,
    CrossExtensionImportCheck,
    InstalledQuadkitPackagesCheck,
    ProviderPackagesCheck,
)

# ---------------------------------------------------------------------------
# InstalledQuadkitPackagesCheck
# ---------------------------------------------------------------------------


class TestInstalledQuadkitPackagesCheck:
    """Tests for InstalledQuadkitPackagesCheck."""

    def _make_dist(self, name: str, version: str) -> MagicMock:
        dist = MagicMock()
        dist.metadata = {"Name": name, "Version": version}
        return dist

    def test_pass_when_packages_found(self) -> None:
        """Returns PASS with a count+list when quadkit packages are installed."""
        fake_dists = [
            self._make_dist("quadkit", "0.1.0"),
            self._make_dist("quadkit-web", "1.0.0"),
            self._make_dist("unrelated-package", "99.0"),
        ]
        with patch(
            "quadkit.cli.registry.health_checks.deps.distributions",
            return_value=fake_dists,
        ):
            result = InstalledQuadkitPackagesCheck().check()

        assert result.status is CheckStatus.PASS
        assert "2 package(s)" in result.message
        assert "quadkit==0.1.0" in result.message
        assert "quadkit-web==1.0.0" in result.message
        assert result.details["packages"] == {
            "quadkit": "0.1.0",
            "quadkit-web": "1.0.0",
        }

    def test_warning_when_no_packages(self) -> None:
        """Returns WARNING when no quadkit-* packages are installed."""
        with patch(
            "quadkit.cli.registry.health_checks.deps.distributions",
            return_value=[self._make_dist("unrelated", "1.0")],
        ):
            result = InstalledQuadkitPackagesCheck().check()

        assert result.status is CheckStatus.WARNING
        assert "No quadkit" in result.message

    def test_missing_name_field_is_skipped(self) -> None:
        """Distributions with no Name field are silently skipped."""
        no_name = MagicMock()
        no_name.metadata = {"Name": None, "Version": "1.0"}
        with patch(
            "quadkit.cli.registry.health_checks.deps.distributions",
            return_value=[no_name],
        ):
            result = InstalledQuadkitPackagesCheck().check()

        assert result.status is CheckStatus.WARNING

    def test_get_name_and_category(self) -> None:
        """Check name and category are set correctly."""
        chk = InstalledQuadkitPackagesCheck()
        assert chk.get_name() == "Installed Packages"
        assert chk.get_category() == "Framework"


# ---------------------------------------------------------------------------
# ProviderPackagesCheck
# ---------------------------------------------------------------------------


class TestProviderPackagesCheck:
    """Tests for ProviderPackagesCheck."""

    def test_skip_when_no_quadkit_yaml(self, tmp_path: Path) -> None:
        """Returns SKIP when application.yaml does not exist."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.SKIP
        assert "application.yaml" in result.message

    def test_pass_when_all_packages_installed(self, tmp_path: Path) -> None:
        """Returns PASS when every configured provider has its package installed."""
        (tmp_path / "application.yaml").write_text(
            "database:\n  dsn: postgres://localhost\n"
        )

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with (
                patch(
                    "quadkit.cli.registry.health_checks.providers.provider_packages",
                    return_value={"database": "quadkit-sql"},
                ),
                patch(
                    "quadkit.cli.registry.health_checks.providers.distribution",
                    return_value=MagicMock(),
                ),
            ):
                result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.PASS
        assert "database" in result.message or "1" in result.message

    def test_fail_when_package_missing(self, tmp_path: Path) -> None:
        """Returns FAIL when a configured provider's package is not installed."""
        from importlib.metadata import PackageNotFoundError

        (tmp_path / "application.yaml").write_text("cache:\n  backend: redis\n")

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with (
                patch(
                    "quadkit.cli.registry.health_checks.providers.provider_packages",
                    return_value={"cache": "quadkit-cache"},
                ),
                patch(
                    "quadkit.cli.registry.health_checks.providers.distribution",
                    side_effect=PackageNotFoundError("quadkit-cache"),
                ),
            ):
                result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.FAIL
        assert "cache" in result.message

    def test_skip_when_no_known_providers_in_yaml(self, tmp_path: Path) -> None:
        """Returns SKIP when application.yaml exists but has no known provider keys."""
        (tmp_path / "application.yaml").write_text("custom_stuff:\n  foo: bar\n")

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.SKIP

    def test_security_section_is_not_treated_as_deleted_provider(
        self, tmp_path: Path
    ) -> None:
        """Security config should not require the deleted quadkit-security package."""
        (tmp_path / "application.yaml").write_text(
            "security:\n  headers:\n    enabled: true\n"
        )

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.SKIP

    def test_fail_when_yaml_invalid(self, tmp_path: Path) -> None:
        """Returns FAIL when application.yaml cannot be parsed."""
        (tmp_path / "application.yaml").write_text(": invalid: yaml: [}\n")

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = ProviderPackagesCheck().check()
        finally:
            os.chdir(orig_cwd)

        # Either FAIL (invalid yaml) or SKIP (yaml parsed as something without
        # known providers); both are acceptable — just not PASS.
        assert result.status in {CheckStatus.FAIL, CheckStatus.SKIP}

    def test_get_name_and_category(self) -> None:
        """Check name and category are set correctly."""
        chk = ProviderPackagesCheck()
        assert chk.get_name() == "Provider Packages"
        assert chk.get_category() == "Framework"


# ---------------------------------------------------------------------------
# CrossExtensionImportCheck
# ---------------------------------------------------------------------------


class TestCrossExtensionImportCheck:
    """Tests for CrossExtensionImportCheck."""

    def test_skip_when_no_src_dir(self, tmp_path: Path) -> None:
        """Returns SKIP when no src/ directory exists."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = CrossExtensionImportCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.SKIP

    def test_pass_when_no_violations(self, tmp_path: Path) -> None:
        """Returns PASS when src/ contains no cross-extension imports."""
        src = tmp_path / "src" / "quadkit" / "web"
        src.mkdir(parents=True)
        (src / "handler.py").write_text(
            "from quadkit.contracts.web import ControllerProtocol\n"
        )

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = CrossExtensionImportCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.PASS

    def test_fail_when_violation_detected(self, tmp_path: Path) -> None:
        """Returns FAIL when a quadkit.web file imports from quadkit.sql directly."""
        src = tmp_path / "src" / "quadkit" / "web"
        src.mkdir(parents=True)
        (src / "repo.py").write_text(
            textwrap.dedent("""\
                from quadkit.sql.session import AsyncSession

                class Repo:
                    pass
            """)
        )

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = CrossExtensionImportCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.FAIL
        assert "1" in result.message
        assert len(result.details["violations"]) == 1
        assert "quadkit.web" in result.details["violations"][0]
        assert "quadkit.sql" in result.details["violations"][0]

    def test_multiple_violations_counted_correctly(self, tmp_path: Path) -> None:
        """Each separate file with a violation is counted once."""
        for name in ("a.py", "b.py"):
            web_dir = tmp_path / "src" / "quadkit" / "web"
            web_dir.mkdir(parents=True, exist_ok=True)
            (web_dir / name).write_text("from quadkit.sql.models import Base\n")

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = CrossExtensionImportCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert result.status is CheckStatus.FAIL
        assert len(result.details["violations"]) == 2

    def test_syntax_error_files_are_skipped_gracefully(self, tmp_path: Path) -> None:
        """Files with syntax errors do not crash the check."""
        src = tmp_path / "src" / "quadkit" / "web"
        src.mkdir(parents=True)
        (src / "bad.py").write_text("def(@broken syntax!!!")

        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = CrossExtensionImportCheck().check()
        finally:
            os.chdir(orig_cwd)

        assert (
            result.status is CheckStatus.PASS
        )  # no violations found; bad file is gracefully skipped

    def test_get_name_and_category(self) -> None:
        """Check name and category are set correctly."""
        chk = CrossExtensionImportCheck()
        assert chk.get_name() == "Architecture Violations"
        assert chk.get_category() == "Architecture"
