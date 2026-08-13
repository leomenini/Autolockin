"""The heartbeat: roll recurring tasks over, resolve the graph, tell everyone.

In build one this loop is deliberately toothless. `_enforce` is the single place
enforcement will ever be called from, and it returns immediately unless the mode is
"armed" — which it is not, by default. Nothing here touches the filesystem or any
process.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from . import config, graph, store
from .models import Board, BoardState, CycleError

log = logging.getLogger("autolockin.ticker")

TICK_SECONDS = 5.0

Broadcast = Callable[[BoardState], Awaitable[None]]


class Ticker:
    def __init__(self, broadcast: Broadcast | None = None) -> None:
        self._broadcast = broadcast
        self._task: asyncio.Task | None = None
        self.state = BoardState(mode=config.read_mode())

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # a bad board must not kill the loop
                log.exception("tick failed")
            await asyncio.sleep(TICK_SECONDS)

    async def tick(self, now: datetime | None = None) -> BoardState:
        now = now or datetime.now()
        board = store.load_board()

        reset = graph.advance_recurrence(board, now)
        if reset:
            log.info("recurring tasks reset: %s", ", ".join(reset))
            store.save_board(board)

        self.state = self.resolve(board, now)

        if config.should_enforce():
            self._enforce(self.state, board)

        if self._broadcast is not None:
            await self._broadcast(self.state)
        return self.state

    def resolve(self, board: Board, now: datetime) -> BoardState:
        """Resolve, turning a cyclic board into a reported error instead of a crash."""
        try:
            state = graph.resolve(board, now)
        except CycleError as exc:
            state = BoardState(errors=[f"dependency cycle: {exc}"], resolved_at=now)
        state.mode = config.read_mode()
        state.panicked = config.is_panicked()
        return state

    def _enforce(self, state: BoardState, board: Board) -> None:
        """Build two lives here. Until then, arming does nothing at all."""
        log.debug("enforcement is armed but not implemented yet; doing nothing")
