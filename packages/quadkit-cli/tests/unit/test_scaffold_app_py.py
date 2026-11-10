"""The composition-root renderer's middleware seam."""

from __future__ import annotations

from quadkit.cli.scaffold.module_files import _app_py
from quadkit.cli.scaffold.specs import ProjectTemplateSpec


def test_app_py_registers_spec_middlewares() -> None:
    spec = ProjectTemplateSpec(
        name="sentinel_app",
        description="sentinel",
        dependencies=(),
        features=frozenset({"web"}),
        middlewares=(
            (
                "sentinel_app.shared.middleware.sentinel_middleware",
                "SentinelMiddleware",
                '{"maxAge": 613}',
            ),
            (
                "sentinel_app.shared.middleware.rate_limit",
                "RateLimitMiddleware",
                None,
            ),
        ),
    )

    text = _app_py("sentinel_app", "sentinel_app", spec)

    assert (
        "from sentinel_app.shared.middleware.sentinel_middleware import "
        "SentinelMiddleware"
    ) in text
    assert '(SentinelMiddleware, {"maxAge": 613}),' in text
    assert "(RateLimitMiddleware,)," in text
    compile(text, "app.py", "exec")


def test_app_py_without_middlewares_keeps_the_plain_web_call() -> None:
    spec = ProjectTemplateSpec(
        name="api",
        description="api",
        dependencies=(),
        features=frozenset({"web"}),
    )

    text = _app_py("api", "api", spec)

    assert "middleware=[" not in text
    compile(text, "app.py", "exec")
