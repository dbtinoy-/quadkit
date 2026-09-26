"""LDAP authentication manager implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quadkit.auth.authn._ldap_directory import (
    ALL,
    BASE,
    LDAP_AVAILABLE,
    Connection,
    LDAPException,
    Server,
    _LDAPDirectoryMixin,
)
from quadkit.auth.exceptions import AuthError
from quadkit.contracts.web import HTTPClientProtocol
from quadkit.logging import get_logger
from quadkit.validation import SecretStr

logger = get_logger(__name__)


@dataclass
class LDAPProvider:
    """LDAP provider configuration."""

    name: str
    server_url: str
    bind_dn: str | None = None
    bind_password: SecretStr | None = None
    user_search_base: str = ""
    user_search_filter: str = "(sAMAccountName={username})"
    user_dn_attribute: str = "distinguishedName"
    group_search_base: str | None = None
    group_search_filter: str | None = None
    require_group_membership: str | None = None
    tls_ca_cert_file: str | None = None
    tls_cert_file: str | None = None
    tls_key_file: str | None = None
    timeout: int = 30
    max_connections: int = 10


class LDAPManager(_LDAPDirectoryMixin):
    """Manager for LDAP/Active Directory authentication operations.

    Handles user authentication, user lookups, and group membership validation
    against LDAP/Active Directory servers.
    """

    def __init__(
        self,
        providers: dict[str, Any],  # dict[str, LDAPProviderConfig] from admin
        http_client: HTTPClientProtocol | None = None,
    ):
        """Initialize LDAP manager.

        Args:
            providers: Dictionary of LDAP provider configurations
            http_client: Optional HTTP client (not used for LDAP, but for consistency)
        """
        if not LDAP_AVAILABLE:
            raise ImportError(
                "LDAP support requires 'ldap3' package. Install with: pip install ldap3",
            )

        self.providers = {}
        for name, config in providers.items():
            # Convert from admin config to auth config
            self.providers[name] = LDAPProvider(
                name=config.name,
                server_url=config.server_url,
                bind_dn=config.bind_dn,
                bind_password=config.bind_password,
                user_search_base=config.user_search_base,
                user_search_filter=config.user_search_filter,
                user_dn_attribute=config.user_dn_attribute,
                group_search_base=config.group_search_base,
                group_search_filter=config.group_search_filter,
                require_group_membership=config.require_group_membership,
                tls_ca_cert_file=config.tls_ca_cert_file,
                tls_cert_file=config.tls_cert_file,
                tls_key_file=config.tls_key_file,
                timeout=config.timeout,
                max_connections=config.max_connections,
            )

        self.http_client = http_client
        self._connection_pool: dict[str, list[Connection]] = {}

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"LDAPManager(providers={list(self.providers)!r})"

    async def authenticate_user(
        self,
        provider_name: str,
        username: str,
        password: str,
    ) -> dict[str, Any] | None:
        """Authenticate a user against LDAP.

        Args:
            provider_name: Name of the LDAP provider
            username: Username to authenticate
            password: Password for authentication

        Returns:
            User information dict if authentication successful, None otherwise

        Raises:
            AuthError: If provider not found or LDAP error occurs
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise AuthError(f"LDAP provider '{provider_name}' not found")

        try:
            # Get user DN first
            user_dn = await self._get_user_dn(provider, username)
            if not user_dn:
                logger.warning("User %s not found in LDAP", username)
                return None

            # Attempt authentication with user DN and password
            if await self._bind_with_credentials(provider, user_dn, password):
                # Get full user info
                user_info = await self._get_user_attributes(provider, user_dn)

                # Check group membership if required
                if (
                    provider.require_group_membership
                    and not await self.check_group_membership(
                        provider_name,
                        username,
                        provider.require_group_membership,
                    )
                ):
                    logger.warning(
                        "User '%s' not member of required group '%s'",
                        username,
                        provider.require_group_membership,
                    )
                    return None

                return user_info
            logger.warning("LDAP authentication failed for user %s", username)
            return None

        except LDAPException as e:
            logger.exception("LDAP error during authentication")
            raise AuthError(f"LDAP authentication failed: {e!s}") from e
        except Exception as e:  # noqa: BLE001 — any auth failure becomes AuthError, never a raw driver exception
            logger.exception("Unexpected error during LDAP authentication")
            raise AuthError(f"LDAP authentication failed: {e!s}") from e

    async def get_user_info(
        self,
        provider_name: str,
        username: str,
    ) -> dict[str, Any] | None:
        """Get user information from LDAP without authentication.

        Args:
            provider_name: Name of the LDAP provider
            username: Username to look up

        Returns:
            User information dict or None if not found
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise AuthError(f"LDAP provider '{provider_name}' not found")

        try:
            user_dn = await self._get_user_dn(provider, username)
            if not user_dn:
                return None

            return await self._get_user_attributes(provider, user_dn)

        except (LDAPException, ConnectionError, OSError):
            logger.exception("Error getting user info")
            return None

    async def check_group_membership(
        self,
        provider_name: str,
        username: str,
        group_name: str,
    ) -> bool:
        """Check if user is a member of the specified group.

        Args:
            provider_name: Name of the LDAP provider
            username: Username to check
            group_name: Group name to check membership for

        Returns:
            True if user is a member of the group
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise AuthError(f"LDAP provider '{provider_name}' not found")

        try:
            # Get user DN
            user_dn = await self._get_user_dn(provider, username)
            if not user_dn:
                return False

            # Get group DN
            group_dn = await self._get_group_dn(provider, group_name)
            if not group_dn:
                return False

            # Check membership
            conn = await self._get_connection(provider)
            try:
                # Search for group and check member attribute
                conn.search(
                    search_base=group_dn,
                    search_filter="(objectClass=*)",
                    search_scope=BASE,
                    attributes=["member", "memberOf"],
                )

                if conn.entries:
                    entry = conn.entries[0]
                    members = entry.member.values if hasattr(entry, "member") else []

                    # Check if user DN is in members
                    if user_dn in members:
                        return True

                    # Also check memberOf on user (for some LDAP implementations)
                    conn.search(
                        search_base=user_dn,
                        search_filter="(objectClass=*)",
                        search_scope=BASE,
                        attributes=["memberOf"],
                    )

                    if conn.entries:
                        user_entry = conn.entries[0]
                        member_of = (
                            user_entry.memberOf.values
                            if hasattr(user_entry, "memberOf")
                            else []
                        )
                        return group_dn in member_of

                return False

            finally:
                self._return_connection(provider, conn)

        except (LDAPException, ConnectionError, OSError):
            logger.exception("Error checking group membership")
            return False

    async def _bind_with_credentials(
        self,
        provider: LDAPProvider,
        user_dn: str,
        password: str,
    ) -> bool:
        """Attempt to bind to LDAP with user credentials.

        Args:
            provider: LDAP provider configuration
            user_dn: User DN to bind with
            password: Password for binding

        Returns:
            True if bind successful
        """
        # Create a new connection for authentication
        server = Server(provider.server_url, get_info=ALL)

        try:
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                read_only=True,
                receive_timeout=provider.timeout,
            )

            # Bind was successful if we get here
            conn.unbind()
            return True

        except LDAPException:
            return False


__all__ = ["LDAPManager", "LDAPProvider"]
