"""Webhook generator rendering tests."""

from __future__ import annotations

import ast
from pathlib import Path

from quadkit.web.cli.generators.webhook import WebhookGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _render(tmp_path: Path, name: str, **kwargs: object) -> str:
    """Generate a webhook module inside an anchored src-layout project."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "webhooks"
    out.mkdir(parents=True, exist_ok=True)
    result = WebhookGenerator(output_dir=out).generate(name, **kwargs)
    return Path(result.files_created[0]).read_text()


def test_webhook_generator_uses_server_side_secret_and_case_insensitive_header(
    tmp_path: Path,
) -> None:
    """Generated webhook shims read secrets server-side and normalize headers.

    Behaviour is exercised against the running module in
    ``test_webhook_shim_behaviour.py``; these assertions cover the shape a
    reader greps for.
    """
    content = _render(tmp_path, "payment")

    assert 'SIGNATURE_HEADER = "x-webhook-signature"' in content
    assert "signature = _header(headers, SIGNATURE_HEADER)" in content
    assert 'secret=os.getenv("WEBHOOK_PAYMENT_SECRET")' in content
    assert 'request.headers.get("x-webhook-secret")' not in content
    assert 'headers.get("X-Webhook-Signature")' not in content


def test_webhook_generator_fails_closed_when_secret_missing(tmp_path: Path) -> None:
    """Generated webhook handlers should not silently skip verification."""
    content = _render(tmp_path, "payment")

    assert 'message": "Webhook secret is not configured"' in content
    assert "if self.verify_signature:" in content


def test_webhook_generator_output_is_parseable_and_lint_shaped(tmp_path: Path) -> None:
    """Generated webhook modules should avoid the known lint regressions."""
    content = _render(tmp_path, "payment")

    ast.parse(content)
    assert '# noqa: BLE001' not in content
    assert 'logger.exception("Error handling webhook: %s", exc)' not in content
    assert 'logger.exception("Error handling webhook")' in content
