"""Allow ``python -m background_worker`` to boot the demo."""

from background_worker.main import main

if __name__ == "__main__":
    raise SystemExit(main())
