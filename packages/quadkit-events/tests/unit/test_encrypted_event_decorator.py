"""Tests for the @encrypted_event class decorator."""

from __future__ import annotations

from quadkit.events.decorators.encryption import (
    ENCRYPTED_ATTR,
    encrypted_event,
)


class TestEncryptedEvent:
    def test_sets_key_alias_attribute(self) -> None:
        @encrypted_event(key_alias="events-key")
        class MyEvent:
            pass

        assert getattr(MyEvent, ENCRYPTED_ATTR) == "events-key"

    def test_attribute_name_constant(self) -> None:
        assert ENCRYPTED_ATTR == "__encrypted_event_key_alias__"

    def test_class_identity_preserved(self) -> None:
        base = type("Base", (), {})
        decorated = encrypted_event(key_alias="k")(base)
        assert decorated is base

    def test_undecorated_class_has_no_attribute(self) -> None:
        class Plain:
            pass

        assert not hasattr(Plain, ENCRYPTED_ATTR)

    def test_multiple_classes_independent(self) -> None:
        @encrypted_event(key_alias="a")
        class A:
            pass

        @encrypted_event(key_alias="b")
        class B:
            pass

        assert getattr(A, ENCRYPTED_ATTR) == "a"
        assert getattr(B, ENCRYPTED_ATTR) == "b"

    def test_key_alias_must_be_keyword(self) -> None:
        import pytest

        with pytest.raises(TypeError):
            encrypted_event("positional")  # type: ignore[call-arg]
