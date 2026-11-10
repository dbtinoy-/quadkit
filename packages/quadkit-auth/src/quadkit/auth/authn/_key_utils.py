"""JWT key normalization utilities."""

from __future__ import annotations

from typing import Any

from quadkit.validation import SecretStr


def normalize_jwt_keys(
    keys: dict[str, Any],
) -> dict[str, SecretStr | dict[str, SecretStr]]:
    """Coerce all JWT key material to :class:`~quadkit.validation.SecretStr`.

    Rejects plain :class:`str` values with a :exc:`TypeError` so that callers
    cannot accidentally embed secrets in tracebacks or log output.

    Args:
        keys: Raw key mapping to normalize.

    Returns:
        Normalized mapping with all string values wrapped in
        :class:`~quadkit.validation.SecretStr`.

    Raises:
        TypeError: If any key material is a plain ``str`` or an unsupported type.
    """
    result: dict[str, SecretStr | dict[str, SecretStr]] = {}
    for k, v in keys.items():
        if isinstance(v, dict):
            inner: dict[str, SecretStr] = {}
            for sk, sv in v.items():
                if isinstance(sv, str):
                    raise TypeError(
                        f"JWTTokenManager: key '{k}.{sk}' must be SecretStr, got str. "
                        "Pass SecretStr('your-secret') instead of plain strings."
                    )
                if not isinstance(sv, SecretStr):
                    raise TypeError(
                        f"JWTTokenManager: key '{k}.{sk}' must be SecretStr, got {type(sv).__name__}."
                    )
                inner[sk] = sv
            result[k] = inner
        elif isinstance(v, str):
            raise TypeError(
                f"JWTTokenManager: key '{k}' must be SecretStr, got str. "
                "Pass SecretStr('your-secret') instead of plain strings."
            )
        elif not isinstance(v, SecretStr):
            raise TypeError(
                f"JWTTokenManager: key '{k}' must be SecretStr, got {type(v).__name__}."
            )
        result[k] = v
    return result


def rsa_key_material(private_pem: str) -> dict[str, SecretStr]:
    """Pair an RSA signing key with its public verification key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    private = serialization.load_pem_private_key(private_pem.encode(), password=None)
    if not isinstance(private, RSAPrivateKey):
        raise TypeError("JWT RSA algorithm requires an RSA private key")
    public = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return {"private": SecretStr(private_pem), "public": SecretStr(public)}


__all__ = ["normalize_jwt_keys", "rsa_key_material"]
