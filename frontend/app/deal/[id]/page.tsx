"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchDeal } from "../../../lib/api";
import MomentumGauge from "../../../components/MomentumGauge";
import ActivityFeed from "../../../components/ActivityFeed";

export default function DealPage() {
  const params = useParams();
  const dealId = params?.id as string;
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (dealId) fetchDeal(dealId).then(setData);
  }, [dealId]);

  if (!data) return <p>Loading deal...</p>;

  return (
    <main style={{ padding: 32 }}>
      <h1>{data.deal.customer_name}</h1>
      <p style={{ color: "#6b7280" }}>
        ${data.deal.value} · {data.deal.stage}
      </p>

      <div style={{ maxWidth: 240, margin: "16px 0" }}>
        <MomentumGauge score={data.deal.momentum_score} />
      </div>

      <h2>Approvals</h2>
      <ActivityFeed actions={data.approvals} />
    </main>
  );
}
