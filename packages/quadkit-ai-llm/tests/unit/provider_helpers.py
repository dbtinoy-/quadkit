"""Test helpers for provider hermetic tests.

Provides fake stream context manager and fake client factories.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock


class DummyStreamCtx:
    def __init__(self, lines, use_content=False):
        self._lines = list(lines)
        self._use_content = use_content

    async def __aenter__(self):
        class Ctx:
            def __init__(self, lines, use_content):
                self._it = iter(lines)
                self._use_content = use_content

            def raise_for_status(self):
                return None

            # content property returning an async generator
            @property
            def content(self):
                async def gen():
                    for l in self._it:
                        yield l

                return gen()

            async def aiter_lines(self):
                for l in self._it:
                    yield l

        return Ctx(self._lines, self._use_content)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def make_fake_client(
    post_response=None, stream_lines=None, stream_raises=None, use_content=False,
):
    fake = SimpleNamespace()
    if post_response is None:

        async def default_json():
            return {}

        resp = SimpleNamespace()
        resp.raise_for_status = lambda: None
        resp.json = default_json
        fake.post = AsyncMock(return_value=resp)
    else:
        fake.post = AsyncMock(return_value=post_response)

    if stream_raises is not None:
        fake.stream = AsyncMock(side_effect=stream_raises)
    else:
        if stream_lines is None:
            fake.stream = AsyncMock(
                return_value=DummyStreamCtx([], use_content=use_content),
            )
        else:

            async def _stream(*a, **kw):
                return DummyStreamCtx(stream_lines, use_content=use_content)

            fake.stream = _stream

    return fake
