"""Core security API surface: events, hooks, decorators, config, provider."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib

import pytest

from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.domain.events import DomainEvent
from quadkit.contracts.security import (
    HasherProtocol,
    InputSanitizerProtocol,
    KeyDerivationProtocol,
)
from quadkit.di.container.container import Container
from quadkit.security import (
    InputSanitizer,
    SecurityGuardBlockedHook,
    SecurityGuardPassedHook,
    SecurityProvider,
    SecurityThreatDetectedHook,
    Sha256Hasher,
    sanitize_input,
)
from quadkit.security.config import HashingConfig, InputSanitizerConfig, SecurityConfig
from quadkit.security.events import (
    CsrfViolationEvent,
    SecretRotatedEvent,
    SecurityGuardDeniedEvent,
    ThreatDetectedEvent,
)


class TestSecurityEvents:
    def test_events_are_frozen_domain_events(self) -> None:
        e = ThreatDetectedEvent(threat_type="xss", source_ip="1.2.3.4")
        assert isinstance(e, DomainEvent)
        assert e.threat_type == "xss"
        with pytest.raises(FrozenInstanceError):
            e.threat_type = "sqli"  # type: ignore[misc]

    def test_event_defaults(self) -> None:
        assert SecretRotatedEvent().secret_name == ""
        assert CsrfViolationEvent(path="/a", method="POST").method == "POST"
        assert SecurityGuardDeniedEvent(guard_name="g").guard_name == "g"


class TestSecurityHooks:
    def test_hook_payloads(self) -> None:
        h = SecurityGuardPassedHook(guard_name="csrf")
        assert h.guard_name == "csrf"
        b = SecurityGuardBlockedHook(guard_name="csrf", reason="bad token")
        assert (b.guard_name, b.reason) == ("csrf", "bad token")
        t = SecurityThreatDetectedHook(threat_type="sqli", source="q")
        assert t.source == "q"

    def test_hooks_frozen(self) -> None:
        h = SecurityGuardPassedHook(guard_name="x")
        with pytest.raises(FrozenInstanceError):
            h.guard_name = "y"  # type: ignore[misc]


class TestSanitizeInputDecorator:
    def test_sync_handler_sanitizes_string_fields(self) -> None:
        @sanitize_input("comment")
        def create(comment: str, other: str) -> tuple[str, str]:
            return comment, other

        result = create(comment="<b>x</b><script>bad()</script>", other="<i>keep")
        # script stripped, non-target field untouched
        assert "<script>" not in result[0]
        assert result[1] == "<i>keep"

    async def test_async_handler_sanitizes(self) -> None:
        @sanitize_input("bio", "name")
        async def update(bio: str, name: str) -> str:
            return bio

        assert "<script>" not in await update(bio="<script>x</script>", name="n")

    def test_non_string_values_pass_through(self) -> None:
        @sanitize_input("payload")
        def handle(payload: object) -> object:
            return payload

        assert handle(payload={"a": 1}) == {"a": 1}
        assert handle(payload=None) is None

    def test_absent_fields_pass_through(self) -> None:
        @sanitize_input("missing")
        def handle() -> str:
            return "ok"

        assert handle() == "ok"

    def test_custom_sanitizer_injected(self) -> None:
        class Marker:
            def sanitize(self, value: str) -> str:
                return f"[{value}]"

        @sanitize_input("v", sanitizer=Marker())
        def handle(v: str) -> str:
            return v

        assert handle(v="x") == "[x]"


class TestSecurityConfig:
    def test_defaults(self) -> None:
        cfg = SecurityConfig()
        assert cfg.enabled is True
        assert cfg.name == "security"
        assert isinstance(cfg.sanitization, InputSanitizerConfig)
        assert isinstance(cfg.hashing, HashingConfig)
        assert cfg.hashing.default_hasher == "sha256"
        assert cfg.hashing.iterations == 100_000

    def test_sub_config_overrides(self) -> None:
        cfg = SecurityConfig(
            sanitization=InputSanitizerConfig(default_sanitize_mode="escape"),
            hashing=HashingConfig(iterations=5_000),
        )
        assert cfg.sanitization.default_sanitize_mode == "escape"
        assert cfg.hashing.iterations == 5_000


class TestSecurityProvider:
    async def test_register_and_boot(self) -> None:
        provider = SecurityProvider()
        container = Container()
        await provider.register(container)

        assert await container.resolve(SecurityConfig) is provider._config
        assert await container.resolve(HasherProtocol) is not None
        assert await container.resolve(KeyDerivationProtocol) is not None
        assert isinstance(await container.resolve(InputSanitizer), InputSanitizerProtocol)

        await provider.boot(container)
        assert provider._input_sanitizer is not None

    async def test_hasher_selection_by_config(self) -> None:
        provider = SecurityProvider(
            SecurityConfig(hashing=HashingConfig(default_hasher="blake2b"))
        )
        container = Container()
        await provider.register(container)
        hasher = await container.resolve(HasherProtocol)
        assert hasher.algorithm == "blake2b"

    async def test_input_sanitizer_config_wrapped(self) -> None:
        provider = SecurityProvider(InputSanitizerConfig(strip_comments=False))
        assert provider._config.sanitization.strip_comments is False

    async def test_health_and_shutdown(self) -> None:
        provider = SecurityProvider()
        result = await provider.health_check()
        assert result.status is HealthStatus.HEALTHY
        assert result.component == "security"
        await provider.shutdown()


class TestSha256Hasher:
    def test_known_vector(self) -> None:
        expected = hashlib.sha256(b"abc").hexdigest()
        assert Sha256Hasher().digest("abc") == expected

    def test_bytes_input(self) -> None:
        assert Sha256Hasher().digest(b"abc") == Sha256Hasher().digest("abc")

    def test_verify_digest_constant_time(self) -> None:
        h = Sha256Hasher()
        assert h.verify_digest("abc", h.digest("abc"))
        assert not h.verify_digest("abc", "0" * 64)
        assert h.algorithm == "sha256"

    async def test_async_aliases(self) -> None:
        h = Sha256Hasher()
        value = await h.hash("abc")
        assert await h.verify("abc", value)
        assert not await h.verify("abd", value)


class TestBlake2bHasher:
    def test_known_vector(self) -> None:
        from quadkit.security.hashing import Blake2bHasher

        expected = hashlib.blake2b(b"abc").hexdigest()
        assert Blake2bHasher().digest("abc") == expected
        assert Blake2bHasher(digest_size=32).digest("abc") == hashlib.blake2b(
            b"abc", digest_size=32
        ).hexdigest()
        assert Blake2bHasher().verify_digest("abc", expected)
        assert Blake2bHasher().algorithm == "blake2b"
