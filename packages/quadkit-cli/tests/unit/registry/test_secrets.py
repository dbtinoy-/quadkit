from __future__ import annotations

import stat
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


def _stat_600() -> os.stat_result:
    return os.stat_result((0o100600, 1, 1, 1, 0, 0, 0, 0, 0, 0))

import pytest

from quadkit.cli.registry.secrets import (
    DotenvSecretBackend,
    EnvVarSecretBackend,
    SecretBackend,
    SecretInfo,
    SecretsRegistry,
    generate_api_key,
    generate_jwt_secret,
    generate_secret,
)


class TestSecretInfo:
    def test_defaults(self) -> None:
        info = SecretInfo(name="key", description="desc")
        assert info.name == "key"
        assert info.required is True
        assert info.env_var is None

    def test_custom(self) -> None:
        info = SecretInfo(name="key", description="desc", required=False, env_var="MY_KEY")
        assert info.required is False
        assert info.env_var == "MY_KEY"


class TestSecretBackend:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            SecretBackend()


class TestEnvVarSecretBackend:
    def test_get(self) -> None:
        with patch("os.environ.get", return_value="val"):
            backend = EnvVarSecretBackend()
            assert backend.get("MY_KEY") == "val"

    def test_get_none(self) -> None:
        with patch("os.environ.get", return_value=None):
            backend = EnvVarSecretBackend()
            assert backend.get("NONEXISTENT") is None

    def test_set(self) -> None:
        with patch("os.environ") as mock_env:
            backend = EnvVarSecretBackend()
            backend.set("MY_KEY", "val")
            mock_env.__setitem__.assert_called_with("MY_KEY", "val")

    def test_delete(self) -> None:
        with patch("os.environ") as mock_env:
            backend = EnvVarSecretBackend()
            backend.delete("MY_KEY")
            mock_env.pop.assert_called_with("MY_KEY", None)

    def test_list(self) -> None:
        with patch("os.environ.keys", return_value=["A", "B"]):
            backend = EnvVarSecretBackend()
            assert backend.list() == ["A", "B"]

    def test_exists(self) -> None:
        backend = EnvVarSecretBackend()
        with patch("os.environ") as mock_env:
            mock_env.__contains__.return_value = True
            assert backend.exists("MY_KEY") is True

    def test_not_exists(self) -> None:
        backend = EnvVarSecretBackend()
        with patch("os.environ") as mock_env:
            mock_env.__contains__.return_value = False
            assert backend.exists("MY_KEY") is False


class TestDotenvSecretBackend:
    def test_load_existing_file(self) -> None:
        content = "KEY1=val1\nKEY2=val2\n"
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat", return_value=_stat_600()):
                with patch("builtins.open", mock_open(read_data=content)):
                    backend = DotenvSecretBackend(".env")
                    assert backend.get("KEY1") == "val1"
                    assert backend.get("KEY2") == "val2"

    def test_load_skips_comments(self) -> None:
        content = "# comment\nKEY=val\n"
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat", return_value=_stat_600()):
                with patch("builtins.open", mock_open(read_data=content)):
                    backend = DotenvSecretBackend(".env")
                    assert backend.get("KEY") == "val"

    def test_load_file_not_exists(self) -> None:
        with patch("pathlib.Path.exists", return_value=False):
            backend = DotenvSecretBackend(".env")
            assert backend.get("ANY") is None

    def test_set_and_save(self) -> None:
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("builtins.open", mock_open()) as m,
        ):
            backend = DotenvSecretBackend(".env")
            backend.set("NEW_KEY", "new_val")
            assert backend.get("NEW_KEY") == "new_val"

    def test_delete(self) -> None:
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("builtins.open", mock_open()),
        ):
            backend = DotenvSecretBackend(".env")
            backend._secrets = {"OLD": "val"}
            backend.delete("OLD")
            assert backend.get("OLD") is None

    def test_list(self) -> None:
        backend = DotenvSecretBackend(".env")
        backend._secrets = {"A": "1", "B": "2"}
        keys = backend.list()
        assert "A" in keys
        assert "B" in keys

    def test_exists(self) -> None:
        backend = DotenvSecretBackend(".env")
        backend._secrets = {"EXISTS": "yes"}
        assert backend.exists("EXISTS") is True
        assert backend.exists("MISSING") is False


