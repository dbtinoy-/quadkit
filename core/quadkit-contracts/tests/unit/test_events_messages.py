"""Events/CQRS message contracts: Message, metadata, queries, commands."""

from __future__ import annotations

from uuid import UUID, uuid4

from quadkit.contracts.events.messages import (
    Command,
    IdempotentCommand,
    Message,
    MessageMetadata,
    MessageSerializerProtocol,
    PaginatedQuery,
    Query,
)


class TestMessageMetadata:
    def test_defaults(self) -> None:
        m = MessageMetadata()
        assert m.correlation_id is None
        assert m.causation_id is None
        assert m.custom == {}

    def test_with_builders(self) -> None:
        m = MessageMetadata()
        cid = uuid4()
        assert m.with_correlation(cid).correlation_id is cid
        assert m.with_causation(uuid4()).causation_id is not None
        assert m.with_user("u1").user_id == "u1"
        assert m.with_tenant("t1").tenant_id == "t1"
        assert m.with_custom("k", 1).custom == {"k": 1}

    def test_with_custom_does_not_mutate(self) -> None:
        m = MessageMetadata(custom={"a": 1})
        m2 = m.with_custom("b", 2)
        assert m.custom == {"a": 1}
        assert m2.custom == {"a": 1, "b": 2}

    def test_frozen(self) -> None:
        import dataclasses

        import pytest

        m = MessageMetadata()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.user_id = "x"  # type: ignore[misc]


class TestMessage:
    def test_defaults(self) -> None:
        m = Message()
        assert isinstance(m.id, UUID)
        assert m.timestamp.tzinfo is not None
        assert m.metadata is not None
        assert m.correlation_id is None
        assert m.causation_id is None

    def test_correlation_roundtrip(self) -> None:
        m = Message()
        cid = uuid4()
        m2 = m.with_correlation_id(cid)
        assert m2.correlation_id is cid
        assert m.correlation_id is None  # original untouched

    def test_with_metadata(self) -> None:
        m = Message()
        new_meta = MessageMetadata(user_id="u")
        m2 = m.with_metadata(new_meta)
        assert m2.metadata is new_meta

    def test_dict_roundtrip(self) -> None:
        m = Message()
        data = m.to_dict()
        assert data["id"] == m.id
        # datetime is serialized via asdict (stays datetime)
        restored = Message.from_dict(data)
        assert restored.id == m.id
        assert restored.timestamp == m.timestamp


class TestQueries:
    def test_query_defaults(self) -> None:
        q = Query[str]()
        assert q.include_deleted is False
        assert q.cache_key is None
        assert q.skip_cache is False

    def test_paginated_defaults(self) -> None:
        q = PaginatedQuery[int]()
        assert q.page == 1
        assert q.page_size == 20
        assert q.sort_by is None
        assert q.sort_desc is False
        assert isinstance(q, Query)


class TestCommand:
    def test_plain_command(self) -> None:
        c = Command[int]()
        assert isinstance(c, Message)

    def test_subclass_with_fields(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True, init=False)
        class CreateUser(Command[bool]):
            username: str = ""

        c = CreateUser(username="alice")
        assert c.username == "alice"
        assert c.id is not None  # inherited Message defaults filled

    def test_extra_kwargs_stored_as_attributes(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True, init=False)
        class ExtraCommand(Command[bool]):
            pass

        c = ExtraCommand(note="keep-me")
        assert c.note == "keep-me"

    def test_idempotent_command(self) -> None:
        c = IdempotentCommand[bool](idempotency_key="k1")
        assert c.idempotency_key == "k1"
        assert isinstance(c, Command)

    def test_command_frozen(self) -> None:
        import dataclasses

        import pytest

        c = Command[int]()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.id = uuid4()  # type: ignore[misc]


class TestMessageSerializerProtocol:
    def test_runtime_checkable(self) -> None:
        class Good:
            def serialize(self, message: Message) -> bytes:
                return b""

            def deserialize(self, data: bytes, message_type: type[Message]) -> Message:
                return Message()

            def serialize_event(self, event: object) -> bytes:
                return b""

            def deserialize_event(self, data: bytes, event_type: type) -> object:
                return None

        class Bad:
            def serialize(self, message: Message) -> bytes:
                return b""

        assert isinstance(Good(), MessageSerializerProtocol)
        assert not isinstance(Bad(), MessageSerializerProtocol)
