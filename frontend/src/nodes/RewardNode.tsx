import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RewardNode as Reward } from "../types";

export interface RewardNodeData extends Record<string, unknown> {
  reward: Reward;
  unlocked: boolean;
  blockingTitles: string[];
}

export function RewardNodeView({ data, selected }: NodeProps) {
  const { reward, unlocked, blockingTitles } = data as unknown as RewardNodeData;
  const targets = [...reward.folders, ...reward.processes];

  return (
    <div
      className={["node", "reward", unlocked ? "unlocked" : "locked", selected ? "selected" : ""]
        .filter(Boolean)
        .join(" ")}
    >
      <Handle type="target" position={Position.Left} />
      <div className="accent" />
      <div className="body">
        <div className="reward-head">
          <span>{unlocked ? "🔓" : "🔒"}</span>
          <span>{reward.title}</span>
        </div>

        {targets.length > 0 && (
          <div className="reward-targets">
            {reward.folders.map((folder) => (
              <div key={folder}>📁 {folder}</div>
            ))}
            {reward.processes.map((process) => (
              <div key={process}>▶ {process}</div>
            ))}
          </div>
        )}

        <div className="reward-blockers">
          {unlocked ? (
            targets.length === 0 ? (
              "unlocked — but nothing is attached to it yet"
            ) : (
              "unlocked"
            )
          ) : blockingTitles.length > 0 ? (
            <>
              waiting on <b>{blockingTitles.join(", ")}</b>
            </>
          ) : (
            "locked"
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
