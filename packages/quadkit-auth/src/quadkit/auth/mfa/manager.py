"""MFA Manager — consolidated TOTP and backup-code management.

Stores MFA state in the user's ``profile['mfa']`` dict so no separate
MFA table is required.  Profile keys:

- ``enabled``: bool — whether TOTP is currently active
- ``secret``: base32-encoded TOTP secret
- ``backup_codes``: list of SHA-256 hex digests of the one-time codes
"""

from __future__ import annotations

import dataclasses
import hashlib
import secrets
from typing import TYPE_CHECKING, Any

from quadkit.auth.authn.mfa import (
    generate_backup_codes,
    generate_totp_secret,
    get_provisioning_uri,
    hash_backup_codes,
    verify_totp,
)
from quadkit.auth.models.mfa import UserMFA
from quadkit.di.decorators import inject
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import MFAConfig
    from quadkit.auth.storage.token_store import UserStoreProtocol

logger = get_logger(__name__)


@inject
class MFAManager:
    """Manages Multi-Factor Authentication (TOTP + backup codes) for users.

    MFA state is stored in the user profile so no dedicated MFA table is
    needed.  Injected via the DI container; the resolved ``UserStoreProtocol`` is
    used for all persistence.

    Args:
        user_store: The user store used to read and persist user profiles.
        config: Optional MFA configuration.  When ``None``, defaults are used.
    """

    def __init__(
        self,
        user_store: UserStoreProtocol,
        config: MFAConfig | None = None,
    ) -> None:
        self.user_store = user_store
        from quadkit.auth.config import MFAConfig as _MFAConfig

        self.config = config or _MFAConfig()
        # Enrollment is deliberately staged: setup returns a secret, but the
        # profile is not marked enabled until the authenticator proves control
        # of that secret.  The pending map is an application-level flow store;
        # deployments that need cross-worker enrollment should wrap the manager
        # with a shared UserStore/cache implementation.
        self._pending_setups: dict[str, dict[str, Any]] = {}

    def _prune_pending_setups(self, now: int | None = None) -> None:
        """Remove expired staged enrollment records."""
        from quadkit.primitives import clock as ambient_clock

        current = int(now if now is not None else ambient_clock.timestamp())
        expired = [
            token
            for token, payload in self._pending_setups.items()
            if int(payload.get("expires_at", 0)) <= current
        ]
        for token in expired:
            self._pending_setups.pop(token, None)

    async def begin_totp_setup(
        self,
        user_id: str,
        issuer: str | None = None,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """Start a staged TOTP enrollment without enabling MFA.

        The returned ``setup_token`` is single-use and short-lived.  The
        caller must pass it, together with a code from the authenticator, to
        :meth:`complete_totp_setup`.  Plain backup codes are returned once and
        are only persisted as SHA-256 digests after successful verification.
        """
        from quadkit.primitives import clock as ambient_clock

        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if issuer is None:
            issuer = self.config.backup.issuer

        self._prune_pending_setups()
        secret = generate_totp_secret()
        account_name = user.name or user.email or user.user_id
        provisioning_uri = get_provisioning_uri(secret, account_name, issuer)
        backup_codes = generate_backup_codes(
            count=self.config.backup.count,
            length=self.config.backup.length,
        )
        setup_token = secrets.token_urlsafe(32)
        expires_at = int(ambient_clock.timestamp()) + max(30, int(ttl_seconds))
        self._pending_setups[setup_token] = {
            "user_id": user_id,
            "secret": secret,
            "backup_codes": backup_codes,
            "backup_hashes": hash_backup_codes(backup_codes),
            "expires_at": expires_at,
        }
        return {
            "setup_token": setup_token,
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
            "expires_at": expires_at,
        }

    async def complete_totp_setup(
        self,
        user_id: str,
        setup_token: str,
        code: str,
    ) -> list[str] | None:
        """Verify a staged TOTP enrollment and persist the MFA profile.

        Returns the plain backup codes on success, or ``None`` when the flow
        is invalid, expired, belongs to another user, or the TOTP code is
        incorrect.  The setup token is consumed on every completion attempt
        so failed flows cannot be brute-forced indefinitely.
        """
        self._prune_pending_setups()
        pending = self._pending_setups.pop(str(setup_token), None)
        if not pending or pending.get("user_id") != user_id:
            return None
        if not verify_totp(str(pending["secret"]), str(code), window=self.config.totp.valid_window):
            return None

        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return None
        profile = dict(user.profile)
        profile["mfa"] = {
            "enabled": True,
            "secret": pending["secret"],
            "backup_codes": list(pending["backup_hashes"]),
        }
        updated = dataclasses.replace(user, profile=profile)
        await self.user_store.update_user(updated)
        return list(pending["backup_codes"])

    async def enable_totp(
        self,
        user_id: str,
        issuer: str | None = None,
    ) -> tuple[str, str, list[str]]:
        """Enable TOTP for a user and return enrollment credentials.

        A fresh TOTP secret and a set of backup codes are generated and
        stored (only the SHA-256 digests of backup codes are persisted).

        Args:
            user_id: The user to enable TOTP for.
            issuer: The issuer label shown in authenticator apps.
                Defaults to ``config.backup.issuer``.

        Returns:
            A ``(secret, provisioning_uri, plain_backup_codes)`` tuple.
            Show the plain backup codes to the user once — they are not
            stored in plaintext.

        Raises:
            ValueError: If the user does not exist.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if issuer is None:
            issuer = self.config.backup.issuer

        secret = generate_totp_secret()
        account_name = user.name or user.email or user.user_id
        provisioning_uri = get_provisioning_uri(secret, account_name, issuer)
        backup_codes = generate_backup_codes(
            count=self.config.backup.count,
            length=self.config.backup.length,
        )
        backup_hashes = hash_backup_codes(backup_codes)

        profile = dict(user.profile)
        profile_mfa = dict(profile.get("mfa") or {})
        profile_mfa.update(
            {"enabled": True, "secret": secret, "backup_codes": backup_hashes},
        )
        profile["mfa"] = profile_mfa
        updated = dataclasses.replace(user, profile=profile)
        await self.user_store.update_user(updated)

        return secret, provisioning_uri, backup_codes

    async def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify a TOTP or backup code for a user.

        A backup code is consumed on first use — a second attempt with the
        same backup code returns ``False``.

        Args:
            user_id: The user to verify.
            code: A 6-digit TOTP code or a raw backup code string.

        Returns:
            ``True`` if the code is valid, ``False`` otherwise.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return False

        mfa = user.profile.get("mfa") or {}
        if not mfa.get("enabled"):
            return False

        secret = mfa.get("secret")
        if secret and verify_totp(secret, code, window=self.config.totp.valid_window):
            return True

        # Check backup codes (single-use).
        backup_hashes = list(mfa.get("backup_codes") or [])
        code_hash = hashlib.sha256(str(code).encode("utf-8")).hexdigest()
        if code_hash in backup_hashes:
            backup_hashes.remove(code_hash)
            profile = dict(user.profile)
            profile_mfa = dict(profile.get("mfa") or {})
            profile_mfa["backup_codes"] = backup_hashes
            profile["mfa"] = profile_mfa
            updated = dataclasses.replace(user, profile=profile)
            await self.user_store.update_user(updated)
            return True

        return False

    async def regenerate_backup_codes(self, user_id: str) -> list[str] | None:
        """Replace backup codes while preserving the enrolled TOTP secret."""
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return None
        mfa = dict(user.profile.get("mfa") or {})
        if not mfa.get("enabled") or not mfa.get("secret"):
            return None
        backup_codes = generate_backup_codes(
            count=self.config.backup.count,
            length=self.config.backup.length,
        )
        mfa["backup_codes"] = hash_backup_codes(backup_codes)
        profile = dict(user.profile)
        profile["mfa"] = mfa
        await self.user_store.update_user(dataclasses.replace(user, profile=profile))
        return backup_codes

    async def disable_totp(self, user_id: str) -> bool:
        """Disable TOTP for a user.

        Args:
            user_id: The user to disable TOTP for.

        Returns:
            ``True`` if TOTP was disabled, ``False`` if the user does not exist.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return False

        profile = dict(user.profile)
        profile_mfa = dict(profile.get("mfa") or {})
        profile_mfa.update({"enabled": False, "secret": None, "backup_codes": []})
        profile["mfa"] = profile_mfa
        updated = dataclasses.replace(user, profile=profile)
        await self.user_store.update_user(updated)
        return True

    # -- MFAManagerProtocol conformance -----------------------------------
    #
    # `MFAManagerProtocol` (quadkit.contracts.auth) declares a generic
    # enroll/verify/revoke/list_methods/get_mfa surface so callers (notably
    # `AuthProviderProtocol.mfa_manager` consumers such as the `require_mfa`
    # middleware decorator) can work with MFA without knowing which second
    # factor is configured. `MFAManager` only ever implemented the TOTP-
    # specific enable_totp/verify_totp/disable_totp trio, so anything
    # resolving it through the protocol (e.g. `auth_provider.mfa_manager.
    # get_mfa(...)`) crashed with AttributeError. The methods below adapt
    # the existing TOTP implementation onto the protocol shape; "totp" is
    # currently the only supported `method`.

    async def enroll(self, user_id: str, method: str) -> dict[str, Any]:
        """Enroll *user_id* in the given MFA *method* (protocol adapter).

        Args:
            user_id: The user to enroll.
            method: MFA method identifier. Only ``"totp"`` is supported.

        Returns:
            A dict with ``secret``, ``provisioning_uri``, and
            ``backup_codes`` keys (mirrors :meth:`enable_totp`).

        Raises:
            ValueError: If ``method`` is not supported, or the user does
                not exist.
        """
        if method != "totp":
            raise ValueError(f"Unsupported MFA method: {method!r}")

        secret, provisioning_uri, backup_codes = await self.enable_totp(user_id)
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
        }

    async def verify(self, user_id: str, method: str, code: str) -> bool:
        """Verify *code* for *user_id* using the given MFA *method*.

        Args:
            user_id: The user to verify.
            method: MFA method identifier. Only ``"totp"`` is supported.
            code: A 6-digit TOTP code or a raw backup code string.

        Returns:
            ``True`` if the code is valid, ``False`` otherwise (including
            for unsupported methods).
        """
        if method != "totp":
            return False
        return await self.verify_totp(user_id, code)

    async def revoke(self, user_id: str, method: str) -> None:
        """Revoke MFA *method* for *user_id* (protocol adapter).

        Args:
            user_id: The user to revoke MFA for.
            method: MFA method identifier. Only ``"totp"`` is supported.
        """
        if method != "totp":
            return
        await self.disable_totp(user_id)

    async def list_methods(self, user_id: str) -> list[str]:
        """List enabled MFA methods for *user_id*.

        Args:
            user_id: The user to inspect.

        Returns:
            ``["totp"]`` if TOTP is enabled for the user, otherwise ``[]``.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return []

        mfa = user.profile.get("mfa") or {}
        return ["totp"] if mfa.get("enabled") else []

    async def get_mfa(self, user_id: str) -> UserMFA | None:
        """Return the current MFA configuration for *user_id*.

        Args:
            user_id: The user to inspect.

        Returns:
            A :class:`UserMFA` snapshot (``is_enabled=False`` if the user
            exists but has never enrolled in MFA), or ``None`` if the user
            does not exist.
        """
        user = await self.user_store.get_user_by_id(user_id)
        if not user:
            return None

        mfa = user.profile.get("mfa") or {}
        return UserMFA(
            mfa_id=f"mfa-totp-{user_id}",
            user_id=user_id,
            mfa_type="totp",
            secret=mfa.get("secret") or "",
            is_enabled=bool(mfa.get("enabled")),
        )

    def __repr__(self) -> str:
        """Return a string representation of this MFAManager."""
        return f"MFAManager(store={type(self.user_store).__name__})"


__all__ = ["MFAManager"]
