"""The provider descriptor: one description, two projections, no runtime.

PROV-2 (`docs/specs/2026-10-29/03-provider-system.md`) makes a vendor's
description data rather than code, so a gateway can route from it and a fixture
pack can publish evidence from it. What is asserted here is the part a later
slice depends on:

* the shape refuses the contradictions that would otherwise surface as traffic
  going to the wrong adaptor — a header name missing, a capability that cannot
  exist alone, two vendors on one channel type;
* a vendor with no fixtures must *say why*, because "we never wrote one" and
  "the terms forbid recording one" are different states for a reviewer;
* the routing projection is deterministic and total, including aliases;
* importing the module pulls no HTTP client, no database driver, no container and
  nothing from either application — the purity is the point, not a side effect.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys

import pytest

from quadkit.contracts.ai import (
    AliasSpec,
    AuthMode,
    AuthStyle,
    FixtureRef,
    OperationMap,
    ProviderCapability,
    ProviderDescriptor,
    SourcePin,
    Translation,
    Vocabulary,
    WireFamily,
    ensure_unique_provider_ids,
    routing_table,
)


def descriptor(**overrides: object) -> ProviderDescriptor:
    """A minimal valid descriptor; each test overrides one field."""
    fields: dict[str, object] = {
        "provider_id": "kling",
        "display_name": "Kling",
        "channel_type": 50,
        "wire": WireFamily.TASK_ASYNC,
        "base_url": "https://api.klingai.com",
        "auth": AuthStyle(AuthMode.BEARER),
        "capabilities": frozenset({ProviderCapability.VIDEO, ProviderCapability.IMAGE}),
        "fixtures": (FixtureRef("kling.video-v1", "sdk-review-2026-10-28"),),
    }
    fields.update(overrides)
    return ProviderDescriptor(**fields)  # type: ignore[arg-type]


class TestAuthStyle:
    def test_a_bearer_needs_no_header(self) -> None:
        assert AuthStyle(AuthMode.BEARER).header is None

    def test_a_header_vendor_must_name_the_header(self) -> None:
        with pytest.raises(ValueError, match="must name the header"):
            AuthStyle(AuthMode.API_KEY_HEADER)

    def test_a_header_style_without_the_mode_is_refused(self) -> None:
        """The failure that ships a key in the wrong header is symmetric."""
        with pytest.raises(ValueError, match="must not name a header"):
            AuthStyle(AuthMode.BEARER, header="x-api-key")

    def test_a_named_header_survives_construction(self) -> None:
        style = AuthStyle(AuthMode.API_KEY_HEADER, header="x-goog-api-key")

        assert style.header == "x-goog-api-key"

    def test_a_bearer_may_name_its_own_scheme(self) -> None:
        """fal sends `Authorization: Key <key>` (`providers/fal.py`), not Bearer."""
        assert AuthStyle(AuthMode.BEARER, scheme="Key").scheme == "Key"

    def test_only_a_bearer_may_name_a_scheme(self) -> None:
        with pytest.raises(ValueError, match="must not name a scheme"):
            AuthStyle(AuthMode.API_KEY_HEADER, header="x-api-key", scheme="Key")

    def test_a_query_vendor_must_name_its_parameter(self) -> None:
        """Gemini builds `?key=` in the path (`gemini.py:82`), so this is live."""
        with pytest.raises(ValueError, match="must name the query parameter"):
            AuthStyle(AuthMode.API_KEY_QUERY)

    def test_a_query_parameter_survives_construction(self) -> None:
        assert AuthStyle(AuthMode.API_KEY_QUERY, parameter="key").parameter == "key"

    @pytest.mark.parametrize(
        ("style", "match"),
        [
            (
                {"mode": AuthMode.API_KEY_QUERY, "header": "x-goog-api-key"},
                "must not name a header",
            ),
            (
                {"mode": AuthMode.API_KEY_HEADER, "parameter": "key"},
                "must not name a query",
            ),
            (
                {"mode": AuthMode.BEARER, "parameter": "key"},
                "must not name a header or parameter",
            ),
        ],
    )
    def test_the_wrong_named_field_is_refused(self, style: dict, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            AuthStyle(**style)  # type: ignore[arg-type]


class TestOperationMap:
    def test_a_well_formed_operation_is_frozen(self) -> None:
        operation = OperationMap(
            operation_id="chat",
            gateway_method="POST",
            gateway_path="/v1/chat/completions",
            upstream_method="POST",
            upstream_path="/chat/completions",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            operation.gateway_path = "/elsewhere"  # type: ignore[misc]
        assert operation.translation is Translation.PASSTHROUGH

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("operation_id", "  ", "operation_id"),
            ("gateway_method", "post", "uppercase HTTP method"),
            ("upstream_method", "P0ST", "uppercase HTTP method"),
            ("gateway_path", "v1/chat", "absolute path"),
            ("upstream_path", "/v1//chat", "ambiguous segment"),
        ],
    )
    def test_malformed_operations_are_refused(
        self, field: str, value: str, match: str
    ) -> None:
        fields = {
            "operation_id": "chat",
            "gateway_method": "POST",
            "gateway_path": "/v1/chat/completions",
            "upstream_method": "POST",
            "upstream_path": "/chat/completions",
            field: value,
        }

        with pytest.raises(ValueError, match=match):
            OperationMap(**fields)  # type: ignore[arg-type]


class TestProviderDescriptor:
    def test_the_minimal_descriptor_round_trips(self) -> None:
        vendor = descriptor()

        assert vendor.channel_types == (50,)
        assert vendor.vocabulary is Vocabulary.NEWAPI
        assert vendor.pricing_ns == "default"
        assert vendor.operation("chat") is None

    def test_aliases_extend_the_channel_types(self) -> None:
        """Azure's three ids are the case this field exists for."""
        vendor = descriptor(
            aliases=(AliasSpec(3, "Azure OpenAI is the same wire on its own id"),)
        )

        assert vendor.channel_types == (50, 3)

    def test_a_channel_type_claimed_twice_is_refused(self) -> None:
        with pytest.raises(ValueError, match="claimed twice"):
            descriptor(aliases=(AliasSpec(50, "duplicate"),))

    def test_a_boolean_channel_type_is_not_a_number(self) -> None:
        with pytest.raises(TypeError, match="channel_type must be an integer"):
            descriptor(channel_type=True)

    def test_a_relative_base_url_is_refused(self) -> None:
        with pytest.raises(ValueError, match="absolute http"):
            descriptor(base_url="api.klingai.com")

    def test_a_vendor_with_no_recorded_endpoint_asks_the_operator(self) -> None:
        """Only three channel types have a default URL in the tree; the rest do not."""
        vendor = descriptor(base_url=None)

        assert vendor.requires_operator_base_url
        assert descriptor().requires_operator_base_url is False

    def test_a_capabilityless_vendor_cannot_be_routed(self) -> None:
        with pytest.raises(ValueError, match="no capability"):
            descriptor(capabilities=frozenset())

    def test_stream_without_chat_is_refused(self) -> None:
        with pytest.raises(ValueError, match="STREAM without CHAT"):
            descriptor(capabilities=frozenset({ProviderCapability.STREAM}))

    def test_a_mutable_capability_set_is_frozen_on_construction(self) -> None:
        vendor = descriptor(capabilities={ProviderCapability.CHAT})  # type: ignore[arg-type]

        assert isinstance(vendor.capabilities, frozenset)

    def test_duplicate_operation_ids_are_refused(self) -> None:
        chat = OperationMap("chat", "POST", "/v1/chat", "POST", "/chat")
        with pytest.raises(ValueError, match="unique"):
            descriptor(operations=(chat, chat))

    def test_fixtures_and_their_absence_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError, match="both ship"):
            descriptor(fixtures_absent_reason="vendored terms forbid it")

    def test_a_vendor_without_fixtures_must_say_why(self) -> None:
        with pytest.raises(ValueError, match="say why"):
            descriptor(fixtures=())

    def test_a_written_reason_is_accepted(self) -> None:
        vendor = descriptor(
            fixtures=(), fixtures_absent_reason="recording is forbidden"
        )

        assert vendor.fixtures == ()
        assert vendor.fixture_profile_ids == ()

    def test_a_vendor_may_ship_several_profiles(self) -> None:
        """Anthropic has three; one reference would silently drop two."""
        vendor = descriptor(
            fixtures=(
                FixtureRef(
                    "anthropic.messages-2023", "sdk-2023-06-01-review-2026-10-27"
                ),
                FixtureRef(
                    "anthropic.messages-2026", "sdk-2026-10-21-review-2026-10-27"
                ),
                FixtureRef("anthropic.stream-2026", "sdk-2026-10-21-review-2026-10-27"),
            )
        )

        assert vendor.fixture_profile_ids == (
            "anthropic.messages-2023",
            "anthropic.messages-2026",
            "anthropic.stream-2026",
        )

    def test_one_profile_referenced_twice_is_refused(self) -> None:
        with pytest.raises(ValueError, match="one fixture profile twice"):
            descriptor(
                fixtures=(
                    FixtureRef("kling.video-v1", "a"),
                    FixtureRef("kling.video-v1", "b"),
                )
            )

    def test_operations_are_addressable_by_id(self) -> None:
        chat = OperationMap("chat", "POST", "/v1/chat", "POST", "/chat")
        vendor = descriptor(operations=(chat,))

        assert vendor.operation("chat") is chat
        assert vendor.operation("missing") is None


