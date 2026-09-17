"""Allow ``python -m multi_tenant_notes`` to boot the demo."""

from multi_tenant_notes.main import main

if __name__ == "__main__":
    raise SystemExit(main())
