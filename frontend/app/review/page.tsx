"use client";

import { useState } from "react";
import { triggerDemoDeal } from "../../lib/api";
import ReviewQueue from "../../components/ReviewQueue";

const DEMO_PAYLOAD = {
  customer_name: "Northwind Logistics",
  value: 180000,
  discount_percent: 18,
  product_type: "custom",
  customer_segment: "enterprise",
  stage: "verbal_agreement",
};

export default function ReviewPage() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runDemo = async () => {
    setLoading(true);
    const res = await triggerDemoDeal(DEMO_PAYLOAD);
    setResult(res);
    setLoading(false);
  };

  return (
    <main style={{ padding: 32 }}>
      <h1>Human Review Checkpoint</h1>
      <p style={{ color: "#6b7280" }}>
        Nothing Threshold drafts reaches a real approver until you click Send.
      </p>

      <button onClick={runDemo} disabled={loading} style={{ marginTop: 16 }}>
        {loading ? "Running Threshold pipeline..." : "Simulate new deal (webhook)"}
      </button>

      {result && (
        <div style={{ marginTop: 24 }}>
          <p>
            Deal momentum score: <strong>{result.momentum_score}</strong>
          </p>
          <ReviewQueue actions={result.drafted_actions} />
        </div>
      )}
    </main>
  );
}