class TestSecretsRegistry:
    def test_register_and_get_secret(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key", "desc", env_var="MY_KEY")
        with patch("os.environ.get", return_value="secret_val"):
            val = SecretsRegistry.get_secret("key")
            assert val == "secret_val"

    def test_get_secret_no_env_var(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key", "desc")
        with patch("os.environ.get", return_value="direct_val"):
            val = SecretsRegistry.get_secret("key")
            assert val == "direct_val"

    def test_set_secret(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key", "desc", env_var="MY_KEY")
        with patch("os.environ") as mock_env:
            SecretsRegistry.set_secret("key", "val")
            mock_env.__setitem__.assert_called_with("MY_KEY", "val")

    def test_delete_secret(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key", "desc", env_var="MY_KEY")
        with patch("os.environ") as mock_env:
            SecretsRegistry.delete_secret("key")
            mock_env.pop.assert_called_with("MY_KEY", None)

    def test_list_secrets(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry.register_secret("key1", "desc1")
        SecretsRegistry.register_secret("key2", "desc2", required=False)
        secrets = SecretsRegistry.list_secrets()
        assert len(secrets) == 2

    def test_check_secrets(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key1", "desc1", env_var="VAR1")
        SecretsRegistry.register_secret("key2", "desc2", env_var="VAR2")
        with patch("os.environ") as mock_env:
            mock_env.__contains__.side_effect = lambda k: k == "VAR1"
            results = SecretsRegistry.check_secrets()
            assert results["key1"] is True
            assert results["key2"] is False

    def test_get_missing_secrets(self) -> None:
        SecretsRegistry._secret_definitions = {}
        SecretsRegistry._backend = EnvVarSecretBackend()
        SecretsRegistry.register_secret("key1", "desc1", required=True, env_var="VAR1")
        SecretsRegistry.register_secret("key2", "desc2", required=False, env_var="VAR2")
        with patch("os.environ") as mock_env:
            mock_env.__contains__.return_value = False
            missing = SecretsRegistry.get_missing_secrets()
            assert len(missing) == 1
            assert missing[0].name == "key1"

    def test_set_backend(self) -> None:
        backend = DotenvSecretBackend(".env")
        SecretsRegistry.set_backend(backend)
        assert SecretsRegistry._backend is backend


class TestGenerateSecret:
    def test_default_length(self) -> None:
        secret = generate_secret()
        assert len(secret) == 32

    def test_custom_length(self) -> None:
        secret = generate_secret(length=16)
        assert len(secret) == 16

    def test_include_digits(self) -> None:
        secret = generate_secret(length=100, include_digits=True)
        assert any(c.isdigit() for c in secret)

    def test_no_digits(self) -> None:
        secret = generate_secret(length=100, include_digits=False)
        assert all(c.isalpha() for c in secret)

    def test_include_special(self) -> None:
        secret = generate_secret(length=100, include_special=True)
        assert any(not c.isalnum() for c in secret)


class TestGenerateApiKey:
    def test_starts_with_lg(self) -> None:
        key = generate_api_key()
        assert key.startswith("lg_")

    def test_length(self) -> None:
        key = generate_api_key()
        assert len(key) > 32


class TestGenerateJwtSecret:
    def test_length(self) -> None:
        secret = generate_jwt_secret(length=64)
        assert len(secret) == 64

    def test_default_length(self) -> None:
        secret = generate_jwt_secret()
        assert len(secret) == 64


class TestDotenvSecretBackendPermissions:
    def test_save_sets_owner_only_permissions(self, tmp_path) -> None:
        env_file = tmp_path / ".env"
        backend = DotenvSecretBackend(str(env_file))
        backend.set("api_key", "s3cret")
        mode = stat.S_IMODE(env_file.stat().st_mode)
        assert mode & 0o077 == 0

    def test_load_rejects_group_readable_file(self, tmp_path) -> None:
        from quadkit.security.secrets.store import SecretAccessError

        env_file = tmp_path / ".env"
        env_file.write_text("api_key=s3cret\n")
        env_file.chmod(0o644)
        with pytest.raises(SecretAccessError):
            DotenvSecretBackend(str(env_file))

    def test_load_accepts_owner_only_file(self, tmp_path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("api_key=s3cret\n")
        env_file.chmod(0o600)
        backend = DotenvSecretBackend(str(env_file))
        assert backend.get("api_key") == "s3cret"
