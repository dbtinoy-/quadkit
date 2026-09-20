"""Feature tour: the Invoker — Java-style method injection, minus the ceremony.

Every `Application` owns an `Invoker` (registered in its own container) that
calls plain async functions with **dependencies resolved from the container
by type** and **arguments supplied positionally** — one line where you'd
otherwise write a doctorate in wiring. The invocation also flows through the
application middleware pipeline, the same one request transports share.
"""

import pytest

from quadkit import Application, Invoker


class GreetingService:
    def hello(self, name: str) -> str:
        return f"hello, {name}"


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[str] = []

    def note(self, entry: str) -> None:
        self.entries.append(entry)


async def greet(name: str, service: GreetingService, log: AuditLog) -> str:
    """Caller-supplied args come first; services resolve by type after them."""
    log.note(f"greeting {name}")
    return service.hello(name)


@pytest.mark.asyncio
async def test_invoker_injects_by_type() -> None:
    app = Application()
    app.container.singleton(GreetingService, GreetingService())
    audit = AuditLog()
    app.container.singleton(AuditLog, audit)

    await app.start()
    try:
        invoker = await app.container.resolve(Invoker)
        assert await invoker.invoke(greet, "ada") == "hello, ada"
        assert audit.entries == ["greeting ada"]
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_invoker_keywords_and_positionals() -> None:
    app = Application()
    app.container.singleton(GreetingService, GreetingService())
    app.container.singleton(AuditLog, AuditLog())

    await app.start()
    try:
        invoker = await app.container.resolve(Invoker)
        assert await invoker.invoke(greet, name="grace") == "hello, grace"
    finally:
        await app.stop()
