import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Status, TaskNode as Task } from "../types";

export interface TaskNodeData extends Record<string, unknown> {
  task: Task;
  overdue: boolean;
  onCycleStatus: (id: string, next: Status) => void;
}

const NEXT_STATUS: Record<Status, Status> = {
  todo: "doing",
  doing: "done",
  done: "todo",
};

function formatDue(due: string): string {
  const date = new Date(due);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return sameDay ? `today ${time}` : `${date.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`;
}

export function TaskNodeView({ data, selected }: NodeProps) {
  const { task, overdue, onCycleStatus } = data as unknown as TaskNodeData;

  const classes = [
    "node",
    `status-${task.status}`,
    overdue ? "overdue" : "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      <Handle type="target" position={Position.Left} />
      <div
        className="accent"
        title={`${task.status} — click to advance`}
        onClick={(event) => {
          event.stopPropagation();
          onCycleStatus(task.id, NEXT_STATUS[task.status]);
        }}
      />
      <div className="body">
        <div className="title">{task.title}</div>
        <div className="chips">
          <span className="chip">⏱ {task.minutes}m</span>
          {task.due && (
            <span className={`chip ${overdue ? "due-overdue" : ""}`}>
              {overdue ? "⚠ " : "📅 "}
              {formatDue(task.due)}
            </span>
          )}
          {task.recurrence !== "none" && <span className="chip recurring">↻ {task.recurrence}</span>}
        </div>
        {task.resources.length > 0 && (
          <div className="chips">
            {task.resources.map((resource, index) => (
              <a
                key={index}
                className="chip link"
                href={resource.url}
                target="_blank"
                rel="noreferrer"
                onClick={(event) => event.stopPropagation()}
              >
                🔗 {resource.label || resource.url}
              </a>
            ))}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
