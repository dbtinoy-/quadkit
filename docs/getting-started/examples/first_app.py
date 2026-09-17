"""Runnable companion to docs/getting-started/first-app.md.

A minimal Quadkit web application: one controller, one route, booted by
the web module. Run it directly to serve over HTTP::

    python first_app.py

then browse http://localhost:8000/hello?name=quadkit — plus /health,
/docs (Swagger UI) and /redoc, which the web module adds for you.
"""

from quadkit import Application
from quadkit.web import Controller, WebModule, get
from quadkit.web.server import run_server


class HelloController(Controller):
    """A controller maps HTTP routes to typed async methods."""

    @get("/hello")
    async def hello(self, name: str = "world") -> dict:
        """Query parameters bind to method arguments by name."""
        return {"message": f"hello, {name}"}


def create_app() -> Application:
    """Assemble the application; the web server boots it on start."""
    app = Application()
    app.add_modules([WebModule.configure(controllers=[HelloController])])
    return app


app = create_app()

if __name__ == "__main__":
    # Serves on 0.0.0.0:8000 by default; the backend resolves from
    # application.yaml's web.server.backend, preferring Granian, then
    # Uvicorn when they are installed.
    run_server(app, port=8000)
