from pathlib import Path
import tomllib


def _load_pyproject(path: Path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_task_package_broker_extras_declared():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = _load_pyproject(pyproject)
    extras = data.get("project", {}).get("optional-dependencies", {})

    assert "redis" in extras, "Expected 'redis' extra in pyproject.toml"
    assert "rabbitmq" in extras, "Expected 'rabbitmq' extra in pyproject.toml"

    redis_extra = extras["redis"]
    assert any(
        "redis" in pkg for pkg in redis_extra
    ), "redis should be in the 'redis' extras"

    rabbit_extra = extras["rabbitmq"]
    assert any(
        "aio-pika" in pkg for pkg in rabbit_extra
    ), "aio-pika should be in the 'rabbitmq' extras"
