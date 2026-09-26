from pathlib import Path
import tomllib


def _load_pyproject(path: Path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_monitoring_extras_declared():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = _load_pyproject(pyproject)
    extras = data.get("project", {}).get("optional-dependencies", {})

    assert "otel" in extras, "Expected 'otel' extra in pyproject.toml"
    assert "prometheus" in extras, "Expected 'prometheus' extra in pyproject.toml"

    otel_extra = extras["otel"]
    assert any(
        "opentelemetry" in pkg for pkg in otel_extra
    ), "opentelemetry should be in the 'otel' extras"

    prom_extra = extras["prometheus"]
    assert any(
        "prometheus-client" in pkg for pkg in prom_extra
    ), "prometheus-client should be in the 'prometheus' extras"
