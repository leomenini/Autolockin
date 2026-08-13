from __future__ import annotations

import stat

import pytest
from fastapi.testclient import TestClient

from autolockin import app as app_module
from autolockin import config, paths


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A server with its state redirected into tmp_path, so tests never touch real state."""
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(paths, "BOARD_FILE", tmp_path / "data" / "board.json")
    monkeypatch.setattr(paths, "LEDGER_FILE", tmp_path / "data" / "locks.json")
    monkeypatch.setattr(paths, "PANIC_FILE", tmp_path / "data" / "PANIC")
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config" / "config.toml")
    with TestClient(app_module.app) as test_client:
        yield test_client


def two_tasks_one_reward(folder: str) -> dict:
    return {
        "nodes": [
            {"id": "hw", "kind": "task", "title": "Maths sheet", "minutes": 45},
            {"id": "read", "kind": "task", "title": "Read chapter 4", "minutes": 30},
            {"id": "steam", "kind": "reward", "title": "Steam",
             "folders": [folder], "processes": ["steam"]},
        ],
        "edges": [
            {"id": "e1", "source": "hw", "target": "steam"},
            {"id": "e2", "source": "read", "target": "steam"},
        ],
    }


def test_board_round_trips(client, tmp_path):
    board = two_tasks_one_reward(str(tmp_path))
    assert client.put("/api/board", json=board).json()["saved"] is True

    saved = client.get("/api/board").json()
    assert [n["id"] for n in saved["nodes"]] == ["hw", "read", "steam"]
    assert saved["nodes"][0]["minutes"] == 45


def test_completing_the_chain_unlocks_the_reward(client, tmp_path):
    client.put("/api/board", json=two_tasks_one_reward(str(tmp_path)))

    state = client.get("/api/state").json()
    assert state["rewards"][0]["unlocked"] is False
    assert sorted(state["rewards"][0]["blocking"]) == ["hw", "read"]

    client.post("/api/nodes/hw/status", json={"status": "done"})
    assert client.get("/api/state").json()["rewards"][0]["unlocked"] is False

    client.post("/api/nodes/read/status", json={"status": "done"})
    assert client.get("/api/state").json()["rewards"][0]["unlocked"] is True


def test_uncompleting_a_task_relocks(client, tmp_path):
    client.put("/api/board", json=two_tasks_one_reward(str(tmp_path)))
    client.post("/api/nodes/hw/status", json={"status": "done"})
    client.post("/api/nodes/read/status", json={"status": "done"})
    assert client.get("/api/state").json()["rewards"][0]["unlocked"] is True

    client.post("/api/nodes/hw/status", json={"status": "todo"})
    assert client.get("/api/state").json()["rewards"][0]["unlocked"] is False


def test_status_on_a_missing_or_non_task_node_404s(client, tmp_path):
    client.put("/api/board", json=two_tasks_one_reward(str(tmp_path)))
    assert client.post("/api/nodes/nope/status", json={"status": "done"}).status_code == 404
    assert client.post("/api/nodes/steam/status", json={"status": "done"}).status_code == 404


def test_a_cyclic_board_is_reported_not_crashed(client):
    cyclic = {
        "nodes": [
            {"id": "a", "kind": "task"},
            {"id": "b", "kind": "task"},
            {"id": "r", "kind": "reward"},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "a"},
        ],
    }
    assert client.put("/api/board", json=cyclic).status_code == 200
    state = client.get("/api/state").json()
    assert state["errors"] and "cycle" in state["errors"][0]


def test_websocket_pushes_the_current_state(client, tmp_path):
    client.put("/api/board", json=two_tasks_one_reward(str(tmp_path)))
    with client.websocket_connect("/ws") as socket:
        payload = socket.receive_json()
        assert "rewards" in payload
        assert payload["mode"] == "off"


# --- the important one ----------------------------------------------------


def test_daemon_is_inert(client, tmp_path):
    """Build one must not touch the system. A locked reward with a real folder and a
    real process pattern should leave both completely alone."""
    victim = tmp_path / "Games"
    victim.mkdir()
    before = stat.S_IMODE(victim.stat().st_mode)

    client.put("/api/board", json=two_tasks_one_reward(str(victim)))
    state = client.get("/api/state").json()

    assert state["rewards"][0]["unlocked"] is False  # it really is locked, logically
    assert state["mode"] == "off"
    assert stat.S_IMODE(victim.stat().st_mode) == before  # ...and nothing happened
    assert not paths.LEDGER_FILE.exists()


def test_should_enforce_is_false_by_default(client):
    assert config.read_mode() == "off"
    assert config.should_enforce() is False


def test_panic_file_forces_mode_off(client):
    config.write_mode("armed")
    assert config.should_enforce() is True

    paths.PANIC_FILE.write_text("stop", encoding="utf-8")
    assert config.read_mode() == "off"
    assert config.should_enforce() is False
    assert client.get("/api/state").json()["panicked"] is True
