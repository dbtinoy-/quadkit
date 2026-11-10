"""Unit tests for BaseConfig.from_env_profile fallback_path and strict nested coercion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest

from quadkit.config import BaseConfig, QuadkitConfig
from quadkit.domain import DomainModel
from quadkit.security.secrets import SecretValue
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class _NestedStrictItem(DomainModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True)

    enabled: bool = Field(default=False)
    label: str = Field(default="default")


@dataclass(init=False)
class _StrictContainer(DomainModel):
    item: _NestedStrictItem = Field(default_factory=_NestedStrictItem)


@dataclass(init=False)
class _NestedSecret(DomainModel):
    api_secret: SecretValue = Field(default=SecretValue(""))


@dataclass(init=False)
class _SecretCfg(BaseConfig):
    config_section = "secret_demo"
    signing_secret: SecretValue = Field(default=SecretValue("dev"))
    nested: _NestedSecret = Field(default_factory=_NestedSecret)


def test_from_env_profile_uses_fallback_path_when_base_path_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When CWD lacks application.yaml, from_env_profile resolves fallback_path."""
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    service_dir = tmp_path / "service"
    service_dir.mkdir()
    (service_dir / "application.yaml").write_text(
        "custom_svc:\n  name: demo-service\n  port: 8100\n",
        encoding="utf-8",
    )
    (service_dir / "application.staging.yaml").write_text(
        "custom_svc:\n  port: 9100\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(empty_cwd)
    monkeypatch.setenv("QK_PROFILE", "staging")

    cfg = QuadkitConfig.from_env_profile(fallback_path=service_dir)
    svc_section = cfg.get_section("custom_svc")
    assert isinstance(svc_section, dict)
    assert svc_section["name"] == "demo-service"
    assert svc_section["port"] == 9100


def test_from_env_profile_prefers_cwd_over_fallback_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When CWD has application.yaml, CWD wins over fallback_path."""
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    (cwd_dir / "application.yaml").write_text(
        "custom_svc:\n  name: cwd-service\n",
        encoding="utf-8",
    )
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    (fallback_dir / "application.yaml").write_text(
        "custom_svc:\n  name: fallback-service\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(cwd_dir)
    monkeypatch.delenv("QK_ENV", raising=False)
    monkeypatch.delenv("QK_PROFILE", raising=False)

    cfg = QuadkitConfig.from_env_profile(fallback_path=fallback_dir)
    svc_section = cfg.get_section("custom_svc")
    assert isinstance(svc_section, dict)
    assert svc_section["name"] == "cwd-service"


def test_nested_strict_domain_model_coerces_dict_payload() -> None:
    """Phase 2b coerces nested dict inputs onto strict DomainModel fields."""
    container = _StrictContainer(item={"enabled": True, "label": "ready"})
    assert isinstance(container.item, _NestedStrictItem)
    assert container.item.enabled is True
    assert container.item.label == "ready"


def test_secret_value_fields_coerce_from_str_and_mask_repr() -> None:
    """SecretValue fields on BaseConfig and nested DomainModels stay masked in repr."""
    cfg = QuadkitConfig.from_dict(
        {
            "secret_demo": {
                "signing_secret": "raw-signing-secret",
                "nested": {"api_secret": "raw-nested-secret"},
            }
        }
    ).get_section("secret_demo", _SecretCfg)

    assert isinstance(cfg.signing_secret, SecretValue)
    assert isinstance(cfg.nested.api_secret, SecretValue)
    assert "raw-signing-secret" not in repr(cfg)
    assert "raw-nested-secret" not in repr(cfg)
    assert str(cfg.signing_secret) == "raw-signing-secret"
    assert str(cfg.nested.api_secret) == "raw-nested-secret"
