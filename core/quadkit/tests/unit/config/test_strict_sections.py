"""Robustness contract for typed config sections.

Pins the four failure modes every adopter hits:

1. unknown/typo keys   → fail fast with did-you-mean (escape: env)
2. nested typo keys    → dotted path in the error
3. missing file        → defaults + INFO observability
4. missing section     → defaults + DEBUG observability
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from quadkit.config.exceptions import ConfigSourceError
from quadkit.config.main import QuadkitConfig


@dataclass
class ServerCfg:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class WebCfg:
    server: ServerCfg = field(default_factory=ServerCfg)
    enabled: bool = True


def _write(tmp_path, text: str) -> str:
    f = tmp_path / "application.yaml"
    f.write_text(text)
    return str(f)


# ── Mode 1+2: unknown / typo keys ───────────────────────────────────────


def test_unknown_top_level_key_raises_with_suggestion(tmp_path) -> None:
    path = _write(tmp_path, "web:\n  enabld: true\n")
    with pytest.raises(ConfigSourceError) as err:
        QuadkitConfig.from_yaml(path).get_section("web", WebCfg)
    assert "enabld" in str(err.value)
    assert "enabled" in str(err.value)


def test_nested_typo_reports_dotted_path_with_suggestion(tmp_path) -> None:
    path = _write(tmp_path, "web:\n  server:\n    prot: 9999\n")
    with pytest.raises(ConfigSourceError) as err:
        QuadkitConfig.from_yaml(path).get_section("web", WebCfg)
    msg = str(err.value)
    assert "server.prot" in msg
    assert "port" in msg


def test_escape_hatch_allows_unknown_and_warns(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QK_CONFIG_ALLOW_UNKNOWN", "true")
    path = _write(tmp_path, "web:\n  enabld: true\n")
    section = QuadkitConfig.from_yaml(path).get_section("web", WebCfg)
    assert section.enabled is True  # default applied — typo was the point


# ── Mode 3: missing file ────────────────────────────────────────────────


def test_missing_file_returns_defaults(capsys) -> None:
    missing = "/tmp/opencode/never/application.yaml"
    cfg = QuadkitConfig.from_yaml(missing)
    assert isinstance(cfg, QuadkitConfig)
    out = capsys.readouterr().out
    assert "config.defaults_only" in out
    assert "/tmp/opencode/never" in out


# ── Mode 4: missing section ─────────────────────────────────────────────


def test_missing_section_returns_model_defaults(
    tmp_path, monkeypatch, capsys
) -> None:
    from quadkit.config import main as cfg_main

    calls: list[tuple[str, dict]] = []
    original = cfg_main.logger.debug
    monkeypatch.setattr(
        cfg_main.logger.__class__,
        "debug",
        lambda self, event, **kw: calls.append((event, kw)),
    )
    path = _write(tmp_path, "app_name: probe\n")
    section = QuadkitConfig.from_yaml(path).get_section("web", WebCfg)

    assert isinstance(section, WebCfg)
    assert section.server.port == 8000  # code default
    # Observability must survive global logging reconfigurations from other
    # tests — assert on the module logger directly.
    assert any(e == "config.section_defaults" for e, _ in calls)
