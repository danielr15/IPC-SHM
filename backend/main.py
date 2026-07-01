from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from engine.models import (
    ProcessCountRequest,
    ProtectionRequest,
    ScenarioRequest,
    SimulationStateDTO,
)
from engine.simulator import engine

TICK_INTERVAL = 0.35
_auto_task: asyncio.Task | None = None
_ws_clients: list[WebSocket] = []


async def _broadcast(state: SimulationStateDTO) -> None:
    payload = state.model_dump()
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


async def _auto_tick_loop() -> None:
    while engine.running:
        state = engine.step()
        await _broadcast(state)
        await asyncio.sleep(TICK_INTERVAL)


def _start_auto_loop() -> None:
    global _auto_task
    if _auto_task is None or _auto_task.done():
        _auto_task = asyncio.create_task(_auto_tick_loop())


def _stop_auto_loop() -> None:
    global _auto_task
    engine.running = False
    if _auto_task and not _auto_task.done():
        _auto_task.cancel()
    _auto_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.clear_scenario()
    yield
    _stop_auto_loop()


app = FastAPI(
    title="Simulador IPC - Memória Compartilhada",
    description="API para simulação de IPC via memória compartilhada protegida",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, str]]:
    return engine.list_scenarios()


@app.get("/api/state", response_model=SimulationStateDTO)
def get_state() -> SimulationStateDTO:
    return engine.get_state()


@app.post("/api/protection", response_model=SimulationStateDTO)
def set_protection(req: ProtectionRequest) -> SimulationStateDTO:
    engine.set_protection(req.mode, req.k, reader_preference=req.reader_preference)
    return engine.get_state()


@app.post("/api/processes", response_model=SimulationStateDTO)
def set_process_count(req: ProcessCountRequest) -> SimulationStateDTO:
    try:
        engine.set_process_count(req.count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return engine.get_state()


@app.post("/api/scenario", response_model=SimulationStateDTO)
def load_scenario(req: ScenarioRequest) -> SimulationStateDTO:
    try:
        engine.load_scenario(req.name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return engine.get_state()


@app.post("/api/start", response_model=SimulationStateDTO)
async def start_simulation() -> SimulationStateDTO:
    engine.start()
    _start_auto_loop()
    return engine.get_state()


@app.post("/api/stop", response_model=SimulationStateDTO)
async def stop_simulation() -> SimulationStateDTO:
    _stop_auto_loop()
    return engine.get_state()


@app.post("/api/step", response_model=SimulationStateDTO)
async def step_simulation() -> SimulationStateDTO:
    was_running = engine.running
    engine.running = False
    state = engine.step()
    await _broadcast(state)
    if was_running:
        engine.running = True
        _start_auto_loop()
    return state


@app.post("/api/reset", response_model=SimulationStateDTO)
async def reset_simulation() -> SimulationStateDTO:
    _stop_auto_loop()
    engine.reset_simulation()
    state = engine.get_state()
    await _broadcast(state)
    return state


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        await websocket.send_json(engine.get_state().model_dump())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
