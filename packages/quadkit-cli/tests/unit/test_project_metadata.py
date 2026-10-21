"""Tests for shared project metadata rendering and CLI scaffold integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.cli.scaffold import (
    ProjectMetadataContext,
    render_project,
    render_project_metadata,
)


def _context(**overrides: object) -> ProjectMetadataContext:
    values: dict[str, object] = {
        "project_name": "inventory-api",
        "package_name": "inventory_api",
        "summary": "A small API project.",
        "template_name": "api",
        "features": ("web",),
        "dependencies": ("quadkit>=0.0.1", "quadkit-web>=0.0.1", "uvicorn"),
        "layout": (
            ("README.md", "human quickstart"),
            ("application.yaml", "runtime configuration"),
            ("pyproject.toml", "dependencies and tools"),
            ("src/inventory_api/app.py", "composition root"),
            ("src/inventory_api/controllers/", "HTTP controllers"),
            ("tests/", "project tests"),
        ),
        "commands": (
            ('pip install -e ".[dev]"', "install project and development tools"),
            ("python -m pytest", "run the tests"),
        ),
        "notes": (),
    }
    values.update(overrides)
    return ProjectMetadataContext(**values)  # type: ignore[arg-type]


def test_renderer_is_deterministic_and_returns_only_app_agent_file() -> None:
    context = _context()

    first = render_project_metadata(context)
    second = render_project_metadata(context)

    assert first == second
    assert tuple(first) == ("AGENTS.md",)
    text = first["AGENTS.md"]
    assert text.startswith("# Agent Guide: inventory-api\n")
    assert "src/inventory_api/app.py" in text
    assert "src/inventory_api/controllers/" in text
    assert "python -m pytest" in text
    assert "https://oridecon.dev/quadkit/getting-started/for-coding-agents/" in text
    assert "robots.txt" not in text
    assert "quadkit-skills" not in text
    assert len(text.splitlines()) < 120


def test_renderer_escapes_markdown_in_summary() -> None:
    text = render_project_metadata(_context(summary="API *notes* [draft]"))["AGENTS.md"]

    assert "API \\*notes\\* \\[draft\\]" in text


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_name", "../bad", "project_name"),
        ("package_name", "bad-package", "package_name"),
        ("summary", "first line\n# injected", "summary"),
        (
            "layout",
            (("../../private/AGENTS.md", "escape"),),
            "layout path",
        ),
        (
            "commands",
            (("python\nmalicious", "run"),),
            "command",
        ),
    ],
)
def test_context_rejects_unsafe_values(field: str, value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _context(**{field: value})


def test_cli_scaffold_metadata_matches_the_selected_template(tmp_path: Path) -> None:
    target = tmp_path / "minimal_app"
    render_project("api", "minimal-app", target)

    agent_file = (target / "AGENTS.md").read_text(encoding="utf-8")
    pyproject = (target / "pyproject.toml").read_text(encoding="utf-8")

    assert "REST API with the web framework" in agent_file
    assert "quadkit-web" in agent_file
    assert "README.md" in agent_file
    assert "application.yaml" in agent_file
    assert "src/minimal_app/app.py" in agent_file
    from tomllib import loads

    manifest = loads(pyproject)
    assert "quadkit" in manifest["project"]["dependencies"]
    assert any(
        dependency.startswith("quadkit-web")
        for dependency in manifest["project"]["dependencies"]
    )


def test_web_scaffold_metadata_is_feature_aware(tmp_path: Path) -> None:
    target = tmp_path / "web_api"
    render_project("api", "web-api", target)

    agent_file = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert "Framework features: `web`" in agent_file
    assert "quadkit dev" in agent_file
    assert "HTTP controllers" in agent_file
    assert "quadkit-web" in agent_file
    assert "replace QK_AUTH__SECRET_KEY" not in agent_file


def test_auth_scaffold_metadata_carries_secret_warning_when_available(
    tmp_path: Path,
) -> None:
    from quadkit.cli.scaffold import template_names

    if "full" not in template_names():
        pytest.skip("full template requires optional provider packages")

    target = tmp_path / "full_app"
    render_project("full", "full-app", target)
    agent_file = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert "Important project notes" in agent_file
    unescaped = agent_file.replace("\\_", "_")
    assert "replace QK_AUTH__SECRET_KEY" in unescaped
    assert "QK_AUTH__TOKEN__SECRET_KEY" in unescaped


def test_agent_metadata_is_included_in_the_render_project_file_result(
    tmp_path: Path,
) -> None:
    created = render_project("api", "my-app", tmp_path / "my-app")

    assert tmp_path / "my-app" / "AGENTS.md" in created


def test_default_scaffold_does_not_overwrite_existing_agent_guidance(
    tmp_path: Path,
) -> None:
    target = tmp_path / "my-app"
    render_project("api", "my-app", target)
    agent_file = target / "AGENTS.md"
    agent_file.write_text("# project-owned guidance\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not empty"):
        render_project("api", "my-app", target)

    assert agent_file.read_text(encoding="utf-8") == "# project-owned guidance\n"


def test_force_scaffold_refreshes_agent_guidance_from_selected_template(
    tmp_path: Path,
) -> None:
    target = tmp_path / "my-app"
    render_project("api", "my-app", target)
    agent_file = target / "AGENTS.md"
    agent_file.write_text("# project-owned guidance\n", encoding="utf-8")

    render_project("api", "my-app", target, force=True)

    refreshed = agent_file.read_text(encoding="utf-8")
    assert refreshed.startswith("# Agent Guide: my-app\n")
    assert "Framework features: `web`" in refreshed
    assert "project-owned guidance" not in refreshed
