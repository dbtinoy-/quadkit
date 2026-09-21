# WebSocket Echo

Room-based WebSocket service — the canonical starter for Quadkit's
websocket surface: connection lifecycle hooks, JSON messages, per-room
membership, a configurable member cap, and an HTTP stats endpoint
sharing the same DI-registered state.

**Demonstrates:** `@websocket_handler("/ws/echo/{room}")`, the
`AbstractWebSocketHandler` lifecycle
(`on_connect`/`on_message`/`on_disconnect`), path parameters,
`broadcast`, and in-process WebSocket tests via
`bed.client.websocket_connect(...)`.

## Layout

```
src/websocket_echo/
├── app.py              # composition root
├── main.py             # serve() with try/finally app.stop()
├── config.py           # WebsocketEchoConfig (max_room_members)
├── controllers/api.py  # StatsController — GET /, GET /stats
├── handlers/echo.py    # EchoHandler — WS /ws/echo/{room}
├── services/rooms.py   # ConnectionRegistry + RoomFullError
└── di/provider.py      # wires registry → handler → controller
```

## Run

```bash
pip install quadkit[web]
PYTHONPATH=src python -m websocket_echo
# then: websocat ws://localhost:8121/ws/echo/lobby
```

Rooms are unlimited by default; set `websocket_echo.max_room_members`
(override with `QK_WEBSOCKET_ECHO__MAX_ROOM_MEMBERS=2`) and extra
members receive a `{"type": "error", "reason": "room-full"}` frame
before the socket closes with 1013.

## Test

```bash
PYTHONPATH=src pytest tests/
```
