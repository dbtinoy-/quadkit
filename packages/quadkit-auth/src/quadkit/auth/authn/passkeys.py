"""WebAuthn / Passkeys helper (server-side operations).

The framework owns the challenge store and authentication verification.  The
authentication path accepts both the legacy QuadKit raw-challenge assertion
used by existing clients and a browser-native WebAuthn assertion containing
``clientDataJSON`` and ``authenticatorData``.  Browser assertions validate the
client-data type/challenge/origin, RP ID hash, user-present flag, signature
input, and authenticator sign counter before the pending ceremony is consumed.

Registration accepts the legacy framework PEM contract for controlled
non-browser clients and validates browser-native ``attestationObject`` /
``clientDataJSON`` responses through ``passkey_attestation``.  ``none`` and
packed self-attestation are verified locally; certificate-backed formats fail
closed until an operator-configured trust store is available.

Storage format (kept on User.profile['passkeys']):
- credential_id: str
- public_key_pem: str
- name: str
- created_at: ISO timestamp
- sign_count: int  (monotonically increasing per-authenticator counter)

Temporary state for in-progress registration/authentication is kept in a
short-lived in-memory map (sufficient for single-process dev/staging and for
unit tests). In production you should replace this with a secure cache (Redis)
if multi-worker deployments are used.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.auth.storage.token_store import UserStoreProtocol
    from quadkit.contracts.infra.cache import CacheBackendProtocol

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from quadkit import serialization as json
from quadkit.auth.authn.passkey_attestation import (
    AttestationError,
    parse_registration_attestation,
)
from quadkit.di.decorators import inject


class _PendingStore:
    """Abstract pending store with optional async cache backend.

    If a `cache` object is provided (e.g., provider.cache_service) we use its
    async `set`, `get`, and `delete` methods. Otherwise fall back to an in-memory
    dict with TTL semantics suitable for tests and single-process deployments.
    """

    def __init__(
        self,
        cache: CacheBackendProtocol | None = None,
    ) -> None:
        self.cache = cache
        self._store: dict[str, tuple[dict, float]] = {}

    async def set(self, key: str, value: dict, ttl: int = 300) -> None:
        if self.cache:
            # Cache backends own their value serialization.  Keep the
            # payload as a text JSON document so both raw Redis/Memcached
            # adapters and structured QuadKit cache backends receive a
            # portable value; passing ``quadkit.serialization.dumps`` bytes
            # would make the memory backend store a string repr like
            # ``b'{...}'`` and break the subsequent decode.
            payload = json.dumps_str(value)
            await self.cache.set(key, payload, ttl)
        else:
            now = ambient_clock.monotonic()
            self._store[key] = (value, now + ttl)

    async def get(self, key: str) -> dict | None:
        if self.cache:
            get_result = await self.cache.get(key)
            raw = (
                get_result.unwrap()
                if hasattr(get_result, "is_ok") and get_result.is_ok()
                else get_result
                if get_result
                else None
            )
            if raw is None:
                return None
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return json.loads(raw) if isinstance(raw, str) else raw  # type: ignore[return-value]
        v = self._store.get(key)
        if not v:
            return None
        value, expiry = v
        now = ambient_clock.monotonic()
        if now > expiry:
            del self._store[key]
            return None
        return value

    async def delete(self, key: str) -> None:
        if self.cache:
            await self.cache.delete(key)
        elif key in self._store:
            del self._store[key]


@inject
class PasskeyService:
    """Manage passkey registration and authentication flows.

    Notes:
    - start_registration / finish_registration: client obtains a challenge and
      then submits credential information (credential_id and public_key_pem)
      along with the challenge to finish registration.
    - start_authentication / finish_authentication: server issues a challenge
      which must be signed by the client's private key; the server verifies
      the signature using the stored public key.

    The service will use the provider's `cache_service` as the backing store for
    pending registration/authentication challenges when available. This ensures
    compatibility with multi-worker deployments (use Redis or similar).
    """

    def __init__(
        self,
        user_store: UserStoreProtocol,
        cache_service: CacheBackendProtocol | None = None,
        *,
        rp_id: str | None = None,
        allowed_origins: set[str] | None = None,
        require_user_verification: bool = True,
        allow_insecure_origins: bool = False,
    ) -> None:
        self.user_store = user_store
        self.rp_id = str(rp_id or "").strip().lower().rstrip(".") or None
        self.allowed_origins: frozenset[str] = (
            frozenset(allowed_origins) if allowed_origins else frozenset()
        )
        # New-api requires UV for enrollment.  Legacy PEM/raw challenge
        # callers do not carry authenticator flags and therefore retain their
        # compatibility path; native browser ceremonies use this policy.
        self.require_user_verification = bool(require_user_verification)
        self.allow_insecure_origins = bool(allow_insecure_origins)
        self._pending_registrations = _PendingStore(cache_service)
        self._pending_authn = _PendingStore(cache_service)

    def _gen_challenge(self) -> str:
        # Return URL-safe base64 challenge
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")

    def _validate_origin(self, origin: str | None) -> bool:
        """Return False if origin is required but invalid or missing.

        Returns True (allow) when:
        - No ``allowed_origins`` are configured (origin enforcement disabled).
        - ``origin`` is provided and contained in ``allowed_origins``.

        Returns False (reject) when:
        - ``allowed_origins`` are configured and ``origin`` is None or missing.
        - ``origin`` is not in ``allowed_origins``.
        """
        if not self.allowed_origins:
            # Origin enforcement not configured — skip silently.
            return True
        if origin is None:
            # Origins required but not provided.
            return False
        return origin in self.allowed_origins

    def _origin_is_acceptable(self, origin: str | None) -> bool:
        """Apply the HTTPS/local-development origin policy before a ceremony."""
        if not origin:
            return True
        parsed = urlparse(origin)
        if (
            parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return False
        if parsed.scheme == "https":
            return True
        return bool(
            parsed.scheme == "http"
            and (
                self.allow_insecure_origins
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        )

    async def start_registration(
        self,
        user_id: str,
        name: str | None = None,
        *,
        origin: str | None = None,
        rp_id: str | None = None,
    ) -> tuple[str, str]:
        """Start registration: return (registration_id, challenge).

        The server-selected origin/RP binding is stored with the opaque
        ceremony so a later browser response cannot silently switch relying
        parties during a configuration change.
        """
        if not user_id:
            raise ValueError("User id is required")
        if origin is not None and (
            not self._validate_origin(origin) or not self._origin_is_acceptable(origin)
        ):
            raise ValueError("Passkey origin is not allowed")
        selected_rp_id = (
            str(rp_id or self.rp_id or "").strip().lower().rstrip(".") or None
        )
        if selected_rp_id is None and origin:
            selected_rp_id = urlparse(origin).hostname
        reg_id = secrets.token_hex(16)
        challenge = self._gen_challenge()
        data = {
            "user_id": user_id,
            "challenge": challenge,
            "name": name or "",
            "origin": origin,
            "rp_id": selected_rp_id,
            "created_at": int(ambient_clock.timestamp()),
        }
        await self._pending_registrations.set(reg_id, data, ttl=300)
        return reg_id, challenge

    async def finish_registration(
        self,
        registration_id: str,
        credential_id: str | None = None,
        public_key_pem: str | None = None,
        actor_user_id: str | None = None,
        *,
        origin: str | None = None,
        attestation_object: bytes | None = None,
        client_data_json: bytes | None = None,
    ) -> bool:
        """Finish registration and persist a verified credential.

        Browser clients submit ``attestation_object`` and ``client_data_json``;
        the parser validates the signed challenge, origin, RP ID hash, user
        presence/verification flags, COSE key, and supported attestation
        statement before this method writes anything.  The older PEM contract
        remains available for controlled non-browser clients and is still
        restricted to canonical P-256 public keys.

        The opaque registration ceremony is consumed before verification, so a
        malformed response cannot be retried indefinitely with the same
        challenge.  ``actor_user_id`` always remains bound to the server-side
        ceremony subject.
        """
        pending = await self._pending_registrations.get(registration_id)
        if not pending:
            return False
        await self._pending_registrations.delete(registration_id)

        pending_origin = pending.get("origin") or origin
        if attestation_object is None and client_data_json is None:
            if not self._validate_origin(pending_origin):
                return False
        elif attestation_object is None or client_data_json is None:
            return False

        user_id = str(pending.get("user_id") or "")
        if actor_user_id is not None and actor_user_id != user_id:
            return False
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return False

        initial_sign_count = 0
        metadata: dict[str, Any] = {
            "aaguid": "",
            "attestation_format": "legacy",
            "user_present": True,
            "user_verified": False,
            "backup_eligible": False,
            "backup_state": False,
        }
        if attestation_object is not None and client_data_json is not None:
            try:
                parsed = parse_registration_attestation(
                    attestation_object,
                    client_data_json,
                    expected_challenge=str(pending.get("challenge") or ""),
                    expected_rp_id=str(pending.get("rp_id") or self.rp_id or "")
                    or None,
                    origin=pending_origin,
                    allowed_origins=self.allowed_origins,
                    require_user_verification=self.require_user_verification,
                    allow_insecure_origins=self.allow_insecure_origins,
                    supplied_credential_id=credential_id,
                )
            except AttestationError:
                return False
            credential_id = parsed.credential_id
            public_key_pem = parsed.public_key_pem
            initial_sign_count = parsed.sign_count
            metadata = {
                "aaguid": parsed.aaguid,
                "attestation_format": parsed.attestation_format,
                "user_present": parsed.user_present,
                "user_verified": parsed.user_verified,
                "backup_eligible": parsed.backup_eligible,
                "backup_state": parsed.backup_state,
            }
        if not credential_id or not public_key_pem:
            return False

        # Normalize the legacy PEM input too; browser-derived keys arrive here
        # already canonicalized by the attestation parser.
        try:
            key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        except (ValueError, TypeError):
            return False
        from cryptography.hazmat.primitives.asymmetric.ec import (
            SECP256R1,
            EllipticCurvePublicKey,
        )

        if (
            not isinstance(key, EllipticCurvePublicKey)
            or key.curve.name != SECP256R1().name
        ):
            return False
        try:
            pub_pem = key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
        except (ValueError, TypeError):
            return False

        profile = dict(user.profile)
        passkeys = list(profile.get("passkeys") or [])
        if any(p.get("credential_id") == credential_id for p in passkeys):
            return False
        passkeys.append(
            {
                "credential_id": credential_id,
                "public_key_pem": pub_pem,
                "name": pending.get("name") or "",
                "created_at": ambient_clock.now().isoformat(),
                "sign_count": initial_sign_count,
                **metadata,
            },
        )
        profile["passkeys"] = passkeys

        import dataclasses

        if dataclasses.is_dataclass(cast("object", user)):
            updated = dataclasses.replace(user, profile=profile)
            await self.user_store.update_user(updated)
        else:
            user.profile = profile
            await self.user_store.update_user(user)
        return True

    async def delete_passkey(
        self, user_id: str, credential_id: str | None = None
    ) -> bool:
        """Delete one passkey, or all passkeys when no id is supplied.

        The operation is deliberately part of the framework service so
        callers do not mutate security profile documents outside the
        QuadKit Auth boundary.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return False
        passkeys = list(user.profile.get("passkeys") or [])
        if credential_id is None:
            changed = bool(passkeys)
            remaining: list[dict[str, Any]] = []
        else:
            remaining = [
                item for item in passkeys if item.get("credential_id") != credential_id
            ]
            changed = len(remaining) != len(passkeys)
        if not changed:
            return False
        profile = dict(user.profile)
        profile["passkeys"] = remaining
        import dataclasses

        await self.user_store.update_user(dataclasses.replace(user, profile=profile))
        return True

    async def list_passkeys(self, user_id: str) -> list[dict[str, Any]]:
        """Return non-secret passkey metadata for a user."""
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return []
        return [
            {
                "credential_id": item.get("credential_id", ""),
                "name": item.get("name", ""),
                "created_at": item.get("created_at"),
                "sign_count": item.get("sign_count", 0),
                "aaguid": item.get("aaguid", ""),
                "attestation_format": item.get("attestation_format", "legacy"),
                "user_verified": bool(item.get("user_verified", False)),
            }
            for item in list(user.profile.get("passkeys") or [])
        ]

    async def start_authentication(self, user_id: str) -> tuple[str, str, list[str]]:
        """Start authn: return (auth_id, challenge, allowed_credential_ids)."""
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        passkeys = list(user.profile.get("passkeys") or [])
        credential_ids = [pk["credential_id"] for pk in passkeys]

        auth_id = secrets.token_hex(16)
        challenge = self._gen_challenge()
        data = {
            "user_id": user_id,
            "challenge": challenge,
            "created_at": int(ambient_clock.timestamp()),
        }
        await self._pending_authn.set(auth_id, data, ttl=300)
        return auth_id, challenge, credential_ids

    async def authentication_user_id(self, auth_id: str) -> str | None:
        """Return the user bound to a pending authentication ceremony.

        This read-only helper lets an application issue a session for the
        server-owned challenge subject rather than trusting a user id supplied
        alongside the assertion.  The pending ceremony remains available for
        :meth:`finish_authentication`, which consumes it exactly once.
        """
        pending = await self._pending_authn.get(str(auth_id or ""))
        if not pending:
            return None
        user_id = pending.get("user_id")
        return str(user_id) if user_id else None

    async def finish_authentication(
        self,
        auth_id: str,
        credential_id: str,
        signature: bytes,
        *,
        origin: str | None = None,
        new_sign_count: int | None = None,
        authenticator_data: bytes | None = None,
        client_data_json: bytes | None = None,
    ) -> bool:
        """Finish authentication with a raw or browser-native assertion.

        When ``authenticator_data`` and ``client_data_json`` are supplied,
        the method validates the WebAuthn ``clientDataJSON`` type/challenge/
        origin, RP ID hash, user-present flag, and authenticator counter, then
        verifies the signature over ``authenticatorData`` concatenated with
        ``SHA-256(clientDataJSON)``.  Omitting both fields preserves the
        framework's legacy raw-challenge contract for existing clients.
        """
        pending = await self._pending_authn.get(auth_id)
        if not pending:
            return False
        # Consume the opaque ceremony before verification.  A failed assertion
        # cannot be retried indefinitely with the same server challenge.
        await self._pending_authn.delete(auth_id)

        full_assertion = authenticator_data is not None or client_data_json is not None
        effective_origin = origin
        effective_sign_count = new_sign_count
        if full_assertion:
            if authenticator_data is None or client_data_json is None:
                return False
            try:
                client_data = json.loads(client_data_json)
            except (TypeError, ValueError):
                return False
            if not isinstance(client_data, dict):
                return False
            if client_data.get("type") != "webauthn.get":
                return False
            client_origin = str(client_data.get("origin") or "")
            effective_origin = effective_origin or client_origin or None
            if origin and client_origin != origin:
                return False
            expected_challenge = str(client_data.get("challenge") or "")
            pending_challenge = str(pending.get("challenge") or "")

            def normalize_b64(value: str) -> str:
                return value.replace("+", "-").replace("/", "_").rstrip("=")

            if not hmac.compare_digest(
                normalize_b64(expected_challenge), normalize_b64(pending_challenge)
            ):
                return False
            if len(authenticator_data) < 37:
                return False
            flags = authenticator_data[32]
            # User Present is required for a normal assertion.  User
            # Verification remains authenticator-policy dependent.
            if not flags & 0x01:
                return False
            expected_rp_id = self.rp_id
            if expected_rp_id is None and effective_origin:
                expected_rp_id = urlparse(effective_origin).hostname
            if expected_rp_id:
                expected_rp_hash = hashlib.sha256(
                    expected_rp_id.encode("utf-8")
                ).digest()
                if not hmac.compare_digest(authenticator_data[:32], expected_rp_hash):
                    return False
            effective_sign_count = int.from_bytes(authenticator_data[33:37], "big")
        if not self._validate_origin(effective_origin):
            return False

        user_id = pending["user_id"]
        challenge = str(pending.get("challenge") or "").encode("utf-8")

        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return False

        passkeys = list(user.profile.get("passkeys") or [])
        pk = next(
            (p for p in passkeys if p.get("credential_id") == credential_id), None
        )
        if not pk:
            return False

        # A zero WebAuthn counter is allowed when both the stored and reported
        # counters are zero (some authenticators do not expose counters).  The
        # legacy raw contract retains its stricter monotonic behavior.
        try:
            stored_count = int(pk.get("sign_count", 0) or 0)
        except (TypeError, ValueError):
            return False
        if effective_sign_count is not None:
            if full_assertion and stored_count == 0 and effective_sign_count == 0:
                pass
            elif effective_sign_count <= stored_count:
                return False

        public_key_pem = str(pk.get("public_key_pem") or "").encode("utf-8")
        signed_message = challenge
        if (
            full_assertion
            and authenticator_data is not None
            and client_data_json is not None
        ):
            signed_message = (
                authenticator_data + hashlib.sha256(client_data_json).digest()
            )
        try:
            public_key = serialization.load_pem_public_key(public_key_pem)
            public_key.verify(signature, signed_message, ec.ECDSA(hashes.SHA256()))  # type: ignore[union-attr, call-arg, arg-type]
        except (ValueError, TypeError):
            return False

        # Persist a newly observed counter on success.
        if effective_sign_count is not None and (
            not full_assertion or effective_sign_count > stored_count
        ):
            pk["sign_count"] = effective_sign_count
            profile = dict(user.profile)
            profile["passkeys"] = passkeys

            import dataclasses

            if dataclasses.is_dataclass(cast("object", user)):
                updated = dataclasses.replace(user, profile=profile)
                await self.user_store.update_user(updated)
            else:
                user.profile = profile
                await self.user_store.update_user(user)

        return True


__all__ = ["PasskeyService"]
