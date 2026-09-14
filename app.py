from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from bluetti_backend import BluettiCommunityService

APP_VERSION = "0.2.12"

service = BluettiCommunityService()
_clients: set[WebSocket] = set()


async def broadcast_loop() -> None:
    last_revision = -1
    while True:
        await asyncio.sleep(0.10)
        revision = service.revision
        if revision == last_revision:
            continue
        last_revision = revision
        payload = service.snapshot(APP_VERSION)
        dead: list[WebSocket] = []
        for ws in list(_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[BLUETTI WEB] Starting Community service...")
    service_task = asyncio.create_task(service.run(), name="bluetti-community-service")
    broadcast_task = asyncio.create_task(broadcast_loop(), name="bluetti-web-broadcast")
    try:
        yield
    finally:
        print("[BLUETTI WEB] Shutdown requested.")
        service.stop()
        for task in (broadcast_task, service_task):
            task.cancel()
        print("[BLUETTI WEB] Waiting for service tasks to stop...")
        results = await asyncio.gather(broadcast_task, service_task, return_exceptions=True)
        print(f"[BLUETTI WEB] Service tasks stopped: {results!r}")


app = FastAPI(title="BLUETTI Web", version=APP_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((Path("static") / "index.html").read_text(encoding="utf-8"))


@app.get("/api/state")
async def api_state() -> dict[str, Any]:
    return service.snapshot(APP_VERSION)


@app.post("/api/control/ac/{value}")
async def set_ac(value: int) -> dict[str, Any]:
    if value not in (0, 1):
        raise HTTPException(status_code=400, detail="AC value must be 0 or 1")
    await service.queue_control("ac", value)
    return {"ok": True, "state": service.snapshot(APP_VERSION)}


@app.post("/api/control/dc/{value}")
async def set_dc(value: int) -> dict[str, Any]:
    if value not in (0, 1):
        raise HTTPException(status_code=400, detail="DC value must be 0 or 1")
    await service.queue_control("dc", value)
    return {"ok": True, "state": service.snapshot(APP_VERSION)}


@app.post("/api/control/mode/{mode}")
async def set_mode(mode: str) -> dict[str, Any]:
    allowed = {"standard": "Standard", "silent": "Silent", "turbo": "Turbo"}
    key = mode.lower()
    if key not in allowed:
        raise HTTPException(status_code=400, detail="Invalid charging mode")
    await service.queue_control("mode", allowed[key])
    return {"ok": True, "state": service.snapshot(APP_VERSION)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        await ws.send_json(service.snapshot(APP_VERSION))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
