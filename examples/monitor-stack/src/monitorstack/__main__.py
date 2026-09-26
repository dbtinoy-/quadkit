"""Module entry point.

``python -m monitorstack`` boots the REST API and serves the monitor stack.
"""

from __future__ import annotations


def main() -> None:
    from monitorstack.main import main as serve_main

    serve_main()


if __name__ == "__main__":
    main()
