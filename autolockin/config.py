"""Enforcement mode. Ships as "off" and stays there until you deliberately arm it.

The mode is read fresh on every tick, so changing it never needs a restart.
"""

from __future__ import annotations

import tomllib
from typing import Literal

from . import paths

Mode = Literal["off", "dry-run", "armed"]
VALID_MODES: tuple[Mode, ...] = ("off", "dry-run", "armed")
DEFAULT_MODE: Mode = "off"

_TEMPLATE = """\
# Autolockin enforcement mode.
#
#   off      Resolve the board and show locks in the UI, but never touch the system.
#   dry-run  Run the enforcement logic and log what it *would* do, without doing it.
#   armed    Actually chmod folders and kill processes.
#
# Start at "off". Move to "dry-run" and read the log for a while. Only then arm.
mode = "{mode}"
"""


def read_mode() -> Mode:
    """The configured mode, or "off" if the config is missing, invalid, or unreadable.

    Every failure path lands on "off" — the safe direction. A config you fat-fingered
    should never be what arms the enforcement.
    """
    if paths.PANIC_FILE.exists():
        return "off"
    try:
        raw = tomllib.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return DEFAULT_MODE
    mode = raw.get("mode", DEFAULT_MODE)
    return mode if mode in VALID_MODES else DEFAULT_MODE


def write_mode(mode: Mode) -> None:
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}, expected one of {VALID_MODES}")
    paths.ensure_dirs()
    paths.CONFIG_FILE.write_text(_TEMPLATE.format(mode=mode), encoding="utf-8")


def ensure_config() -> Mode:
    """Create the config with the safe default if it doesn't exist yet."""
    if not paths.CONFIG_FILE.exists():
        write_mode(DEFAULT_MODE)
    return read_mode()


def is_panicked() -> bool:
    return paths.PANIC_FILE.exists()


def should_enforce() -> bool:
    """The single gate. Nothing touches the system without going through here."""
    return not is_panicked() and read_mode() == "armed"
