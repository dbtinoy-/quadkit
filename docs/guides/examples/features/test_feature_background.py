"""Feature tour: background work.

Return the response now; run the rest after. Returning a tuple of
``(payload, BackgroundTasks)`` — or using the ``@background`` decorator API —
lets handlers acknowledge instantly while mail, indexing, and audit work
finish after the bytes hit the wire.
"""

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import BackgroundTasks, Controller, WebModule, get


class MailController(Controller):
    prefix = "/mail"

    @get("/send")
    async def send(self) -> tuple[dict, BackgroundTasks]:
        tasks = BackgroundTasks()
        tasks.add(_deliver, "hello@quadkit.dev")
        return {"queued": True, "task_count": len(tasks)}, tasks


delivered: list[str] = []


def _deliver(address: str) -> None:
    delivered.append(address)


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[MailController]))
    return app


@pytest.mark.asyncio
async def test_background_tasks_run_after_the_response():
    delivered.clear()
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/mail/send")
        assert response.status_code == 200
        assert response.json == {"queued": True, "task_count": 1}

    assert delivered == ["hello@quadkit.dev"]
