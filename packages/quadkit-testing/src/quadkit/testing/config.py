"""Configuration models for Quadkit Testing.

This module provides Pydantic models for configuring testing utilities.

Example:
    from quadkit.testing.config import TestingConfig

    # From YAML
    config = TestingConfig.from_yaml("application.yaml")

    # From environment
    config = TestingConfig()  # reads QK_TESTING__* env vars
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.testing import constants as test_const
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class TestingConfig(BaseConfig):
    """Hierarchical root configuration for Quadkit Testing.

    Attributes:
        enabled: Whether testing module is enabled
        db_reuse: Reuse test databases between tests
        mock_external_services: Mock external service calls
        cleanup_temp_files: Clean up temporary files after tests
    """

    config_section: ClassVar[str] = "testing"

    model_config = cast(
        "ConfigDict",
        {
            "env_prefix": test_const.ENV_PREFIX,
            "env_nested_delimiter": test_const.ENV_NESTED_DELIMITER,
            "extra": "ignore",
        },
    )

    name: str = "testing"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    db_reuse: bool = Field(
        default=True,
        description="Reuse test databases between tests",
    )
    mock_external_services: bool = Field(
        default=True,
        description="Mock external service calls",
    )
    cleanup_temp_files: bool = Field(
        default=True,
        description="Clean up temporary files after tests",
    )


__all__ = ["TestingConfig"]
