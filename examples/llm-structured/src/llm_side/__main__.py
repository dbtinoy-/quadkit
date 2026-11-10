"""Allow ``python -m llm_side`` to boot the demo."""

from llm_side.main import main

if __name__ == "__main__":
    raise SystemExit(main())