class TestSourcePin:
    def test_a_pin_names_its_artifact_and_revision(self) -> None:
        pin = SourcePin("vendored/kling/openapi.json", revision="60c29b9d")

        assert pin.sha256 is None

    @pytest.mark.parametrize(
        ("path", "revision", "match"),
        [
            ("  ", "abc", "name the artifact"),
            ("vendored/x.json", " ", "name a revision"),
        ],
    )
    def test_an_anonymous_pin_is_refused(
        self, path: str, revision: str, match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            SourcePin(path, revision=revision)

    def test_a_malformed_digest_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed sha256"):
            SourcePin("vendored/x.json", revision="abc", sha256="deadbeef")


class TestRoutingTable:
    def test_the_table_indexes_primary_and_alias_ids(self) -> None:
        vendor = descriptor(aliases=(AliasSpec(3, "azure"),))

        table = routing_table([vendor])

        assert table == {50: vendor, 3: vendor}

    def test_two_vendors_on_one_type_is_a_build_error(self) -> None:
        """Last-one-wins is exactly the silence PROV-1 removed for unknown types."""
        with pytest.raises(ValueError, match="claimed by both"):
            routing_table([descriptor(), descriptor(provider_id="other")])

    def test_one_vendor_listed_twice_is_not_a_collision(self) -> None:
        vendor = descriptor()

        assert routing_table([vendor, vendor]) == {50: vendor}

    def test_duplicate_provider_ids_have_their_own_refusal(self) -> None:
        with pytest.raises(ValueError, match="described twice"):
            ensure_unique_provider_ids([descriptor(), descriptor(channel_type=51)])

    def test_unique_ids_pass(self) -> None:
        ensure_unique_provider_ids(
            [descriptor(), descriptor(provider_id="suno", channel_type=64)]
        )


def test_the_module_is_pure() -> None:
    """No HTTP client, no database driver, no container, no application import.

    A fresh interpreter, because this session has all of them importable already
    — an in-process assertion would pass for the wrong reason.

    Stated as an allowlist rather than a banned list. The banned list named the
    applications it feared, which meant a *new* application import passed the
    test silently — the test only caught the ones somebody had already thought
    of. The contract has no third-party dependency beyond ``typing_extensions``
    (measured: everything else in ``sys.modules`` after the import is stdlib), so
    "stdlib, quadkit, typing_extensions" is an exact rule rather than a
    guess, and it holds whatever an application is called.
    """
    code = (
        "import sys\n"
        "import quadkit.contracts.ai.providers\n"
        # `sitecustomize` is the environment's, not the module's: it is injected
        # by site initialisation before any import runs.
        "allowed = set(sys.stdlib_module_names) | {'quadkit', 'typing_extensions', 'sitecustomize'}\n"
        "tops = {m.split('.')[0] for m in sys.modules if not m.startswith('_')}\n"
        "print(','.join(sorted(tops - allowed)) or 'clean')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean"
