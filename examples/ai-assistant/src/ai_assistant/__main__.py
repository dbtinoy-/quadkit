"""Allow ``python -m ai_assistant`` to boot the demo."""

from ai_assistant.main import main

if __name__ == "__main__":
    raise SystemExit(main())
