"""Encrypted event serializer using Fernet symmetric encryption.

Event payloads that contain PII or sensitive fields can be encrypted at
rest by wrapping the default JSON serializer with
:class:`EncryptedEventSerializer`.  Key material is fetched on demand
from a :class:`~quadkit.contracts.security.secrets.SecretStoreProtocol`
so that keys are never stored in application code.

Only events decorated with :func:`~quadkit.events.decorators.encryption.encrypted_event`
are encrypted; plain events pass through the inner serializer unchanged.

Example::

    from cryptography.fernet import Fernet
    from quadkit.events.encryption.serializer import EncryptedEventSerializer
    from quadkit.security.secrets.store import InMemorySecretStore

    store = InMemorySecretStore()
    store.set_secret("events-key", Fernet.generate_key().decode())

    serializer = EncryptedEventSerializer(secret_store=store)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from quadkit.contracts.security.secrets import SecretStoreProtocol
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)

# Marker key written into the stored JSON so the deserialiser knows the
# ``"payload"`` field contains Fernet-encrypted ciphertext.
_ENCRYPTED_MARKER = "_enc"
_ENCRYPTED_VERSION = 1


class EncryptedEventSerializer:
    """Serializer that transparently encrypts event payloads marked with ``@encrypted_event``.

    Non-encrypted events are serialised/deserialised unchanged by the inner
    *json_serializer*.  Encrypted events have their payload field replaced by
    Fernet ciphertext so that the stored bytes reveal no plaintext.

    Key material is retrieved lazily via :class:`~quadkit.contracts.security.secrets.SecretStoreProtocol`
    and cached in-process for performance.

    Args:
        secret_store: Provides Fernet keys by alias.
        json_serializer: Inner serializer used for non-encrypted events and
            for converting the event data to JSON before encryption.  When
            ``None``, :func:`json.dumps` / :func:`json.loads` are used.
    """

    def __init__(
        self,
        secret_store: SecretStoreProtocol,
        json_serializer: Any | None = None,
    ) -> None:
        """Initialise the encrypted event serializer.

        Args:
            secret_store: Secret store from which Fernet keys are fetched.
            json_serializer: Optional inner serializer.  Must implement
                ``serialize(event) -> dict`` and ``deserialize(data) -> Event``.
        """
        self._store = secret_store
        self._inner = json_serializer
        self._key_cache: dict[str, bytes] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_fernet(self, key_alias: str) -> Any:
        """Return a :class:`~cryptography.fernet.Fernet` instance for *key_alias*.

        Args:
            key_alias: The secret name used to look up the Fernet key.

        Returns:
            A configured :class:`~cryptography.fernet.Fernet` instance.

        Raises:
            RuntimeError: If the ``cryptography`` package is not installed.
            SecretNotFoundError: If the key alias is not found in the store.
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'cryptography' package is required for encrypted events. "
                "Install it with: uv add cryptography"
            ) from exc

        if key_alias not in self._key_cache:
            raw_key = self._store.get_secret(key_alias)
            self._key_cache[key_alias] = (
                raw_key.encode() if isinstance(raw_key, str) else raw_key
            )

        return Fernet(self._key_cache[key_alias])

    def _event_to_dict(self, event: Event) -> dict[str, Any]:
        """Convert *event* to a plain dict using the inner serializer or model_dump.

        Args:
            event: The domain event to serialise.

        Returns:
            Dict representation suitable for JSON encoding.
        """
        if self._inner is not None:
            payload: dict[str, Any] = self._inner.serialize(event)
            return payload
        if hasattr(event, "model_dump"):
            dumped: dict[str, Any] = event.model_dump(mode="json")
            return dumped
        return dict(getattr(event, "__dict__", {}))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def serialize(self, event: Event) -> dict[str, Any]:
        """Serialise *event*, encrypting the payload when marked with ``@encrypted_event``.

        For non-encrypted events the inner serializer is used directly.
        For encrypted events, the full JSON payload is encrypted with Fernet
        and stored under the ``"payload"`` key alongside an ``"_enc"`` marker.

        Args:
            event: The domain event to serialise.

        Returns:
            A dict safe for persistence.  Encrypted events include
            ``{"_enc": 1, "event_type": "...", "payload": "<ciphertext>"}``.
        """
        key_alias: str | None = getattr(
            type(event), "__encrypted_event_key_alias__", None
        )

        if key_alias is None:
            # Not an encrypted event — pass through.
            return self._event_to_dict(event)

        fernet = self._get_fernet(key_alias)
        inner_dict = self._event_to_dict(event)
        plaintext = dumps(inner_dict)
        ciphertext = fernet.encrypt(plaintext.encode()).decode()  # type: ignore[attr-defined]

        event_type: str = getattr(event, "event_type", type(event).__name__)
        logger.debug("event.encrypted", event_type=event_type, key_alias=key_alias)

        return {
            _ENCRYPTED_MARKER: _ENCRYPTED_VERSION,
            "event_type": event_type,
            "payload": ciphertext,
        }

    def deserialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decrypt *data* if it carries the encrypted marker.

        Non-encrypted records are returned unchanged so that migration is
        seamless (existing plaintext records still deserialise correctly).

        Args:
            data: The raw dict loaded from storage.

        Returns:
            The original event dict (plaintext).
        """
        if data.get(_ENCRYPTED_MARKER) != _ENCRYPTED_VERSION:
            # Plaintext record — nothing to do.
            return data

        event_type: str = data.get("event_type", "<unknown>")
        ciphertext: str = data["payload"]

        # Determine which key alias to use.
        # This is stored as metadata on the registered event class when available.
        key_alias: str | None = None
        if self._inner is not None and hasattr(self._inner, "_event_type_registry"):
            event_cls = self._inner._event_type_registry.get(event_type)
            if event_cls is not None:
                key_alias = getattr(event_cls, "__encrypted_event_key_alias__", None)

        if key_alias is None:
            # Fall back: try the event_type itself as the alias key prefix
            logger.warning(
                "event.decrypt.no_key_alias",
                event_type=event_type,
                note="Cannot determine key alias; returning raw record",
            )
            return data

        fernet = self._get_fernet(key_alias)
        plaintext = fernet.decrypt(ciphertext.encode())
        decrypted: dict[str, Any] = loads(plaintext.decode())
        logger.debug("event.decrypted", event_type=event_type, key_alias=key_alias)
        return decrypted


__all__ = ["EncryptedEventSerializer"]
