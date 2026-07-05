"use client";

import { useState } from "react";
import { sendApprovalNudge, holdApprovalNudge } from "../lib/api";

type DraftedAction = {
  approval_id: string;
  department: string;
  approver_id: string;
  artifact_draft: string;
  nudge_draft: string;
  prediction: { root_cause: string; delay_probability: number };
};

export default function ReviewQueue({ actions }: { actions: DraftedAction[] }) {
  const [statusMap, setStatusMap] = useState<Record<string, string>>({});

  const handleSend = async (action: DraftedAction) => {
    await sendApprovalNudge(action.approval_id, action.nudge_draft);
    setStatusMap((prev) => ({ ...prev, [action.approval_id]: "sent" }));
  };

  const handleHold = async (action: DraftedAction) => {
    await holdApprovalNudge(action.approval_id);
    setStatusMap((prev) => ({ ...prev, [action.approval_id]: "held" }));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {actions.map((action) => (
        <div
          key={action.approval_id}
          style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}
        >
          <div style={{ fontWeight: 600 }}>
            {action.department} — {action.approver_id}
          </div>
          <p style={{ fontSize: 13, color: "#6b7280" }}>
            {action.prediction.root_cause} (delay risk:{" "}
            {Math.round(action.prediction.delay_probability * 100)}%)
          </p>

          <div style={{ background: "#f9fafb", padding: 12, borderRadius: 8, marginTop: 8 }}>
            <div style={{ fontSize: 12, color: "#6b7280" }}>Drafted artifact</div>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{action.artifact_draft}</pre>
          </div>

          <div style={{ background: "#f9fafb", padding: 12, borderRadius: 8, marginTop: 8 }}>
            <div style={{ fontSize: 12, color: "#6b7280" }}>Drafted nudge message</div>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{action.nudge_draft}</pre>
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button onClick={() => handleSend(action)}>Send</button>
            <button onClick={() => handleHold(action)}>Hold</button>
          </div>

          {statusMap[action.approval_id] && (
            <div style={{ fontSize: 12, marginTop: 8, color: "#16a34a" }}>
              Status: {statusMap[action.approval_id]}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
