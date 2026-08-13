"""The local server: board CRUD, resolved state, and a socket that pushes changes."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, paths, store
from .models import Board, Status
from .ticker import Ticker

log = logging.getLogger("autolockin.app")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class Sockets:
    """Every open canvas, so a state change reaches all of them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, socket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(socket)

    async def remove(self, socket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(socket)

    async def broadcast(self, payload) -> None:
        async with self._lock:
            clients = list(self._clients)
        for socket in clients:
            try:
                await socket.send_text(payload.model_dump_json())
            except Exception:
                await self.remove(socket)


sockets = Sockets()
ticker = Ticker(broadcast=sockets.broadcast)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    paths.ensure_dirs()
    mode = config.ensure_config()
    log.info("autolockin starting in mode=%s", mode)
    await ticker.start()
    try:
        yield
    finally:
        await ticker.stop()


app = FastAPI(title="Autolockin", lifespan=lifespan)


class StatusUpdate(BaseModel):
    status: Status


@app.get("/api/board")
def get_board() -> Board:
    return store.load_board()


@app.put("/api/board")
async def put_board(board: Board) -> dict:
    store.save_board(board)
    state = await ticker.tick()
    return {"saved": True, "errors": state.errors}


@app.post("/api/nodes/{node_id}/status")
async def set_status(node_id: str, update: StatusUpdate) -> dict:
    board = store.load_board()
    node = board.node(node_id)
    if node is None or node.kind != "task":
        raise HTTPException(status_code=404, detail=f"no task node {node_id!r}")

    node.status = update.status
    node.done_at = datetime.now() if update.status == "done" else None
    store.save_board(board)

    await ticker.tick()
    return {"id": node_id, "status": node.status}


@app.get("/api/state")
async def get_state():
    """Resolve on demand so a fresh page load never waits for the next tick."""
    return await ticker.tick()


@app.websocket("/ws")
async def websocket(socket: WebSocket) -> None:
    await socket.accept()
    await sockets.add(socket)
    try:
        await socket.send_text(ticker.state.model_dump_json())
        while True:
            # We don't expect messages; this just keeps the connection open and
            # notices when the tab closes.
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await sockets.remove(socket)


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

else:

    @app.get("/")
    def index_missing() -> dict:
        return {
            "error": "frontend not built",
            "fix": "cd frontend && npm install && npm run build",
        }
