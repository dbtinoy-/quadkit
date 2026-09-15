from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.lib.config_gen import (
    _collect_comments,
    _dict_to_yaml_lines,
    _format_yaml_value,
    _get_default_value,
    _import_config_class,
    _is_instance_of_domain_model,
    _is_pydantic_model,
    _model_to_yaml_dict,
    generate_package_config,
    run_config_gen,
)


class TestImportConfigClass:
    def test_import_success(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_mod.DatabaseConfig = "DatabaseConfigCls"
            mock_import.return_value = mock_mod
            result = _import_config_class("quadkit.sql.config:DatabaseConfig")
            assert result == "DatabaseConfigCls"

    def test_import_failure(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module", side_effect=ImportError):
            with pytest.raises(ImportError):
                _import_config_class("nonexistent.module:Cls")


class TestGetDefaultValue:
    def test_has_default(self) -> None:
        field_info = MagicMock()
        field_info.default = 42
        field_info.default_factory = None
        assert _get_default_value(field_info, "field") == 42

    def test_no_default(self) -> None:
        field_info = MagicMock()
        field_info.default = None
        field_info.default_factory = None
        assert _get_default_value(field_info, "field") is None

    def test_has_factory(self) -> None:
        field_info = MagicMock()
        field_info.default = None
        field_info.default_factory = lambda: "factory_val"
        assert _get_default_value(field_info, "field") == "factory_val"

    def test_factory_raises(self) -> None:
        field_info = MagicMock()
        field_info.default = None
        field_info.default_factory = MagicMock(side_effect=RuntimeError)
        assert _get_default_value(field_info, "field") is None


class TestIsPydanticModel:
    def test_is_model(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module") as mock_import:
            mock_domain = MagicMock()
            mock_domain.DomainModel = type("DomainModel", (), {})
            mock_import.return_value = mock_domain

            class FakeModel(mock_domain.DomainModel):
                pass

            assert _is_pydantic_model(FakeModel) is True

    def test_not_model(self) -> None:
        assert _is_pydantic_model(str) is False

    def test_import_error(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module", side_effect=ImportError):
            assert _is_pydantic_model(str) is False


class TestModelToYamlDict:
    def test_converts_fields(self) -> None:
        mock_cls = MagicMock()
        mock_cls.model_fields = {
            "name": MagicMock(annotation=str),
            "count": MagicMock(annotation=int),
        }

        def get_default(field_info, name):
            return {"name": 42, "count": 10}.get(name)

        with patch("quadkit.cli.lib.config_gen._get_default_value", side_effect=get_default):
            result = _model_to_yaml_dict(mock_cls)
            assert "name" in result
            assert "count" in result


class TestCollectComments:
    def test_collects_descriptions(self) -> None:
        mock_cls = MagicMock()
        mock_field = MagicMock()
        mock_field.annotation = str
        mock_field.description = "A field"
        mock_cls.model_fields = {"name": mock_field}

        comments = _collect_comments(mock_cls)
        assert "name" in comments
        assert comments["name"] == "A field"

    def test_skips_classvar(self) -> None:
        from typing import ClassVar
        mock_cls = MagicMock()
        mock_field = MagicMock()
        mock_field.annotation = ClassVar[int]
        mock_cls.model_fields = {"ignored": mock_field}

        comments = _collect_comments(mock_cls)
        assert "ignored" not in comments


class TestFormatYamlValue:
    def test_bool(self) -> None:
        assert _format_yaml_value(True) == "true"
        assert _format_yaml_value(False) == "false"

    def test_string(self) -> None:
        val = _format_yaml_value("hello")
        assert isinstance(val, str)
        assert "hello" in val

    def test_string_with_special_chars(self) -> None:
        val = _format_yaml_value("hello: world")
        assert val.startswith('"')

    def test_none(self) -> None:
        assert _format_yaml_value(None) == "null"

    def test_int(self) -> None:
        assert _format_yaml_value(42) == "42"


class TestDictToYamlLines:
    def test_basic(self) -> None:
        lines = _dict_to_yaml_lines({"key": "value"}, {})
        assert any("key" in l for l in lines)

    def test_with_comments(self) -> None:
        lines = _dict_to_yaml_lines({"key": "value"}, {"key": "A comment"})
        assert any("A comment" in l for l in lines)

    def test_nested_dict(self) -> None:
        lines = _dict_to_yaml_lines({"nested": {"inner": "val"}}, {})
        assert any("inner" in l for l in lines)

    def test_bool_value(self) -> None:
        lines = _dict_to_yaml_lines({"enabled": True}, {})
        assert any("true" in l for l in lines)

    def test_none_value(self) -> None:
        lines = _dict_to_yaml_lines({"optional": None}, {})
        assert any("null" in l for l in lines)

    def test_empty_list(self) -> None:
        lines = _dict_to_yaml_lines({"items": []}, {})
        assert any("[]" in l for l in lines)


class TestIsInstanceOfDomainModel:
    def test_is_instance_true(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module") as mock_import:
            mock_domain = MagicMock()
            DomainModel = type("DomainModel", (), {})
            mock_domain.DomainModel = DomainModel
            mock_import.return_value = mock_domain

            class FakeModel(DomainModel):
                pass

            assert _is_instance_of_domain_model(FakeModel()) is True

    def test_is_instance_false(self) -> None:
        assert _is_instance_of_domain_model(42) is False

    def test_import_error(self) -> None:
        with patch("quadkit.cli.lib.config_gen.importlib.import_module", side_effect=ImportError):
            assert _is_instance_of_domain_model("test") is False


class TestGeneratePackageConfig:
    @patch("quadkit.cli.lib.config_gen._import_config_class")
    @patch("quadkit.cli.lib.config_gen._model_to_yaml_dict", return_value={"key": "val"})
    @patch("quadkit.cli.lib.config_gen._collect_comments", return_value={})
    def test_generates_config(self, mock_comments, mock_model, mock_import) -> None:
        mock_import.return_value = MagicMock(__name__="DatabaseConfig")
        result = generate_package_config("database", "quadkit.sql.config:DatabaseConfig")
        assert "database" in result
        assert "key" in result

    @patch("quadkit.cli.lib.config_gen._import_config_class", side_effect=ImportError("no module"))
    def test_import_error_handling(self, mock_import) -> None:
        result = generate_package_config("database", "nonexistent:Config")
        assert "Failed to import" in result


class TestRunConfigGen:
    def test_all_packages(self) -> None:
        mock_args = MagicMock()
        mock_args.output_dir = "/tmp/config_gen_test"
        mock_args.package = None
        mock_args.generate_all = True
        mock_args.overwrite = True
        mock_args.with_comments = True

        with patch("pathlib.Path.mkdir"):
            with patch("quadkit.cli.lib.config_gen.generate_package_config", return_value="key: val\n"):
                with patch("pathlib.Path.write_text"):
                    run_config_gen(mock_args)

    def test_specific_package(self) -> None:
        mock_args = MagicMock()
        mock_args.output_dir = "/tmp/config_gen_test"
        mock_args.package = "database"
        mock_args.generate_all = False
        mock_args.overwrite = True
        mock_args.with_comments = True

        with patch("pathlib.Path.mkdir"):
            with patch("quadkit.cli.lib.config_gen.generate_package_config", return_value="database:\n  key: val\n"):
                with patch("pathlib.Path.write_text"):
                    run_config_gen(mock_args)

    def test_no_package_no_all(self) -> None:
        mock_args = MagicMock()
        mock_args.output_dir = "/tmp"
        mock_args.package = None
        mock_args.generate_all = False

        run_config_gen(mock_args)

    def test_unknown_package(self) -> None:
        mock_args = MagicMock()
        mock_args.output_dir = "/tmp"
        mock_args.package = "unknown"
        mock_args.generate_all = False
        mock_args.overwrite = True
        mock_args.with_comments = True

        with patch("pathlib.Path.mkdir"):
            run_config_gen(mock_args)
