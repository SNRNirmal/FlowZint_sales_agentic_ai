type Twin = {
  approver_id: string;
  department: string;
  avg_turnaround_days: number;
  fastest_responding_format: string;
  slowest_trigger: string;
  total_deals_reviewed: number;
};

export default function ApproverCard({ twin }: { twin: Twin }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
      <div style={{ fontWeight: 600 }}>{twin.approver_id}</div>
      <div style={{ fontSize: 13, color: "#6b7280" }}>{twin.department}</div>
      <div style={{ marginTop: 8, fontSize: 13 }}>
        Avg turnaround: <strong>{twin.avg_turnaround_days} days</strong>
      </div>
      <div style={{ fontSize: 13 }}>
        Responds fastest to: {twin.fastest_responding_format}
      </div>
      <div style={{ fontSize: 13 }}>Slows down on: {twin.slowest_trigger}</div>
      <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
        {twin.total_deals_reviewed} deals reviewed
      </div>
    </div>
  );
}
