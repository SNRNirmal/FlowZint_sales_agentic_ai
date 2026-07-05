"use client";

import { useEffect, useState } from "react";
import { fetchDashboardSummary } from "../../lib/api";
import MomentumGauge from "../../components/MomentumGauge";

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    fetchDashboardSummary().then(setSummary);
  }, []);

  if (!summary) return <p>Loading dashboard...</p>;

  return (
    <main style={{ padding: 32 }}>
      <h1>Threshold Dashboard</h1>
      <p style={{ color: "#6b7280" }}>
        {summary.total_deals} deals tracked · {summary.stalled_deals} stalled
      </p>

      <div style={{ maxWidth: 240, marginTop: 16 }}>
        <MomentumGauge score={summary.avg_momentum_score} />
      </div>

      <h2 style={{ marginTop: 32 }}>Deals</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {summary.deals.map((deal: any) => (
          <a
            key={deal.id}
            href={`/deal/${deal.id}`}
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: 12,
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <strong>{deal.customer_name}</strong> — ${deal.value} — momentum{" "}
            {deal.momentum_score}
          </a>
        ))}
      </div>
    </main>
  );
}
