"""Allow ``python -m database_tasks`` to boot the demo."""

from database_tasks.main import main

if __name__ == "__main__":
    raise SystemExit(main())
