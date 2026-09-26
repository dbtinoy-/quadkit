"""Event payload encryption for quadkit-events.

Provides opt-in Fernet-based encryption for domain events that contain
PII or other sensitive fields.

Usage::

    from quadkit.events.encryption import encrypted_event, EncryptedEventSerializer

    @encrypted_event(key_alias="events-key")
    class UserCreated(DomainEvent):
        email: str

    # In your provider / bootstrap code:
    from quadkit.security.secrets.store import InMemorySecretStore
    store = InMemorySecretStore()
    store.set_secret("events-key", Fernet.generate_key().decode())

    serializer = EncryptedEventSerializer(secret_store=store)
"""

from __future__ import annotations

from quadkit.events.decorators.encryption import encrypted_event
from quadkit.events.encryption.serializer import EncryptedEventSerializer

__all__ = ["EncryptedEventSerializer", "encrypted_event"]
