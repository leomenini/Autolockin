"""Getting your folders back.

This module deliberately depends on nothing but the ledger file. It does not import
the daemon, does not talk to it over HTTP, and does not care whether it is running,
hung, or crashed mid-write. If Autolockin ever locks something it shouldn't have,
this is the code that undoes it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import paths, store


@dataclass
class RestoreReport:
    restored: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # path no longer exists
    failed: list[tuple[str, int, str]] = field(default_factory=list)  # path, mode, error

    @property
    def ok(self) -> bool:
        return not self.failed


def restore_all(ledger_path: Path | None = None) -> RestoreReport:
    """Put every path in the ledger back to the mode it had before we touched it.

    Entries that succeed are dropped from the ledger; entries that fail are kept, so
    a later run can try again. Never raises — a recovery tool that can crash halfway
    is not a recovery tool.
    """
    target = ledger_path or paths.LEDGER_FILE
    ledger = store.load_ledger(target)
    report = RestoreReport()
    remaining: dict[str, int] = {}

    for path_str, mode in ledger.items():
        path = Path(path_str)
        if not path.exists():
            report.missing.append(path_str)
            continue
        try:
            os.chmod(path, mode)
            report.restored.append(path_str)
        except OSError as exc:
            remaining[path_str] = mode
            report.failed.append((path_str, mode, str(exc)))

    store.save_ledger(remaining, target)
    return report


def format_report(report: RestoreReport) -> str:
    lines: list[str] = []
    for path in report.restored:
        lines.append(f"  restored  {path}")
    for path in report.missing:
        lines.append(f"  gone      {path} (no longer exists, nothing to restore)")
    for path, mode, error in report.failed:
        lines.append(f"  FAILED    {path}: {error}")
        lines.append(f"            fix it by hand:  chmod {mode & 0o7777:o} {path}")
    if not lines:
        lines.append("  nothing was locked")
    return "\n".join(lines)
