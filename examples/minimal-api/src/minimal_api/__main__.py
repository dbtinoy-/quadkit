"""Allow ``python -m minimal_api`` to boot the demo."""

from minimal_api.main import main

if __name__ == "__main__":
    raise SystemExit(main())
