"""Tests for CLI constants."""

import pytest
from quadkit.cli.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_CONFIG_FILE,
    FORMAT_TEXT,
    FORMAT_JSON,
    FORMAT_TABLE,
)


class TestCLIEnvConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_CLI__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"


class TestCLIDefaults:
    def test_default_output_format(self) -> None:
        assert DEFAULT_OUTPUT_FORMAT == "text"

    def test_default_log_level(self) -> None:
        assert DEFAULT_LOG_LEVEL == "INFO"

    def test_default_config_file(self) -> None:
        assert DEFAULT_CONFIG_FILE == "application.yaml"


class TestOutputFormats:
    def test_text(self) -> None:
        assert FORMAT_TEXT == "text"

    def test_json(self) -> None:
        assert FORMAT_JSON == "json"

    def test_table(self) -> None:
        assert FORMAT_TABLE == "table"
