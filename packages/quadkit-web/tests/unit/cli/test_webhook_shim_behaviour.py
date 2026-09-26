"""Webhook shim behaviour: signatures, header casing, payload types.

The generator's output is a module a user is expected to run *as generated*,
so these tests execute it rather than pattern-match it. Three defects found by
doing that (`QUADKIT_FRAMEWORK_BUGS.md` WEBHOOK-1..4):

* the secret came from a request header, so any caller could supply the value
  they had signed with;
* the signature header was read with one fixed casing, but ASGI transports
  lower-case header names — a correctly-signed request was rejected;
* the import block was not in the order ruff produces, so `ruff check` failed
  on a fresh file;
* payload field types were rendered verbatim, so a ``decimal``/``uuid``/
  ``datetime`` field produced a Pydantic model that could not be built and
  every request failed at ``Payload(**data)``.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

from quadkit.web.cli.generators.webhook import WebhookGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'

#: Field tokens whose annotations are not builtins -- one from each shape of
#: the rendering defect (module name, datetime name, composite).
TYPED_PAYLOAD = "order_id:uuid,amount:decimal,seen_at:datetime,payload:json"


def _generate(tmp_path: Path, name: str, **kwargs: object) -> Path:
    """Generate a webhook module inside an anchored src-layout project."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "webhooks"
    out.mkdir(parents=True, exist_ok=True)
    result = WebhookGenerator(output_dir=out).generate(name, **kwargs)
    return Path(result.files_created[0])


def _load(path: Path, module_name: str) -> object:
    """Import a generated module the way an application would."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _ruff(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ruff the way a generated project does: no ambient config.

    A generated project ships ``[tool.ruff] src = ["src"]`` and nothing else,
    which for import *order* is the same as ``--isolated``. Linting without
    the flag would instead pick up whatever config the test runner's working
    directory happens to sit under, and ``cwd`` is the generated project for
    the same reason: ruff's first-party detection depends on it.
    """
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args, "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=path.parents[2],
    )


@pytest.mark.parametrize(
    "header_name",
    ["x-webhook-signature", "X-Webhook-Signature", "X-WEBHOOK-SIGNATURE"],
)
def test_a_signed_request_is_accepted_whatever_case_the_header_uses(
    tmp_path: Path, header_name: str
) -> None:
    """Header names are case-insensitive; ASGI lower-cases them in practice."""
    module = _load(_generate(tmp_path, "payment"), "generated_payment_case")
    body = b'{"event_type": "payment.created", "timestamp": "2026-09-23T00:00:00Z"}'

    async def run() -> dict[str, object]:
        webhook = module.PaymentWebhook(secret="s3cret", verify_signature=True)

        async def handler(payload: object) -> dict[str, object]:
            return {"ok": True}

        webhook.register_handler("payment.created", handler)
        return await webhook.handle_request(body, {header_name: _sign("s3cret", body)})

    assert asyncio.run(run())["status"] == "success"


def test_missing_and_wrong_signatures_fail_closed(tmp_path: Path) -> None:
    module = _load(_generate(tmp_path, "payment"), "generated_payment_verify")
    body = b'{"event_type": "payment.created", "timestamp": "2026-09-23T00:00:00Z"}'

    async def run() -> tuple[str, str, str]:
        webhook = module.PaymentWebhook(secret="s3cret", verify_signature=True)
        missing = await webhook.handle_request(body, {})
        wrong = await webhook.handle_request(
            body, {"x-webhook-signature": "not-the-signature"}
        )
        # A request that carries the secret it signed with must not verify:
        # that is what taking the secret from a request header would allow.
        forged = await webhook.handle_request(
            body,
            {
                "x-webhook-secret": "attacker-chosen",
                "x-webhook-signature": _sign("attacker-chosen", body),
            },
        )
        return str(missing["message"]), str(wrong["message"]), str(forged["message"])

    assert asyncio.run(run()) == (
        "Missing signature",
        "Invalid signature",
        "Invalid signature",
    )


