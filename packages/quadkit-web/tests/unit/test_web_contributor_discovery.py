from __future__ import annotations

from starlette.applications import Starlette

from quadkit.web.contributors.discovery import ENTRY_POINT_GROUP, load_web_contributors


class _WorkingContributor:
    @property
    def contributor_id(self) -> str:
        return "working"

    def get_controllers(self) -> list[type]:
        return []

    def get_middleware(self) -> list[type]:
        return []

    async def mount_to_app(self, app: Starlette, container: object) -> None:  # noqa: ARG002
        return None


class _WorkingEntryPoint:
    name = "working"

    def load(self):  # noqa: ANN201
        return _WorkingContributor


class _BrokenLoadEntryPoint:
    name = "broken-load"

    def load(self):  # noqa: ANN201
        raise RuntimeError("boom")


class _BrokenInitContributor:
    def __init__(self) -> None:
        raise RuntimeError("bad init")


class _BrokenInitEntryPoint:
    name = "broken-init"

    def load(self):  # noqa: ANN201
        return _BrokenInitContributor


def test_load_web_contributors_skips_bad_entry_points(monkeypatch) -> None:
    monkeypatch.setattr(
        "quadkit.web.contributors.discovery.entry_points",
        lambda group: [  # noqa: ARG005
            _BrokenLoadEntryPoint(),
            _BrokenInitEntryPoint(),
            _WorkingEntryPoint(),
        ],
    )

    contributors = load_web_contributors()

    assert ENTRY_POINT_GROUP == "quadkit.web.contributors"
    assert [contributor.contributor_id for contributor in contributors] == ["working"]
