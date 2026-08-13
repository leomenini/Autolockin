"""Where Autolockin keeps its state. One place, so nothing has to guess."""

from __future__ import annotations

import os
from pathlib import Path


def _xdg(env_var: str, fallback: str) -> Path:
    raw = os.environ.get(env_var)
    return Path(raw) if raw else Path.home() / fallback


DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / "autolockin"
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / "autolockin"

BOARD_FILE = DATA_DIR / "board.json"
LEDGER_FILE = DATA_DIR / "locks.json"
PANIC_FILE = DATA_DIR / "PANIC"
DRYRUN_LOG = DATA_DIR / "dryrun.log"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
