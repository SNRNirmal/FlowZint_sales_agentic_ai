type ActivityItem = {
  department: string;
  approver_id: string;
  review_status: string;
  prediction?: { root_cause?: string };
};

type Props = {
  actions: ActivityItem[];
};

export default function ActivityFeed({ actions }: Props) {
  if (!actions || actions.length === 0) {
    return <p style={{ color: "#6b7280" }}>No agent activity yet.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {actions.map((action, i) => (
        <div
          key={i}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 12,
          }}
        >
          <strong>{action.department}</strong> → {action.approver_id}
          <div style={{ fontSize: 13, color: "#6b7280" }}>
            {action.prediction?.root_cause}
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            Status: {action.review_status}
          </div>
        </div>
      ))}
    </div>
  );
}
