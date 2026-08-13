"""The shape of a board: task nodes, reward nodes, and the edges between them."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Status = Literal["todo", "doing", "done"]
Recurrence = Literal["none", "daily", "weekly"]


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class Resource(BaseModel):
    """A link you'll need to actually do the task."""

    label: str = ""
    url: str = ""


class TaskNode(BaseModel):
    id: str
    kind: Literal["task"] = "task"
    title: str = "New task"
    minutes: int = 30
    notes: str = ""
    resources: list[Resource] = Field(default_factory=list)
    due: datetime | None = None
    recurrence: Recurrence = "none"
    status: Status = "todo"
    done_at: datetime | None = None
    position: Position = Field(default_factory=Position)


class RewardNode(BaseModel):
    """What completing the upstream chain buys you."""

    id: str
    kind: Literal["reward"] = "reward"
    title: str = "New reward"
    folders: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)
    position: Position = Field(default_factory=Position)


Node = Annotated[TaskNode | RewardNode, Field(discriminator="kind")]


class Edge(BaseModel):
    id: str
    source: str  # the prerequisite
    target: str  # the thing that depends on it


class Board(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def node(self, node_id: str) -> TaskNode | RewardNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    @property
    def tasks(self) -> list[TaskNode]:
        return [n for n in self.nodes if isinstance(n, TaskNode)]

    @property
    def rewards(self) -> list[RewardNode]:
        return [n for n in self.nodes if isinstance(n, RewardNode)]


class RewardState(BaseModel):
    """The resolved verdict for one reward node."""

    reward_id: str
    unlocked: bool
    blocking: list[str] = Field(default_factory=list)  # task ids not yet done
    overdue: list[str] = Field(default_factory=list)  # task ids past their deadline


class BoardState(BaseModel):
    """Everything the UI needs to render the current truth."""

    rewards: list[RewardState] = Field(default_factory=list)
    overdue: list[str] = Field(default_factory=list)
    mode: str = "off"
    panicked: bool = False
    errors: list[str] = Field(default_factory=list)
    resolved_at: datetime | None = None


class CycleError(ValueError):
    """The board contains a dependency cycle, so it cannot be resolved."""
