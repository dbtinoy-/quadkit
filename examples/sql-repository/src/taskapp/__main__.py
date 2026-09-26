"""Module entry point.

``python -m taskapp`` boots the REST API and serves the task manager.
"""

from __future__ import annotations


def main() -> None:
    from taskapp.main import main as serve_main

    serve_main()


if __name__ == "__main__":
    main()
