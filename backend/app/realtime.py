"""WebSocket connection manager: pushes live events to every dashboard."""
import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger("realtime")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket, user: dict) -> None:
        await ws.accept()
        self.active[ws] = user
        log.info("WS connected (%d clients)", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.pop(ws, None)

    async def broadcast(self, event: str, data) -> None:
        message = json.dumps({"event": event, "data": data}, default=str)

        async def _send(ws: WebSocket):
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=5)
            except Exception:
                self.disconnect(ws)

        await asyncio.gather(*(_send(ws) for ws in list(self.active)), return_exceptions=True)


manager = ConnectionManager()
