"""Tests for CLI error hierarchy."""

from quadkit.cli.exceptions import CliError


class TestCliError:
    def test_basic_error(self):
        err = CliError("something broke")
        assert "something broke" in str(err)
        assert err.message == "something broke"

    def test_error_with_hints(self):
        err = CliError(
            "Database connection failed",
            causes=["PostgreSQL is not running", "Database does not exist"],
            suggestions=["Start PostgreSQL: sudo systemctl start postgresql",
                         "Check config: quadkit config show database"],
        )
        assert err.causes == ["PostgreSQL is not running", "Database does not exist"]
        assert len(err.suggestions) == 2

    def test_error_with_no_extras(self):
        err = CliError("simple error")
        assert err.causes == []
        assert err.suggestions == []

    def test_error_inherits_quadkit_error(self):
        from quadkit.contracts.exceptions import QuadkitError
        err = CliError("test")
        assert isinstance(err, QuadkitError)

    def test_config_not_found_error(self):
        from quadkit.cli.exceptions import ConfigNotFoundError
        err = ConfigNotFoundError()
        assert "application.yaml" in err.message
        assert any("quadkit init" in s for s in err.suggestions)

    def test_provider_not_installed_error(self):
        from quadkit.cli.exceptions import ProviderNotInstalledError
        err = ProviderNotInstalledError("quadkit-example")
        assert "quadkit-example" in err.message
