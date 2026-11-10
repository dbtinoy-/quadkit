"""Allow ``python -m mcp_side`` to boot the demo."""

from mcp_side.main import main

if __name__ == "__main__":
    raise SystemExit(main())
