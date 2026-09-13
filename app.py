from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

APP_VERSION = "0.1.0"

app = FastAPI(title="BLUETTI Web", version=APP_VERSION)
app.mount("/static", StaticFiles(directory="static"), name="static")

_state: dict[str, Any] = {
    "connected": True,
    "model": "EL30V2",
    "soc": 73,
    "ac_on": False,
    "dc_on": False,
    "ac_input_w": 0,
    "ac_output_w": 0,
    "dc_input_w": 84,
    "dc_output_w": 0,
    "temperature_c": 23.7,
    "charging_mode": "Silent",
    "battery_voltage_v": 25.6,
    "battery_current_a": 0.3,
    "battery_state": "Charging",
    "pv_generation_kwh": 3.1,
    "updated_at": time.time(),
}

_clients: set[WebSocket] = set()


def snapshot() -> dict[str, Any]:
    data = dict(_state)
    data["version"] = APP_VERSION
    return data


async def broadcast() -> None:
    if not _clients:
        return
    payload = snapshot()
    dead = []
    for ws in list(_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((Path("static") / "index.html").read_text(encoding="utf-8"))


@app.get("/api/state")
async def api_state() -> dict[str, Any]:
    return snapshot()


@app.post("/api/control/ac/{value}")
async def set_ac(value: int) -> dict[str, Any]:
    _state["ac_on"] = bool(value)
    _state["ac_output_w"] = 62 if _state["ac_on"] else 0
    _state["updated_at"] = time.time()
    await broadcast()
    return {"ok": True, "state": snapshot()}


@app.post("/api/control/dc/{value}")
async def set_dc(value: int) -> dict[str, Any]:
    _state["dc_on"] = bool(value)
    _state["dc_output_w"] = 18 if _state["dc_on"] else 0
    _state["updated_at"] = time.time()
    await broadcast()
    return {"ok": True, "state": snapshot()}


@app.post("/api/control/mode/{mode}")
async def set_mode(mode: str) -> dict[str, Any]:
    allowed = {"standard": "Standard", "silent": "Silent", "turbo": "Turbo"}
    key = mode.lower()
    if key not in allowed:
        return {"ok": False, "error": "invalid mode"}
    _state["charging_mode"] = allowed[key]
    _state["updated_at"] = time.time()
    await broadcast()
    return {"ok": True, "state": snapshot()}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        await ws.send_json(snapshot())
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


async def mock_telemetry_loop() -> None:
    while True:
        await asyncio.sleep(2.0)
        _state["dc_input_w"] = max(
            0, int(_state["dc_input_w"]) + random.choice([-2, -1, 0, 1, 2])
        )
        _state["temperature_c"] = round(
            float(_state["temperature_c"]) + random.choice([-0.1, 0.0, 0.1]), 1
        )
        _state["updated_at"] = time.time()
        await broadcast()


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(mock_telemetry_loop())