def test_an_unconfigured_secret_refuses_rather_than_skipping_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shim reads the secret from the environment; absent must mean no.

    ``secret is None`` used to make ``_verify_signature`` return ``True``, so
    an environment that never set the variable accepted anything.
    """
    monkeypatch.delenv("WEBHOOK_PAYMENT_SECRET", raising=False)
    module = _load(_generate(tmp_path, "payment"), "generated_payment_no_secret")
    body = b'{"event_type": "payment.created", "timestamp": "2026-09-23T00:00:00Z"}'

    async def run() -> str:
        webhook = module.PaymentWebhook(
            secret=os.getenv("WEBHOOK_PAYMENT_SECRET"), verify_signature=True
        )
        result = await webhook.handle_request(
            body, {"x-webhook-signature": _sign("s3cret", body)}
        )
        return str(result["message"])

    assert asyncio.run(run()) == "Webhook secret is not configured"


def test_a_custom_payload_still_carries_the_dispatch_key(tmp_path: Path) -> None:
    """``--fields`` must not remove the field the handler dispatches on."""
    content = _generate(tmp_path, "payment", fields_str="order_id:uuid").read_text()

    assert "event_type: str = Field(" in content
    # A caller who names it keeps theirs: no duplicate model field.
    named = _generate(
        tmp_path / "named", "payment", fields_str="event_type:str,order_id:uuid"
    ).read_text()
    assert named.count("event_type: str = Field(") == 1


def test_the_secret_is_read_server_side_never_from_the_request(tmp_path: Path) -> None:
    content = _generate(tmp_path, "payment").read_text()

    assert 'secret=os.getenv("WEBHOOK_PAYMENT_SECRET")' in content
    assert 'request.headers.get("x-webhook-secret")' not in content
    assert 'request.headers.get("X-Webhook-Secret")' not in content


def test_the_signature_header_is_named_once(tmp_path: Path) -> None:
    """One constant and one lookup, so a casing bug cannot come back twice."""
    content = _generate(tmp_path, "payment").read_text()

    assert 'SIGNATURE_HEADER = "x-webhook-signature"' in content
    assert "signature = _header(headers, SIGNATURE_HEADER)" in content
    assert 'headers.get("X-Webhook-Signature")' not in content


def test_generated_module_is_lint_and_format_clean_on_its_own(tmp_path: Path) -> None:
    path = _generate(tmp_path, "payment")

    check = _ruff(path, "check")
    assert check.returncode == 0, f"ruff check:\n{check.stdout}"

    formatted = _ruff(path, "format", "--check")
    assert formatted.returncode == 0, f"ruff format:\n{formatted.stdout}"


def test_a_typed_payload_builds_a_working_model(tmp_path: Path) -> None:
    """A non-builtin field token must still yield a constructible model.

    Rendering ``decimal`` verbatim made the model unresolvable, and Pydantic
    raised at request time — the failure was a 500-shaped error response, not
    an import error, so nothing short of executing a request catches it.
    """
    module = _load(
        _generate(tmp_path, "payment", fields_str=TYPED_PAYLOAD),
        "generated_payment_typed",
    )
    body = (
        b'{"event_type": "payment.created", "order_id":'
        b' "8b1c2e5e-3f4a-4a1b-9c2d-0e1f2a3b4c5d", "amount": 10.5,'
        b' "seen_at": "2026-09-23T00:00:00Z", "payload": {"k": 1}}'
    )

    async def run() -> dict[str, object]:
        webhook = module.PaymentWebhook(secret="s3cret", verify_signature=True)
        return await webhook.handle_request(
            body, {"x-webhook-signature": _sign("s3cret", body)}
        )

    assert asyncio.run(run())["status"] == "ignored"
    content = (tmp_path / "src" / "webhooks" / "payment_webhook.py").read_text()
    assert "order_id: UUID" in content
    assert "payload: dict[str, Any]" in content
    # The dispatch key is present even though the caller only asked for
    # business fields: without it every request failed at ``.event_type``.
    assert "event_type: str" in content
