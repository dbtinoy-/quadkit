"""CLI scaffold + config validators: pure rendering and validation logic."""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from quadkit.cli.registry.config import (
    AuthConfigValidator,
    ConfigValidatorRegistry,
    DatabaseConfigValidator,
    EnvironmentVariablesValidator,
    ProductionValidator,
    RequiredFieldsValidator,
    SecretValidationValidator,
    has_errors,
    validate_config,
)
from quadkit.cli.scaffold import (
    _TEMPLATE_SPECS,
    TEMPLATES,
    component_packages,
    render_project,
    resolve_template,
    template_names,
)
from quadkit.cli.scaffold_package import render_package


class TestScaffoldTemplates:
    def test_template_names(self) -> None:
        names = template_names()
        assert set(names) == set(TEMPLATES) == set(_TEMPLATE_SPECS)
        assert names == ["api"]

    def test_resolve_template(self) -> None:
        spec = resolve_template("api")
        assert spec.name == "api"
        assert "web" in spec.features
        assert "quadkit-web" in spec.dependencies
        assert "uvicorn" in spec.dependencies

    def test_resolve_unknown_template(self) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            resolve_template("nonexistent-template")

    def test_component_packages(self) -> None:
        pkgs = component_packages()
        assert isinstance(pkgs, dict)
        assert all(isinstance(v, tuple) for v in pkgs.values())


