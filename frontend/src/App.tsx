import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import * as api from "./api";
import { RewardNodeView } from "./nodes/RewardNode";
import { TaskNodeView } from "./nodes/TaskNode";
import { NodeEditor } from "./panel/NodeEditor";
import {
  emptyReward,
  emptyTask,
  type Board,
  type BoardNode,
  type BoardState,
  type Status,
} from "./types";

const nodeTypes = { task: TaskNodeView, reward: RewardNodeView };
const SAVE_DEBOUNCE_MS = 800;

const newId = () => `n${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

type SaveState = "idle" | "saving" | "saved" | "error";

export default function App() {
  const [board, setBoard] = useState<Board>({ nodes: [], edges: [] });
  const [state, setState] = useState<BoardState | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [loaded, setLoaded] = useState(false);

  const saveTimer = useRef<number | undefined>(undefined);
  const boardRef = useRef(board);
  boardRef.current = board;

  // --- load + live state ------------------------------------------------

  useEffect(() => {
    api
      .getBoard()
      .then((loadedBoard) => {
        setBoard(loadedBoard);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    api.getState().then(setState).catch(() => undefined);
    return api.connect(setState);
  }, []);

  // --- saving -----------------------------------------------------------

  const save = useCallback((next: Board) => {
    window.clearTimeout(saveTimer.current);
    setSaveState("saving");
    saveTimer.current = window.setTimeout(() => {
      api
        .putBoard(next)
        .then(() => setSaveState("saved"))
        .catch(() => setSaveState("error"));
    }, SAVE_DEBOUNCE_MS);
  }, []);

  const update = useCallback(
    (next: Board) => {
      setBoard(next);
      save(next);
    },
    [save]
  );

  // --- domain <-> react flow -------------------------------------------

  const rewardStates = useMemo(
    () => new Map((state?.rewards ?? []).map((reward) => [reward.reward_id, reward])),
    [state]
  );
  const overdue = useMemo(() => new Set(state?.overdue ?? []), [state]);
  const titleOf = useMemo(
    () => new Map(board.nodes.map((node) => [node.id, node.title])),
    [board.nodes]
  );

  const cycleStatus = useCallback(
    (id: string, next: Status) => {
      // Optimistic: flip it locally, then let the daemon confirm via the socket.
      const nodes = boardRef.current.nodes.map((node) =>
        node.id === id && node.kind === "task" ? { ...node, status: next } : node
      );
      setBoard({ ...boardRef.current, nodes });
      api
        .setStatus(id, next)
        .then(() => api.getState())
        .then(setState)
        .catch(() => undefined);
    },
    []
  );

  const flowNodes: Node[] = useMemo(
    () =>
      board.nodes.map((node) => ({
        id: node.id,
        type: node.kind,
        position: node.position,
        selected: node.id === selectedId,
        data:
          node.kind === "task"
            ? { task: node, overdue: overdue.has(node.id), onCycleStatus: cycleStatus }
            : {
                reward: node,
                unlocked: rewardStates.get(node.id)?.unlocked ?? false,
                blockingTitles: (rewardStates.get(node.id)?.blocking ?? []).map(
                  (id) => titleOf.get(id) ?? id
                ),
              },
      })),
    [board.nodes, overdue, rewardStates, titleOf, selectedId, cycleStatus]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      board.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated:
          board.nodes.find((node) => node.id === edge.source)?.kind === "task" &&
          (board.nodes.find((node) => node.id === edge.source) as { status?: Status })
            ?.status === "doing",
      })),
    [board.edges, board.nodes]
  );

  // --- canvas events ----------------------------------------------------

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Only positions and removals belong in our state. React Flow also emits
      // "dimensions" and "select" changes on every render — feeding those back into
      // setBoard would rebuild `flowNodes`, which emits them again, forever.
      const moves = new Map(
        changes.flatMap((change) =>
          change.type === "position" && change.position
            ? ([[change.id, change.position]] as [string, { x: number; y: number }][])
            : []
        )
      );
      const removed = new Set(
        changes.filter((change) => change.type === "remove").map((change) => change.id)
      );
      if (!moves.size && !removed.size) return;

      const current = boardRef.current;
      const next: Board = {
        nodes: current.nodes
          .filter((node) => !removed.has(node.id))
          .map((node) => (moves.has(node.id) ? { ...node, position: moves.get(node.id)! } : node)),
        edges: current.edges.filter(
          (edge) => !removed.has(edge.source) && !removed.has(edge.target)
        ),
      };

      // Persist on drop and on delete; during a drag just track it locally.
      const dropped = changes.some((change) => change.type === "position" && !change.dragging);
      if (removed.size || dropped) update(next);
      else setBoard(next);

      if (removed.size && selectedId && removed.has(selectedId)) setSelectedId(null);
    },
    [update, selectedId]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const removed = new Set(
        changes.filter((change) => change.type === "remove").map((change) => change.id)
      );
      if (!removed.size) return;
      update({
        ...boardRef.current,
        edges: boardRef.current.edges.filter((edge) => !removed.has(edge.id)),
      });
    },
    [update]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const edges = addEdge({ ...connection, id: newId() }, flowEdges);
      update({
        ...boardRef.current,
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
        })),
      });
    },
    [flowEdges, update]
  );

  const addNode = (kind: "task" | "reward") => {
    const id = newId();
    // Drop it somewhere visible and out of the way of what's already there.
    const position = { x: 120 + board.nodes.length * 40, y: 120 + (board.nodes.length % 6) * 90 };
    const node = kind === "task" ? emptyTask(id, position) : emptyReward(id, position);
    update({ ...boardRef.current, nodes: [...boardRef.current.nodes, node] });
    setSelectedId(id);
  };

  const editNode = (updated: BoardNode) =>
    update({
      ...boardRef.current,
      nodes: boardRef.current.nodes.map((node) => (node.id === updated.id ? updated : node)),
    });

  const deleteNode = (id: string) => {
    update({
      nodes: boardRef.current.nodes.filter((node) => node.id !== id),
      edges: boardRef.current.edges.filter(
        (edge) => edge.source !== id && edge.target !== id
      ),
    });
    setSelectedId(null);
  };

  const selected = board.nodes.find((node) => node.id === selectedId) ?? null;
  const mode = state?.mode ?? "off";

  return (
    <div className="app">
      <header className="header">
        <h1>Autolockin</h1>
        <button onClick={() => addNode("task")}>+ Task</button>
        <button onClick={() => addNode("reward")}>+ Reward</button>
        <div className="spacer" />
        <span className="save-state">
          {saveState === "saving" ? "saving…" : saveState === "error" ? "save failed" : saveState === "saved" ? "saved" : ""}
        </span>
        <span className={`mode-badge mode-${mode}`} title="Enforcement mode">
          {state?.panicked ? "PANIC" : mode.toUpperCase()}
        </span>
      </header>

      {state?.errors?.length ? <div className="banner">⚠ {state.errors.join("; ")}</div> : null}

      <div className="canvas-wrap">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_event, node) => setSelectedId(node.id)}
          onPaneClick={() => setSelectedId(null)}
          fitView
          proOptions={{ hideAttribution: false }}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#3a3a52" />
          <Controls />
          <MiniMap
            pannable
            zoomable
            bgColor="#22222e"
            maskColor="#1a1a24cc"
            nodeColor={(node) => (node.type === "reward" ? "#f5a623" : "#4a9eff")}
            nodeStrokeColor="#45455e"
          />
        </ReactFlow>

        {selected && (
          <NodeEditor
            node={selected}
            onChange={editNode}
            onDelete={deleteNode}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>

      {loaded && board.nodes.length === 0 && (
        <div className="banner" style={{ background: "#4a9eff20", borderColor: "#4a9eff", color: "#bcd9ff" }}>
          Empty board — add a Task, add a Reward, then drag from the task's right handle to the
          reward's left handle.
        </div>
      )}
    </div>
  );
}
