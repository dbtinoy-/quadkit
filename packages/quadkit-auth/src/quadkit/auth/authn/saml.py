"""SAML 2.0 authentication flows"""

from __future__ import annotations

import threading
from typing import Any, Protocol

from quadkit.logging import get_logger

try:
    from saml2 import BINDING_HTTP_POST

    # Optional imports that may not be used directly are aliased to avoid unused-import warnings
    from saml2 import BINDING_HTTP_REDIRECT as _BINDING_HTTP_REDIRECT
    from saml2.client import Saml2Client
    from saml2.config import Config as Saml2Config
    from saml2.metadata import (
        entity_descriptor as _entity_descriptor,
    )
    from saml2.response import AuthnResponse
    from saml2.saml import NAMEID_FORMAT_EMAILADDRESS
    import xmlsec as _xmlsec

    HAS_SAML = True
    # Use no-op references to aliased optional imports so static linters don't flag them
    _ = _xmlsec
    _ = _BINDING_HTTP_REDIRECT
    _ = _entity_descriptor
except ImportError:
    HAS_SAML = False
    Saml2Client = None
    Saml2Config = None
    AuthnResponse = None
    # Fallback constant for when SAML libraries are not available
    NAMEID_FORMAT_EMAILADDRESS = (
        "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    )


logger = get_logger(__name__)


# =============================================================================
# SAML Attribute Mapper Registry
# =============================================================================


class SAMLAttributeMapper(Protocol):
    """Protocol for SAML attribute mappers."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        """Map SAML attributes to user info."""
        ...


class EmailAttributeMapper:
    """Maps SAML email attribute to user info."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        if "email" in ava:
            user_info["email"] = ava["email"][0]


class NameAttributeMapper:
    """Maps SAML name attributes to user info."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        if "givenName" in ava and "sn" in ava:
            user_info["name"] = f"{ava['givenName'][0]} {ava['sn'][0]}"
        elif "displayName" in ava:
            user_info["name"] = ava["displayName"][0]


class FirstNameAttributeMapper:
    """Maps SAML firstName/givenName attribute to user info."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        if "givenName" in ava:
            user_info["first_name"] = ava["givenName"][0]
        elif "firstName" in ava:
            user_info["first_name"] = ava["firstName"][0]


class LastNameAttributeMapper:
    """Maps SAML lastName/surname attribute to user info."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        if "sn" in ava:
            user_info["last_name"] = ava["sn"][0]
        elif "surname" in ava:
            user_info["last_name"] = ava["surname"][0]


class GroupsAttributeMapper:
    """Maps SAML groups attribute to user info."""

    def map_attribute(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        if "groups" in ava:
            user_info["groups"] = ava["groups"]
        elif "memberOf" in ava:
            user_info["groups"] = ava["memberOf"]


class SAMLAttributeMapperRegistry:
    """Registry for SAML attribute mappers.

    Allows dynamic registration of custom attribute mappers for
    different SAML identity providers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mappers: list[SAMLAttributeMapper] = []

    @classmethod
    def _default_entries(cls) -> dict[str, SAMLAttributeMapper]:
        """Declare the standard attribute mappers."""
        return {
            "email": EmailAttributeMapper(),
            "name": NameAttributeMapper(),
            "first_name": FirstNameAttributeMapper(),
            "last_name": LastNameAttributeMapper(),
            "groups": GroupsAttributeMapper(),
        }

    @classmethod
    def with_defaults(cls) -> SAMLAttributeMapperRegistry:
        """Create a registry pre-loaded with the standard attribute mappers."""
        instance = cls()
        instance._mappers = list(cls._default_entries().values())
        return instance

    def register_mapper(self, mapper: SAMLAttributeMapper) -> None:
        """Register a custom attribute mapper."""
        with self._lock:
            self._mappers.append(mapper)

    def clear_mappers(self) -> None:
        """Clear all registered mappers."""
        with self._lock:
            self._mappers.clear()

    def get_mappers(self) -> list[SAMLAttributeMapper]:
        """Get all registered mappers."""
        with self._lock:
            return list(self._mappers)

    def map_attributes(
        self,
        ava: dict[str, list[str]],
        user_info: dict[str, Any],
    ) -> None:
        """Map all SAML attributes using registered mappers."""
        with self._lock:
            mappers = list(self._mappers)
        for mapper in mappers:
            mapper.map_attribute(ava, user_info)


# Global registry instance
_saml_attribute_registry = SAMLAttributeMapperRegistry.with_defaults()


class SAMLProvider:
    """SAML identity provider configuration"""

    def __init__(
        self,
        name: str,
        entity_id: str,
        sso_url: str,
        slo_url: str | None = None,
        x509_cert: str | None = None,
        name_id_format: str = NAMEID_FORMAT_EMAILADDRESS,
        want_assertions_signed: bool = True,
        want_response_signed: bool = True,
        want_logout_response_signed: bool = False,
        want_logout_request_signed: bool = False,
    ):
        self.name = name
        self.entity_id = entity_id
        self.sso_url = sso_url
        self.slo_url = slo_url
        self.x509_cert = x509_cert
        self.name_id_format = name_id_format
        self.want_assertions_signed = want_assertions_signed
        self.want_response_signed = want_response_signed
        self.want_logout_response_signed = want_logout_response_signed
        self.want_logout_request_signed = want_logout_request_signed


class SAMLManager:
    """SAML 2.0 authentication manager"""

    def __init__(
        self,
        providers: dict[str, SAMLProvider],
        http_client: Any | None = None,
    ) -> None:
        if not HAS_SAML:
            raise ImportError(
                "SAML libraries (pysaml2, xmlsec) are required for SAML functionality",
            )

        self.providers = providers
        self._http_client = http_client
        self._clients = {}

        # Initialize SAML clients for each provider
        for name, provider in providers.items():
            self._clients[name] = self._create_saml_client(provider)

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"SAMLManager(providers={list(self.providers)!r})"

    def _create_saml_client(self, provider: SAMLProvider) -> Saml2Client:
        """Create SAML client for a provider"""
        config = Saml2Config()

        # Service provider configuration
        config.load(
            {
                "entityid": f"the optional provider-{provider.name}",
                "service": {
                    "sp": {
                        "name": f"Quadkit Admin - {provider.name}",
                        "name_id_format": provider.name_id_format,
                        "want_assertions_signed": provider.want_assertions_signed,
                        "want_response_signed": provider.want_response_signed,
                        "want_logout_response_signed": provider.want_logout_response_signed,
                        "want_logout_request_signed": provider.want_logout_request_signed,
                    },
                },
                "metadata": {
                    "remote": [
                        {
                            "url": provider.entity_id,
                            "cert": provider.x509_cert,
                        },
                    ],
                },
                "key_file": None,  # SP doesn't need signing key for basic auth
                "cert_file": None,
            },
        )

        return Saml2Client(config)

    async def get_login_url(
        self,
        provider_name: str,
        relay_state: str | None = None,
    ) -> str:
        """Get SAML login URL for the given provider"""
        client = self._clients.get(provider_name)
        if not client:
            raise ValueError(f"SAML provider '{provider_name}' not configured")

        _req_id, info = client.prepare_for_authenticate(relay_state=relay_state)

        # Return the login URL
        url = info.get("url")
        if isinstance(url, str):
            return url
        if url is not None:
            return str(url)
        return ""  # Fallback to empty string if not available

    async def process_assertion(
        self,
        provider_name: str,
        saml_response: str,
        relay_state: str | None = None,
    ) -> dict[str, Any]:
        """Process SAML assertion response"""
        client = self._clients.get(provider_name)
        if not client:
            raise ValueError(f"SAML provider '{provider_name}' not configured")

        # Parse and validate the SAML response
        authn_response = client.parse_authn_request_response(
            saml_response,
            BINDING_HTTP_POST,
        )

        if authn_response is None:
            raise ValueError("Invalid SAML response")

        # Extract user information
        user_info = {
            "name_id": authn_response.name_id,
            "name_id_format": authn_response.name_id_format,
            "session_index": authn_response.session_index,
            "attributes": authn_response.ava,  # Attribute value assertions
        }

        # Map common attributes using the registry
        _saml_attribute_registry.map_attributes(authn_response.ava, user_info)

        return user_info

    async def get_logout_url(
        self,
        provider_name: str,
        name_id: str,
        session_index: str | None = None,
    ) -> str | None:
        """Get SAML logout URL for the given provider"""
        client = self._clients.get(provider_name)
        if not client:
            raise ValueError(f"SAML provider '{provider_name}' not configured")

        if not client.slo_service_urls:
            return None

        # Prepare logout request
        _slo_req = client.create_logout_request(
            name_id=name_id,
            session_index=session_index,
        )

        # Get logout URL
        _binding, slo_url = next(iter(client.slo_service_urls.items()))
        if isinstance(slo_url, str):
            return slo_url
        if slo_url is not None:
            return str(slo_url)
        return None

    async def process_logout_response(
        self,
        provider_name: str,
        saml_response: str,
    ) -> bool:
        """Process SAML logout response"""
        client = self._clients.get(provider_name)
        if not client:
            raise ValueError(f"SAML provider '{provider_name}' not configured")

        # Parse logout response
        logout_response = client.parse_logout_request_response(
            saml_response,
            BINDING_HTTP_POST,
        )

        return logout_response is not None


__all__ = [
    "EmailAttributeMapper",
    "FirstNameAttributeMapper",
    "GroupsAttributeMapper",
    "LastNameAttributeMapper",
    "NameAttributeMapper",
    "SAMLAttributeMapper",
    "SAMLAttributeMapperRegistry",
    "SAMLManager",
    "SAMLProvider",
]
