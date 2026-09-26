"""JWT token binding configuration and helpers.

Provides :class:`TokenBindingConfig` and the :func:`compute_binding_hash` /
:func:`verify_binding` helpers consumed by :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.

Token binding is **opt-in** and backward-compatible: tokens issued without a
``bind`` claim continue to pass verification so that callers can enable
binding incrementally without invalidating existing sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass
class TokenBindingConfig:
    """Configuration for opt-in JWT client binding.

    When configured, a SHA-256 hash of the active binding factors is embedded
    in the ``bind`` claim of every issued token.  On verification the hash is
    re-computed from the current request context and compared against the
    stored value.  A mismatch rejects the token, preventing reuse of a stolen
    token from a different IP or device.

    Attributes:
        bind_to_ip: Include the client IP address in the binding hash.
        bind_to_fingerprint: Include an arbitrary client fingerprint string
            (e.g., the value of ``X-Client-Fingerprint``) in the hash.
        fingerprint_header: HTTP header name carrying the fingerprint value.
            Informational only — callers must extract the header value and
            pass it via the ``binding_context`` dict.
    """

    bind_to_ip: bool = False
    bind_to_fingerprint: bool = False
    fingerprint_header: str = "X-Client-Fingerprint"


def compute_binding_hash(
    config: TokenBindingConfig,
    ctx: dict[str, str],
) -> str | None:
    """Compute a binding hash from the provided context.

    Args:
        config: Active binding configuration.
        ctx: Request context mapping.  Recognised keys are ``ip`` and
            ``fingerprint``.

    Returns:
        Hex-encoded SHA-256 digest of the active binding factors joined by
        ``|``, or ``None`` if no binding factors are active in *config* or
        *ctx* supplies no values for them.
    """
    parts: list[str] = []
    if config.bind_to_ip and (ip := ctx.get("ip")):
        parts.append(f"ip:{ip}")
    if config.bind_to_fingerprint and (fp := ctx.get("fingerprint")):
        parts.append(f"fp:{fp}")
    if not parts:
        return None
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def verify_binding(
    config: TokenBindingConfig,
    claims: dict[str, object],
    ctx: dict[str, str],
) -> bool:
    """Verify that the token binding hash matches the current context.

    Tokens that carry no ``bind`` claim pass unconditionally so that
    pre-binding tokens remain valid after binding is enabled.

    Args:
        config: Active binding configuration.
        claims: Decoded JWT payload.
        ctx: Current request context (same keys as :func:`compute_binding_hash`).

    Returns:
        ``True`` when binding is satisfied or no binding was stored.
        ``False`` when the stored hash does not match the re-computed value.
    """
    stored = claims.get("bind")
    if stored is None:
        # Issued before binding was configured — backward-compatible pass.
        return True
    expected = compute_binding_hash(config, ctx)
    if expected is None:
        # Config has no active binding factors — skip.
        return True
    return stored == expected


__all__ = ["TokenBindingConfig", "compute_binding_hash", "verify_binding"]
