"""The escape hatch has to work even when everything else is broken."""

from __future__ import annotations

import json
import os
import stat

from autolockin import recover, store


def test_restore_puts_a_locked_directory_back(tmp_path):
    victim = tmp_path / "Games"
    victim.mkdir()
    original = stat.S_IMODE(victim.stat().st_mode)

    ledger = tmp_path / "locks.json"
    store.save_ledger({str(victim): original}, ledger)
    os.chmod(victim, 0o000)
    assert stat.S_IMODE(victim.stat().st_mode) == 0o000

    report = recover.restore_all(ledger)

    assert report.ok
    assert report.restored == [str(victim)]
    assert stat.S_IMODE(victim.stat().st_mode) == original
    assert store.load_ledger(ledger) == {}


def test_restore_on_an_empty_ledger_is_a_no_op(tmp_path):
    report = recover.restore_all(tmp_path / "nothing.json")
    assert report.ok
    assert report.restored == []
    assert "nothing was locked" in recover.format_report(report)


def test_restore_survives_a_corrupt_ledger(tmp_path):
    ledger = tmp_path / "locks.json"
    ledger.write_text("{not json at all", encoding="utf-8")
    report = recover.restore_all(ledger)
    assert report.ok


def test_restore_reports_paths_that_no_longer_exist(tmp_path):
    ledger = tmp_path / "locks.json"
    store.save_ledger({str(tmp_path / "deleted"): 0o755}, ledger)
    report = recover.restore_all(ledger)
    assert report.ok
    assert report.missing == [str(tmp_path / "deleted")]


def test_restore_handles_many_paths_independently(tmp_path):
    good = tmp_path / "good"
    good.mkdir()
    gone = tmp_path / "gone"
    ledger = tmp_path / "locks.json"
    store.save_ledger({str(good): 0o700, str(gone): 0o755}, ledger)

    report = recover.restore_all(ledger)

    assert report.restored == [str(good)]
    assert report.missing == [str(gone)]
    assert stat.S_IMODE(good.stat().st_mode) == 0o700


def test_ledger_is_written_atomically(tmp_path):
    """A half-written ledger is the one failure that would strand a folder."""
    ledger = tmp_path / "locks.json"
    store.save_ledger({"/a": 0o755}, ledger)
    store.save_ledger({"/b": 0o700}, ledger)
    assert json.loads(ledger.read_text()) == {"/b": 0o700}
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]
