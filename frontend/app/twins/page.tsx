"use client";

import { useEffect, useState } from "react";
import { fetchDashboardSummary } from "../../lib/api";
import ApproverCard from "../../components/ApproverCard";

export default function TwinsPage() {
  const [twins, setTwins] = useState<any[]>([]);

  useEffect(() => {
    fetchDashboardSummary().then((data) => setTwins(data.approver_profiles || []));
  }, []);

  return (
    <main style={{ padding: 32 }}>
      <h1>Approver Behavioral Twins</h1>
      <p style={{ color: "#6b7280" }}>
        Live profiles, updated by the Learning Agent after every closed deal.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 16,
          marginTop: 16,
        }}
      >
        {twins.map((twin) => (
          <ApproverCard key={twin.approver_id} twin={twin} />
        ))}
      </div>
    </main>
  );
}
