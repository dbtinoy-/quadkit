"""Allow ``python -m http_side`` to boot the demo."""

from http_side.main import main

if __name__ == "__main__":
    raise SystemExit(main())
