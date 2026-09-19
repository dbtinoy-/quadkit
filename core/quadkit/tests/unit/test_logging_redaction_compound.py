"""Additional redaction tests: compound/camelCase secret keys.

Extends ``test_logging_redaction.py`` — the matcher must treat any key
containing a secret-bearing token (token/secret/password/key/dsn/auth/
credential) as sensitive, so compound names like ``auth_token``,
``setup_token``, ``dsn`` and camelCase ``apiKey`` are masked, while benign
keys that merely contain the letters (monkey, token_count, keyboard) pass.
"""

from __future__ import annotations

import pytest

from quadkit.logging.redaction import DefaultRedactor


@pytest.mark.parametrize(
    "key",
    [
        "auth_token",
        "setup_token",
        "secret_key",
        "session_secret",
        "dsn",
        "server_key",
        "apns_auth_key",
        "vapid_private_key",
        "apiKey",
        "clientSecret",
        "smtp_password",
    ],
)
def test_compound_and_camel_keys_masked(key: str) -> None:
    out = DefaultRedactor().redact_dict({key: "leak"})
    assert out[key] == "<redacted>", key


@pytest.mark.parametrize(
    "key", ["monkey", "keyboard", "donkey", "token_count", "credentials_file"]
)
def test_benign_similar_keys_not_masked(key: str) -> None:
    out = DefaultRedactor().redact_dict({key: "value"})
    assert out[key] == "value"


def test_nested_compound_key_masked() -> None:
    out = DefaultRedactor().redact_dict({"smtp": {"auth_token": "leak"}})
    assert out["smtp"]["auth_token"] == "<redacted>"
