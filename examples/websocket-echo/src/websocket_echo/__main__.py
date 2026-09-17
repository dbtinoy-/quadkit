"""Allow ``python -m websocket_echo`` to boot the demo."""

from websocket_echo.main import main

if __name__ == "__main__":
    raise SystemExit(main())