class TestRenderProject:
    def test_render_api(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        created = render_project("api", "my-app", target)
        assert created
        pyproject = target / "pyproject.toml"
        assert pyproject.exists()
        data = tomllib.loads(pyproject.read_text())
        assert data["project"]["name"] == "my-app"
        # app package uses underscores
        app_py = target / "src" / "my_app" / "app.py"
        assert app_py.exists()
        assert "Application" in app_py.read_text()

    def test_render_dashes_to_underscores(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        render_project("api", "my-cool-app", target)
        assert (target / "src" / "my_cool_app").is_dir()

    def test_render_refuses_non_empty(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        target.mkdir()
        (target / "keep.txt").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="not empty"):
            render_project("api", "p", target)

    def test_render_force_overwrites(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        target.mkdir()
        (target / "keep.txt").write_text("x", encoding="utf-8")
        created = render_project("api", "p", target, force=True)
        assert created
        assert (target / "keep.txt").exists()  # foreign files untouched

    def test_render_api_has_the_web_feature(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        render_project("api", "big-app", target)
        text = (target / "src" / "big_app" / "app.py").read_text()
        assert "web" in TEMPLATES["api"].features
        assert "WebModule" in text

    def test_render_api_composition_root_has_builders(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"
        render_project("api", "shop-api", target)
        text = (target / "src" / "shop_api" / "app.py").read_text()
        assert "def build_modules() -> list[object]:" in text
        assert "def build_providers() -> list[Provider]:" in text
        assert "def create_app(config: QuadkitConfig | None = None)" in text
        assert '"build_modules", "build_providers"' in text
        assert "    return []\n" in text
        compile(text, "app.py", "exec")

    def test_render_api_docstring_has_no_stray_blank_lines(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "proj"
        render_project("api", "shop-api", target)
        text = (target / "src" / "shop_api" / "app.py").read_text()
        docstring = text.split('"""')[1]
        assert "\n\n\n" not in docstring
        assert "Convention followed: **Composition root**" in docstring

    def test_unknown_template_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            render_project("nope", "p", tmp_path / "x")


class TestRenderPackage:
    def test_render_package(self, tmp_path: Path) -> None:
        target = tmp_path / "quadkit-my-feature"
        created = render_package(
            "my_feature",
            target,
            class_name="MyFeature",
            description="Does things",
        )
        assert created

        pyproject = tomllib.loads((target / "pyproject.toml").read_text())
        assert pyproject["project"]["name"] == "quadkit-my-feature"
        assert "quadkit" in pyproject["project"]["dependencies"]

        provider = (
            target / "src" / "quadkit" / "my_feature" / "di" / "provider.py"
        ).read_text()
        assert "class MyFeatureProvider(Provider)" in provider
        assert 'name = "my_feature"' in provider

        init = (target / "src" / "quadkit" / "my_feature" / "__init__.py").read_text()
        assert "MyFeatureProvider" in init
        assert "Does things" in init

    def test_derived_class_name(self, tmp_path: Path) -> None:
        target = tmp_path / "pkg"
        render_package("user_store", target)
        provider = (
            target / "src" / "quadkit" / "user_store" / "di" / "provider.py"
        ).read_text()
        assert "class UserStoreProvider" in provider

    def test_refuses_non_empty_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "pkg"
        target.mkdir()
        (target / "x").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="not empty"):
            render_package("f", target)


# ---------------------------------------------------------------------------
# Config validators
# ---------------------------------------------------------------------------


class TestRequiredFieldsValidator:
    def test_clean(self) -> None:
        v = RequiredFieldsValidator()
        v.REQUIRED_FIELDS = {"project": ["name"]}
        assert v.validate({"project": {"name": "x"}}) == []
        assert v.get_name() == "Required Fields"

    def test_missing_section_and_field(self) -> None:
        v = RequiredFieldsValidator()
        v.REQUIRED_FIELDS = {"project": ["name", "version"]}
        issues = v.validate({})
        assert any("Missing required section" in i.message for i in issues)
        issues = v.validate({"project": {"name": "x"}})
        assert any("Missing required field" in i.message for i in issues)
        assert all(i.severity == "error" for i in issues)

    def test_non_dict_section_skipped(self) -> None:
        v = RequiredFieldsValidator()
        v.REQUIRED_FIELDS = {"project": ["name"]}
        assert v.validate({"project": "just-a-string"}) == []


class TestSecretValidationValidator:
    def test_placeholder_secret_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        v = SecretValidationValidator()
        issues = v.validate(
            {"db": {"password": "change-me-123"}},
        )
        assert any("placeholder secret" in i.message for i in issues)
        assert all(i.severity == "error" for i in issues)

    def test_env_ref_unset_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TOTALLY_UNSET_XYZ", raising=False)
        v = SecretValidationValidator()
        issues = v.validate({"db": {"url": "postgres://${TOTALLY_UNSET_XYZ}"}})
        assert any("TOTALLY_UNSET_XYZ" in i.message for i in issues)

    def test_env_ref_set_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SET_SECRET_XYZ", "value")
        v = SecretValidationValidator()
        issues = v.validate({"db": {"url": "postgres://${SET_SECRET_XYZ}"}})
        assert issues == []

    def test_non_secret_fields_ignored(self) -> None:
        v = SecretValidationValidator()
        assert v.validate({"db": {"host": "change-me"}}) == []


class TestProductionValidator:
    def test_production_debug_flagged(self) -> None:
        v = ProductionValidator()
        issues = v.validate({"web": {"debug": True}}, env="production")
        assert any(i.severity == "error" for i in issues)

    def test_production_localhost_warns(self) -> None:
        v = ProductionValidator()
        issues = v.validate(
            {"database": {"url": "postgres://localhost/x"}}, env="production"
        )
        assert any(i.severity == "warning" for i in issues)

    def test_development_untouched(self) -> None:
        v = ProductionValidator()
        assert v.validate({"web": {"debug": True}}, env="development") == []

    def test_production_clean(self) -> None:
        v = ProductionValidator()
        assert (
            v.validate(
                {"web": {"debug": False}, "database": {"url": "postgres://db/x"}},
                env="production",
            )
            == []
        )


class TestDatabaseConfigValidator:
    def test_missing_url_error(self) -> None:
        v = DatabaseConfigValidator()
        issues = v.validate({"database": {}})
        assert issues
        assert issues[0].severity == "error"

    def test_memory_sqlite_warning(self) -> None:
        v = DatabaseConfigValidator()
        issues = v.validate({"database": {"url": "sqlite:///:memory:"}})
        assert any(i.severity == "warning" for i in issues)

    def test_file_sqlite_ok(self) -> None:
        v = DatabaseConfigValidator()
        assert v.validate({"database": {"url": "sqlite:///data.db"}}) == []

    def test_no_database_section(self) -> None:
        v = DatabaseConfigValidator()
        assert v.validate({}) == []


class TestAuthConfigValidator:
    def test_enabled_without_secret(self) -> None:
        v = AuthConfigValidator()
        issues = v.validate({"auth": {"enabled": True}})
        assert issues
        assert issues[0].severity == "error"

    def test_enabled_with_secret(self) -> None:
        v = AuthConfigValidator()
        assert v.validate({"auth": {"enabled": True, "secret": "s"}}) == []

    def test_disabled_skipped(self) -> None:
        v = AuthConfigValidator()
        assert v.validate({"auth": {"enabled": False}}) == []


class TestEnvironmentVariablesValidator:
    def test_missing_var_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_VAR_XYZ", raising=False)
        v = EnvironmentVariablesValidator()
        issues = v.validate({"a": {"b": "${MISSING_VAR_XYZ}"}})
        assert any("MISSING_VAR_XYZ" in i.message for i in issues)

    def test_set_var_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRESENT_VAR_XYZ", "v")
        v = EnvironmentVariablesValidator()
        assert v.validate({"a": "${PRESENT_VAR_XYZ}"}) == []


class TestValidateConfigFacade:
    def test_returns_all_validators(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NOPE_VAR_XYZ", raising=False)
        results = validate_config({"database": {"url": ""}})
        assert "Database" in results
        assert "Required Fields" in results
        assert has_errors(results)  # missing database.url is an error

    def test_clean_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CFG_OK_VAR", "v")
        results = validate_config(
            {"database": {"url": "postgres://db/x"}, "auth": {"enabled": False}},
        )
        assert has_errors(results) is False

    def test_validator_exception_recorded(self) -> None:
        class Bad(RequiredFieldsValidator):
            def validate(self, config, env="development"):
                raise RuntimeError("boom")

        registry = ConfigValidatorRegistry()
        registry.register(Bad)
        assert len(registry.get_all_validators()) == 1

    def test_registry_defaults(self) -> None:
        reg = ConfigValidatorRegistry.with_defaults()
        names = {c.get_name() for c in (v() for v in reg.get_all_validators())}
        assert "Secrets" in names
        assert "Database" in names
        assert len(reg.get_all_validators()) == 6
