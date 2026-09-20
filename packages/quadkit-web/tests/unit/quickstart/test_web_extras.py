from pathlib import Path
import tomllib


def _load_pyproject(path: Path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_templates_extra_declared():
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    data = _load_pyproject(pyproject)
    extras = data.get("project", {}).get("optional-dependencies", {})

    assert "templates" in extras, "Expected 'templates' extra in pyproject.toml"
    templates = extras["templates"]
    assert any(
        "jinja2" in pkg for pkg in templates
    ), "jinja2 should be in 'templates' extras"
