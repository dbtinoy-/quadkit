"""Allow ``python -m auth_tokens`` to boot the demo."""

from auth_tokens.main import main

if __name__ == "__main__":
    raise SystemExit(main())
