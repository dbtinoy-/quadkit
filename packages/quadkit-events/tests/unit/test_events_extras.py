from pathlib import Path
import tomllib


def _load_pyproject(path: Path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_messaging_extra_declared():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = _load_pyproject(pyproject)
    extras = data.get("project", {}).get("optional-dependencies", {})

    assert "messaging" in extras, "Expected 'messaging' extra in pyproject.toml"

    messaging = extras["messaging"]
    assert any(
        "aiokafka" in pkg for pkg in messaging
    ), "aiokafka should be in 'messaging' extras"
    assert any(
        "aio-pika" in pkg for pkg in messaging
    ), "aio-pika should be in 'messaging' extras"
