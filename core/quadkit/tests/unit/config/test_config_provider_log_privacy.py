"""Privacy regression tests for config-provider diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import quadkit.config.di.provider as provider_module
from quadkit.config.di.provider import ConfigProvider
from quadkit.di.container import Container


@pytest.mark.asyncio
async def test_config_provider_log_omits_default_config_path_and_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_exists = Path.exists
    private_path = str(Path.cwd() / "PRIVATE_CONFIG_PATH_SENTINEL" / "application.yaml")

    def fail_private_application_yaml(
        path: Path, *args: object, **kwargs: object
    ) -> bool:
        if path.name == "application.yaml" and path.parent == Path.cwd():
            raise OSError(f"PRIVATE_CONFIG_ERROR_SENTINEL {private_path}")
        return original_exists(path, *args, **kwargs)

    mock_logger = MagicMock()
    monkeypatch.setattr(provider_module, "logger", mock_logger)
    monkeypatch.setattr(Path, "exists", fail_private_application_yaml)
    await ConfigProvider().register(Container())

    mock_logger.debug.assert_called_once_with("no_default_config", error_type="OSError")
    rendered = str(mock_logger.mock_calls)
    assert "PRIVATE_CONFIG_PATH_SENTINEL" not in rendered
    assert "PRIVATE_CONFIG_ERROR_SENTINEL" not in rendered
