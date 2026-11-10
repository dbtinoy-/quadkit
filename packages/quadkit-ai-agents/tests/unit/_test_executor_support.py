"""Shared fixtures/stubs for test_executor tests."""

from __future__ import annotations

from quadkit.ai.agents.strategies import ReActStrategy


class MockAgent:
    """Mock agent for testing."""

    def __init__(
        self,
        name: str = "test_agent",
        tools: list | None = None,
        system_prompt: str = "",
    ):
        self.name = name
        self._tools = tools or []
        self.system_prompt = system_prompt
        self.strategy = ReActStrategy()

    @property
    def tools(self):
        return self._tools


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str = "test response"):
        self.response = response
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs):
        self.call_count += 1
        return {"content": self.response, "usage": {"tokens": 10}}

    async def complete(self, messages, **kwargs):
        """Return a Result-like object wrapping a Completion-like object."""
        self.call_count += 1

        class _Completion:
            def __init__(self, text: str):
                self.content = f"THOUGHT: Responding directly\nFINAL_ANSWER: {text}"

        class _Ok:
            def __init__(self, val):
                self._val = val

            def is_ok(self):
                return True

            def is_err(self):
                return False

            def unwrap(self):
                return self._val

        return _Ok(_Completion(self.response))


class MockGovernance:
    """Mock governance for testing."""

    def __init__(self, allow: bool = True):
        self.allow = allow
        self.check_count = 0

    async def check_request(
        self, model: str, provider: str, user_id: str | None = None
    ):
        self.check_count += 1
        return self.allow


class MockMemory:
    """Mock memory for testing."""

    def __init__(self, messages: list | None = None):
        self._messages = messages or []
        self.added = []

    def get_messages_dict(self):
        return self._messages

    async def add(self, role: str, content: str):
        self.added.append({"role": role, "content": content})


class MockEventBus:
    """Mock event bus for testing."""

    def __init__(self):
        self.published_events = []

    async def publish(self, event):
        self.published_events.append(event)


class MockGuardPipeline:
    def __init__(self, input_action="allow", output_action="allow", final_content=None):
        self.input_action = input_action
        self.output_action = output_action
        self.final_content = final_content
        self.input_called = False
        self.output_called = False

    async def check_input(self, content, **kwargs):
        self.input_called = True
        return self._make_result(self.input_action, content)

    async def check_output(self, content, original_input="", **kwargs):
        self.output_called = True
        return self._make_result(self.output_action, content)

    def _make_result(self, action, content):
        from quadkit.result import Ok

        class MockGuardResult:
            def __init__(self, action, name, reason):
                self.action = action
                self.guard_name = name
                self.reason = reason
                self.passed = action in ("pass", "warn", "redact")
                self.details = {}

        class MockAggregateGuardResult:
            def __init__(self, action, blocked, blocking_result, final_content):
                self.action = action
                self.blocked = blocked
                self.blocking_result = blocking_result
                self.final_content = final_content

            @property
            def passed(self) -> bool:
                return not self.blocked

            @property
            def guard_name(self) -> str:
                return "aggregate"

            @property
            def details(self) -> dict:
                return {}

        if action == "block":
            agg = MockAggregateGuardResult(
                action="block",
                blocked=True,
                blocking_result=MockGuardResult("block", "stub", "blocked"),
                final_content=self.final_content or content,
            )
        else:
            agg = MockAggregateGuardResult(
                action="pass",
                blocked=False,
                blocking_result=None,
                final_content=self.final_content or content,
            )
        return Ok(agg)
