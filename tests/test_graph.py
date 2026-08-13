from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from autolockin.graph import (
    advance_recurrence,
    ancestors,
    detect_cycle,
    is_overdue,
    resolve,
)
from autolockin.models import Board, CycleError, Edge, RewardNode, TaskNode

NOW = datetime(2026, 8, 13, 12, 0, 0)


def task(node_id: str, **kwargs) -> TaskNode:
    return TaskNode(id=node_id, title=node_id, **kwargs)


def board_of(*nodes, edges: list[tuple[str, str]] = ()) -> Board:
    return Board(
        nodes=list(nodes),
        edges=[Edge(id=f"{s}->{t}", source=s, target=t) for s, t in edges],
    )


def state_for(board: Board, reward_id: str, now: datetime = NOW):
    return next(r for r in resolve(board, now).rewards if r.reward_id == reward_id)


# --- ancestors / cycles ---------------------------------------------------


def test_ancestors_are_transitive():
    b = board_of(
        task("a"), task("b"), task("c"), RewardNode(id="r"),
        edges=[("a", "b"), ("b", "c"), ("c", "r")],
    )
    assert ancestors(b, "r") == {"a", "b", "c"}
    assert ancestors(b, "b") == {"a"}
    assert ancestors(b, "a") == set()


def test_diamond_dependency_counts_each_node_once():
    b = board_of(
        task("top"), task("left"), task("right"), RewardNode(id="r"),
        edges=[("top", "left"), ("top", "right"), ("left", "r"), ("right", "r")],
    )
    assert ancestors(b, "r") == {"top", "left", "right"}


def test_edges_to_deleted_nodes_are_ignored():
    b = board_of(task("a"), RewardNode(id="r"), edges=[("ghost", "r"), ("a", "r")])
    assert ancestors(b, "r") == {"a"}


def test_detect_cycle_finds_a_loop():
    b = board_of(task("a"), task("b"), edges=[("a", "b"), ("b", "a")])
    cycle = detect_cycle(b)
    assert cycle is not None
    assert set(cycle) == {"a", "b"}


def test_detect_cycle_returns_none_for_a_dag():
    b = board_of(task("a"), task("b"), edges=[("a", "b")])
    assert detect_cycle(b) is None


def test_resolve_refuses_a_cyclic_board():
    b = board_of(task("a"), task("b"), RewardNode(id="r"), edges=[("a", "b"), ("b", "a")])
    with pytest.raises(CycleError):
        resolve(b, NOW)


def test_ancestors_terminates_on_a_cycle():
    # resolve() rejects cycles, but ancestors() must not hang if called directly.
    b = board_of(task("a"), task("b"), edges=[("a", "b"), ("b", "a")])
    assert ancestors(b, "a") == {"a", "b"}


# --- unlocking ------------------------------------------------------------


def test_reward_locked_until_every_upstream_task_is_done():
    b = board_of(
        task("a", status="done"), task("b"), RewardNode(id="r"),
        edges=[("a", "r"), ("b", "r")],
    )
    assert state_for(b, "r").unlocked is False
    assert state_for(b, "r").blocking == ["b"]

    b.node("b").status = "done"
    assert state_for(b, "r").unlocked is True
    assert state_for(b, "r").blocking == []


def test_reward_with_no_prerequisites_is_unlocked():
    b = board_of(RewardNode(id="r"))
    assert state_for(b, "r").unlocked is True


def test_doing_is_not_done():
    b = board_of(task("a", status="doing"), RewardNode(id="r"), edges=[("a", "r")])
    assert state_for(b, "r").unlocked is False


def test_rewards_are_independent():
    b = board_of(
        task("homework", status="done"), task("dishes"),
        RewardNode(id="games"), RewardNode(id="folder"),
        edges=[("homework", "folder"), ("dishes", "games")],
    )
    assert state_for(b, "folder").unlocked is True
    assert state_for(b, "games").unlocked is False


def test_chained_rewards_inherit_upstream_tasks():
    b = board_of(
        task("a"), RewardNode(id="r1"), RewardNode(id="r2"),
        edges=[("a", "r1"), ("r1", "r2")],
    )
    assert state_for(b, "r2").blocking == ["a"]


# --- deadlines ------------------------------------------------------------


def test_is_overdue_only_for_unfinished_past_deadlines():
    past, future = NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    assert is_overdue(task("a", due=past), NOW) is True
    assert is_overdue(task("a", due=future), NOW) is False
    assert is_overdue(task("a", due=past, status="done"), NOW) is False
    assert is_overdue(task("a", due=None), NOW) is False


def test_overdue_upstream_task_relocks_a_reward():
    """The whole point of per-node deadlines: an unlocked reward can go back."""
    due = NOW + timedelta(minutes=30)
    b = board_of(
        task("chore", status="done", due=due, recurrence="daily"),
        RewardNode(id="steam"),
        edges=[("chore", "steam")],
    )
    assert state_for(b, "steam").unlocked is True

    # An hour later the daily chore has rolled over and is now past its new deadline.
    later = NOW + timedelta(hours=1)
    advance_recurrence(b, later)
    b.node("chore").due = later - timedelta(minutes=1)  # its deadline has just lapsed

    relocked = state_for(b, "steam", later)
    assert relocked.unlocked is False
    assert relocked.overdue == ["chore"]
    assert relocked.blocking == ["chore"]


def test_board_state_lists_all_overdue_tasks():
    b = board_of(
        task("a", due=NOW - timedelta(days=1)),
        task("b", due=NOW + timedelta(days=1)),
    )
    assert resolve(b, NOW).overdue == ["a"]


# --- recurrence -----------------------------------------------------------


def test_daily_task_resets_once_its_deadline_passes():
    due = NOW - timedelta(minutes=5)
    b = board_of(task("a", status="done", done_at=NOW, due=due, recurrence="daily"))

    assert advance_recurrence(b, NOW) == ["a"]
    a = b.node("a")
    assert a.status == "todo"
    assert a.done_at is None
    assert a.due == due + timedelta(days=1)


def test_recurrence_does_not_reset_before_the_deadline():
    due = NOW + timedelta(hours=2)
    b = board_of(task("a", status="done", done_at=NOW, due=due, recurrence="daily"))
    assert advance_recurrence(b, NOW) == []
    assert b.node("a").status == "done"


def test_recurrence_catches_up_after_a_long_gap():
    """Come back after a week away and the daily task shouldn't be a week overdue."""
    due = NOW - timedelta(days=6, hours=3)
    b = board_of(task("a", status="done", done_at=due, due=due, recurrence="daily"))
    advance_recurrence(b, NOW)
    assert b.node("a").due > NOW
    assert b.node("a").due <= NOW + timedelta(days=1)


def test_weekly_task_advances_by_a_week():
    due = NOW - timedelta(minutes=1)
    b = board_of(task("a", status="done", done_at=NOW, due=due, recurrence="weekly"))
    advance_recurrence(b, NOW)
    assert b.node("a").due == due + timedelta(weeks=1)


def test_recurring_task_without_a_deadline_resets_a_period_after_completion():
    b = board_of(task("a", status="done", done_at=NOW, recurrence="daily"))
    assert advance_recurrence(b, NOW + timedelta(hours=23)) == []
    assert advance_recurrence(b, NOW + timedelta(days=1)) == ["a"]
    assert b.node("a").status == "todo"


def test_non_recurring_task_stays_done():
    b = board_of(
        task("a", status="done", done_at=NOW, due=NOW - timedelta(days=5)),
    )
    assert advance_recurrence(b, NOW) == []
    assert b.node("a").status == "done"
