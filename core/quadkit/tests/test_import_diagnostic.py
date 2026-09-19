import contextlib

with contextlib.suppress(Exception):
    pass

with contextlib.suppress(Exception):
    pass


def test_diagnostic():
    from quadkit.contracts.web import get

    assert get is not None
