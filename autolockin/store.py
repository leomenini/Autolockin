"""Persistence. Writes are atomic so a crash mid-save can't corrupt the board."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import paths
from .models import Board


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_board(path: Path | None = None) -> Board:
    """Load the board, or an empty one if there isn't a saved board yet."""
    target = path or paths.BOARD_FILE
    if not target.exists():
        return Board()
    return Board.model_validate_json(target.read_text(encoding="utf-8"))


def save_board(board: Board, path: Path | None = None) -> None:
    target = path or paths.BOARD_FILE
    _write_atomic(target, board.model_dump_json(indent=2))


def load_ledger(path: Path | None = None) -> dict[str, int]:
    """The record of directory modes as they were before we touched them.

    Maps absolute path -> original mode. This is the only thing standing between a
    locked folder and a permanently inaccessible one, so it is written before any
    chmod happens, and read directly (never via the daemon) during recovery.
    """
    target = path or paths.LEDGER_FILE
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {str(k): int(v) for k, v in raw.items()}


def save_ledger(ledger: dict[str, int], path: Path | None = None) -> None:
    target = path or paths.LEDGER_FILE
    _write_atomic(target, json.dumps(ledger, indent=2, sort_keys=True))
