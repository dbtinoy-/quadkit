"""LDAP connection pooling and directory search seam for :class:`LDAPManager`.

This module is an internal implementation detail; import
:class:`~quadkit.auth.authn.ldap.LDAPManager` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    import ldap3
    from ldap3 import ALL, BASE, SUBTREE, Connection, Server
    from ldap3.core.exceptions import LDAPException

    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    ldap3 = None
    # ldap3 scope constants referenced in ``get_info=`` / ``search_scope=``
    ALL = BASE = SUBTREE = None

    class LDAPException(Exception):  # type: ignore[no-redef]  # noqa: N818
        """Placeholder exception used when ``ldap3`` is not installed."""

    # Define placeholder types for when LDAP is not available
    Connection = Any
    Server = Any

if TYPE_CHECKING:
    from quadkit.auth.authn.ldap import LDAPProvider


class _LDAPDirectoryMixin:
    """Mixin providing LDAP connection pooling and directory searches.

    All public attributes referenced here are initialised by
    ``LDAPManager.__init__``.
    """

    # ── Attributes set by LDAPManager.__init__ ───────────────────────────────
    _connection_pool: dict[str, list[Connection]]

    async def _get_user_dn(self, provider: LDAPProvider, username: str) -> str | None:
        """Get the DN for a username by searching LDAP.

        Args:
            provider: LDAP provider configuration
            username: Username to search for

        Returns:
            User DN or None if not found
        """
        conn = await self._get_connection(provider)
        try:
            search_filter = provider.user_search_filter.format(username=username)

            conn.search(
                search_base=provider.user_search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[provider.user_dn_attribute],
            )

            if conn.entries:
                entry = conn.entries[0]
                value = getattr(entry, provider.user_dn_attribute).value
                # Normalize to str when possible
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="ignore")
                if isinstance(value, str):
                    return value
                if value is not None:
                    return str(value)

            return None

        finally:
            self._return_connection(provider, conn)

    async def _get_group_dn(
        self,
        provider: LDAPProvider,
        group_name: str,
    ) -> str | None:
        """Get the DN for a group by searching LDAP.

        Args:
            provider: LDAP provider configuration
            group_name: Group name to search for

        Returns:
            Group DN or None if not found
        """
        if not provider.group_search_base or not provider.group_search_filter:
            return None

        conn = await self._get_connection(provider)
        try:
            search_filter = provider.group_search_filter.format(group=group_name)

            conn.search(
                search_base=provider.group_search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["distinguishedName"],
            )

            if conn.entries:
                entry = conn.entries[0]
                value = entry.distinguishedName.value
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="ignore")
                if isinstance(value, str):
                    return value
                if value is not None:
                    return str(value)

            return None

        finally:
            self._return_connection(provider, conn)

    async def _get_user_attributes(
        self,
        provider: LDAPProvider,
        user_dn: str,
    ) -> dict[str, Any]:
        """Get user attributes from LDAP.

        Args:
            provider: LDAP provider configuration
            user_dn: User DN to get attributes for

        Returns:
            Dictionary of user attributes
        """
        conn = await self._get_connection(provider)
        try:
            # Common attributes to retrieve
            attributes = [
                "objectGUID",
                "objectSid",
                "sAMAccountName",
                "userPrincipalName",
                "mail",
                "displayName",
                "givenName",
                "sn",
                "cn",
                "distinguishedName",
                "memberOf",
                "userAccountControl",
                "whenCreated",
                "whenChanged",
            ]

            conn.search(
                search_base=user_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=attributes,
            )

            if conn.entries:
                entry = conn.entries[0]
                user_info = {}

                for attr in attributes:
                    if hasattr(entry, attr):
                        value = getattr(entry, attr).value
                        # Convert bytes to string for certain attributes
                        if isinstance(value, bytes):
                            if attr in ["objectGUID", "objectSid"]:
                                # Keep as bytes for unique identifiers
                                user_info[attr] = value.hex()
                            else:
                                user_info[attr] = value.decode("utf-8", errors="ignore")
                        else:
                            user_info[attr] = value

                return user_info

            return {}

        finally:
            self._return_connection(provider, conn)

    async def _get_connection(self, provider: LDAPProvider) -> Connection:
        """Get a connection from the pool or create a new one.

        Args:
            provider: LDAP provider configuration

        Returns:
            LDAP connection
        """
        provider_name = provider.name

        # Initialize pool if needed
        if provider_name not in self._connection_pool:
            self._connection_pool[provider_name] = []

        # Try to get existing connection
        if self._connection_pool[provider_name]:
            conn = self._connection_pool[provider_name].pop()
            if conn.bound:
                return conn

        # Create new connection
        server = Server(provider.server_url, get_info=ALL)

        return Connection(
            server,
            user=provider.bind_dn,
            password=(
                provider.bind_password.get_secret_value()
                if provider.bind_password is not None
                else None
            ),
            auto_bind=True,
            read_only=True,
            receive_timeout=provider.timeout,
        )

    def _return_connection(self, provider: LDAPProvider, conn: Connection) -> None:
        """Return a connection to the pool.

        Args:
            provider: LDAP provider configuration
            conn: Connection to return
        """
        provider_name = provider.name

        if provider_name not in self._connection_pool:
            self._connection_pool[provider_name] = []

        # Only return if pool not full and connection is still valid
        if (
            len(self._connection_pool[provider_name]) < provider.max_connections
            and conn.bound
        ):
            self._connection_pool[provider_name].append(conn)
        else:
            conn.unbind()


__all__ = ["ALL", "BASE", "LDAP_AVAILABLE", "LDAPException", "_LDAPDirectoryMixin"]
