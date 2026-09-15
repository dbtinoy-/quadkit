import inspect

from quadkit.web.routing.router import Router


def test_get_handler_signature_is_cached(monkeypatch):
    calls = []

    def fake_get_type_hints(func, globalns=None):
        calls.append(func)
        return {}

    # Patch the module-level get_type_hints used by the router
    monkeypatch.setattr("quadkit.web.routing.router.get_type_hints", fake_get_type_hints)

    class Controller:
        async def handler(self, x: int) -> int:  # simple annotated handler
            return x

    router = Router()

    # First resolution should call get_type_hints
    sig1 = router._get_handler_signature(Controller, "handler")
    assert "sig" in sig1 and inspect.signature(getattr(Controller, "handler")) == sig1["sig"]

    # Second resolution must hit the cache and not call get_type_hints again
    sig2 = router._get_handler_signature(Controller, "handler")
    assert sig1 is sig2 or sig1 == sig2
    assert len(calls) == 1
