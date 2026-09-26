"""``@encrypted_event`` decorator for marking domain events as needing encryption at rest.

Usage::

    from quadkit.events.decorators.encryption import encrypted_event
    from quadkit.contracts.domain.events import DomainEvent

    @encrypted_event(key_alias="events-key")
    class UserCreated(DomainEvent):
        email: str
        name: str

The *key_alias* must match a secret name registered in the
:class:`~quadkit.contracts.security.secrets.SecretStoreProtocol` that
contains a valid Fernet key (``Fernet.generate_key().decode()``).

The decorator only stores metadata on the class — no encryption happens
at decoration time.  The actual encryption/decryption is performed by
:class:`~quadkit.events.encryption.serializer.EncryptedEventSerializer`
when events are persisted or loaded from the event store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_C = TypeVar("_C", bound=type)

#: Attribute set on decorated classes to signal encryption and carry the key alias.
ENCRYPTED_ATTR = "__encrypted_event_key_alias__"


def encrypted_event(*, key_alias: str) -> Callable[[_C], _C]:
    """Mark an event class as requiring Fernet encryption at rest.

    Args:
        key_alias: The name used to look up the Fernet key in the
            :class:`~quadkit.contracts.security.secrets.SecretStoreProtocol`.

    Returns:
        A class decorator that attaches ``__encrypted_event_key_alias__``
        metadata to the event class without otherwise modifying it.

    Example::

        @encrypted_event(key_alias="events/pii-key")
        class PaymentProcessed(DomainEvent):
            card_last_four: str
            amount: int
    """

    def decorator(cls: _C) -> _C:
        setattr(cls, ENCRYPTED_ATTR, key_alias)
        return cls

    return decorator


__all__ = ["ENCRYPTED_ATTR", "encrypted_event"]
