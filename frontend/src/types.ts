// Mirrors autolockin/models.py.

export type Status = "todo" | "doing" | "done";
export type Recurrence = "none" | "daily" | "weekly";
export type Mode = "off" | "dry-run" | "armed";

export interface Resource {
  label: string;
  url: string;
}

export interface Position {
  x: number;
  y: number;
}

export interface TaskNode {
  id: string;
  kind: "task";
  title: string;
  minutes: number;
  notes: string;
  resources: Resource[];
  due: string | null;
  recurrence: Recurrence;
  status: Status;
  done_at: string | null;
  position: Position;
}

export interface RewardNode {
  id: string;
  kind: "reward";
  title: string;
  folders: string[];
  processes: string[];
  position: Position;
}

export type BoardNode = TaskNode | RewardNode;

export interface BoardEdge {
  id: string;
  source: string;
  target: string;
}

export interface Board {
  nodes: BoardNode[];
  edges: BoardEdge[];
}

export interface RewardState {
  reward_id: string;
  unlocked: boolean;
  blocking: string[];
  overdue: string[];
}

export interface BoardState {
  rewards: RewardState[];
  overdue: string[];
  mode: Mode;
  panicked: boolean;
  errors: string[];
  resolved_at: string | null;
}

export const emptyTask = (id: string, position: Position): TaskNode => ({
  id,
  kind: "task",
  title: "New task",
  minutes: 30,
  notes: "",
  resources: [],
  due: null,
  recurrence: "none",
  status: "todo",
  done_at: null,
  position,
});

export const emptyReward = (id: string, position: Position): RewardNode => ({
  id,
  kind: "reward",
  title: "New reward",
  folders: [],
  processes: [],
  position,
});
