"""Resolution logic: given a board and the current time, what is unlocked?

Everything here is free of I/O so it can be unit-tested directly. `advance_recurrence`
is the one function that mutates its argument; it says so in its docstring.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .models import Board, BoardState, CycleError, RewardState, TaskNode

_PERIODS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def _incoming(board: Board) -> dict[str, list[str]]:
    """node id -> ids of its direct prerequisites."""
    incoming: dict[str, list[str]] = defaultdict(list)
    ids = {n.id for n in board.nodes}
    for edge in board.edges:
        # Ignore edges pointing at nodes that no longer exist.
        if edge.source in ids and edge.target in ids:
            incoming[edge.target].append(edge.source)
    return incoming


def detect_cycle(board: Board) -> list[str] | None:
    """Return one cycle as a list of node ids, or None if the board is a DAG.

    The canvas lets you draw a cycle, so this has to be checked rather than assumed.
    """
    incoming = _incoming(board)
    UNVISITED, VISITING, DONE = 0, 1, 2
    color: dict[str, int] = {n.id: UNVISITED for n in board.nodes}

    def walk(node_id: str, path: list[str]) -> list[str] | None:
        color[node_id] = VISITING
        path.append(node_id)
        for parent in incoming.get(node_id, ()):
            if color.get(parent) == VISITING:
                return path[path.index(parent) :] + [parent]
            if color.get(parent) == UNVISITED:
                found = walk(parent, path)
                if found:
                    return found
        path.pop()
        color[node_id] = DONE
        return None

    for node in board.nodes:
        if color[node.id] == UNVISITED:
            found = walk(node.id, [])
            if found:
                return found
    return None


def ancestors(board: Board, node_id: str) -> set[str]:
    """Every node transitively upstream of `node_id` (its prerequisite closure)."""
    incoming = _incoming(board)
    seen: set[str] = set()
    queue = list(incoming.get(node_id, ()))
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(incoming.get(current, ()))
    return seen


def is_overdue(task: TaskNode, now: datetime) -> bool:
    return task.due is not None and task.status != "done" and task.due < now


def advance_recurrence(board: Board, now: datetime) -> list[str]:
    """Roll completed recurring tasks into their next period. **Mutates `board`.**

    This is what makes the board reset itself — there is no separate reset clock.
    A task you finished becomes `todo` again once the deadline it satisfied has passed,
    and its `due` moves forward to the next period still in the future.

    Returns the ids of the tasks that were reset.
    """
    reset: list[str] = []
    for task in board.tasks:
        period = _PERIODS.get(task.recurrence)
        if period is None or task.status != "done":
            continue

        if task.due is not None:
            if now >= task.due:
                next_due = task.due
                while next_due <= now:
                    next_due += period
                task.due = next_due
                task.status = "todo"
                task.done_at = None
                reset.append(task.id)
        elif task.done_at is not None and now >= task.done_at + period:
            # No deadline set, so the period runs from when you finished it.
            task.status = "todo"
            task.done_at = None
            reset.append(task.id)

    return reset


def resolve(board: Board, now: datetime) -> BoardState:
    """Work out which rewards are unlocked, and what is holding the locked ones back.

    A reward is unlocked when every task upstream of it is done and none of them is
    overdue. Overdue tasks are also, by definition, not done — they appear in both
    lists so the UI can say *why* something is blocking.
    """
    cycle = detect_cycle(board)
    if cycle:
        raise CycleError(" -> ".join(cycle))

    overdue_ids = [t.id for t in board.tasks if is_overdue(t, now)]

    states: list[RewardState] = []
    for reward in board.rewards:
        upstream = ancestors(board, reward.id)
        upstream_tasks = [t for t in board.tasks if t.id in upstream]
        blocking = [t.id for t in upstream_tasks if t.status != "done"]
        overdue = [t.id for t in upstream_tasks if is_overdue(t, now)]
        states.append(
            RewardState(
                reward_id=reward.id,
                unlocked=not blocking and not overdue,
                blocking=blocking,
                overdue=overdue,
            )
        )

    return BoardState(
        rewards=states,
        overdue=overdue_ids,
        resolved_at=now,
    )
