"""Emergency Detection, Public Safety & Response Coordination - API server."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .realtime import manager
from .routers import auth, cameras, incidents, units
from .security import decode_token
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
os.makedirs(settings.media_dir, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await seed()
    yield


app = FastAPI(
    title="Emergency Detection & Response Coordination API",
    version="1.0.0",
    description="AI-detected emergencies (falls, smoke, fire, intrusion, water distress) "
                "with location-tagged alerts, video evidence, operator verification and dispatch.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(incidents.router)
app.include_router(units.router)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/api/health")
async def health():
    return {"status": "ok", "ws_clients": len(manager.active)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    payload = decode_token(token)
    if not payload:
        await ws.close(code=4401)
        return
    await manager.connect(ws, payload)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"event":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
