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


__all__ = ["normalize_jwt_keys"]
