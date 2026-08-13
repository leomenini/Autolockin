import type { BoardNode, Recurrence, RewardNode, TaskNode } from "../types";

interface Props {
  node: BoardNode;
  onChange: (node: BoardNode) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

/** <input type="datetime-local"> wants "YYYY-MM-DDTHH:MM" with no zone or seconds. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

const fromLocalInput = (value: string): string | null =>
  value ? new Date(value).toISOString() : null;

/** One path or pattern per line, blanks dropped. */
const linesToList = (value: string): string[] =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

export function NodeEditor({ node, onChange, onDelete, onClose }: Props) {
  return (
    <aside className="drawer">
      <h2>{node.kind === "task" ? "Task" : "Reward"}</h2>

      <div className="field">
        <label>Title</label>
        <input
          value={node.title}
          onChange={(event) => onChange({ ...node, title: event.target.value })}
          autoFocus
        />
      </div>

      {node.kind === "task" ? (
        <TaskFields
          task={node}
          patch={(changes) => onChange({ ...node, ...changes })}
        />
      ) : (
        <RewardFields
          reward={node}
          patch={(changes) => onChange({ ...node, ...changes })}
        />
      )}

      <div className="drawer-actions">
        <button onClick={onClose}>Close</button>
        <button className="danger" onClick={() => onDelete(node.id)}>
          Delete node
        </button>
      </div>
    </aside>
  );
}

function TaskFields({
  task,
  patch,
}: {
  task: TaskNode;
  patch: (changes: Partial<TaskNode>) => void;
}) {
  const setResource = (index: number, changes: Partial<{ label: string; url: string }>) => {
    const resources = task.resources.map((resource, i) =>
      i === index ? { ...resource, ...changes } : resource
    );
    patch({ resources });
  };

  return (
    <>
      <div className="row">
        <div className="field">
          <label>Minutes</label>
          <input
            type="number"
            min={0}
            value={task.minutes}
            onChange={(event) => patch({ minutes: Number(event.target.value) || 0 })}
          />
        </div>
        <div className="field">
          <label>Status</label>
          <select
            value={task.status}
            onChange={(event) => patch({ status: event.target.value as TaskNode["status"] })}
          >
            <option value="todo">todo</option>
            <option value="doing">doing</option>
            <option value="done">done</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label>Due</label>
        <input
          type="datetime-local"
          value={toLocalInput(task.due)}
          onChange={(event) => patch({ due: fromLocalInput(event.target.value) })}
        />
      </div>

      <div className="field">
        <label>Repeats</label>
        <select
          value={task.recurrence}
          onChange={(event) => patch({ recurrence: event.target.value as Recurrence })}
        >
          <option value="none">never</option>
          <option value="daily">daily</option>
          <option value="weekly">weekly</option>
        </select>
      </div>
      <p className="hint">
        A repeating task comes back as <i>todo</i> once its deadline passes — which re-locks
        anything downstream of it.
      </p>

      <div className="field">
        <label>Notes</label>
        <textarea value={task.notes} onChange={(event) => patch({ notes: event.target.value })} />
      </div>

      <div className="field">
        <label>Resources</label>
        {task.resources.map((resource, index) => (
          <div className="resource-row" key={index}>
            <input
              className="label"
              placeholder="label"
              value={resource.label}
              onChange={(event) => setResource(index, { label: event.target.value })}
            />
            <input
              placeholder="https://…"
              value={resource.url}
              onChange={(event) => setResource(index, { url: event.target.value })}
            />
            <button
              onClick={() =>
                patch({ resources: task.resources.filter((_, i) => i !== index) })
              }
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={() => patch({ resources: [...task.resources, { label: "", url: "" }] })}
        >
          + link
        </button>
      </div>
    </>
  );
}

function RewardFields({
  reward,
  patch,
}: {
  reward: RewardNode;
  patch: (changes: Partial<RewardNode>) => void;
}) {
  return (
    <>
      <div className="field">
        <label>Folders (one per line)</label>
        <textarea
          placeholder={"/home/you/Games\n/home/you/Videos"}
          value={reward.folders.join("\n")}
          onChange={(event) => patch({ folders: linesToList(event.target.value) })}
        />
      </div>

      <div className="field">
        <label>Processes (one pattern per line)</label>
        <textarea
          placeholder={"steam\nlutris"}
          value={reward.processes.join("\n")}
          onChange={(event) => patch({ processes: linesToList(event.target.value) })}
        />
      </div>

      <p className="hint">
        These are recorded but <b>not enforced</b> while the mode badge says OFF — nothing on
        your machine is touched. Enforcement is a separate, deliberate step; see the README.
      </p>
    </>
  );
}
