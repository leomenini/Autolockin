import type { Board, BoardState, Status } from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const getBoard = () => fetch("/api/board").then(json<Board>);

export const putBoard = (board: Board) =>
  fetch("/api/board", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(board),
  }).then(json<{ saved: boolean; errors: string[] }>);

export const getState = () => fetch("/api/state").then(json<BoardState>);

export const setStatus = (id: string, status: Status) =>
  fetch(`/api/nodes/${encodeURIComponent(id)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  }).then(json<{ id: string; status: Status }>);

/** Keeps a socket to the daemon open, reconnecting if it drops. */
export function connect(onState: (state: BoardState) => void): () => void {
  let socket: WebSocket | null = null;
  let retry: number | undefined;
  let closed = false;

  const open = () => {
    if (closed) return;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${location.host}/ws`);
    socket.onmessage = (event) => onState(JSON.parse(event.data) as BoardState);
    socket.onclose = () => {
      if (!closed) retry = window.setTimeout(open, 2000);
    };
    socket.onerror = () => socket?.close();
  };

  open();
  return () => {
    closed = true;
    window.clearTimeout(retry);
    socket?.close();
  };
}
