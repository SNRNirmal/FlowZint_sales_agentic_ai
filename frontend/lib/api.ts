const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchDashboardSummary() {
  const res = await fetch(`${API_URL}/dashboard/summary`);
  return res.json();
}

export async function fetchDeal(dealId: string) {
  const res = await fetch(`${API_URL}/deals/${dealId}`);
  return res.json();
}

export async function sendApprovalNudge(approvalId: string, nudgeText: string) {
  const res = await fetch(
    `${API_URL}/approvals/${approvalId}/send?nudge_text=${encodeURIComponent(nudgeText)}`,
    { method: "POST" }
  );
  return res.json();
}

export async function holdApprovalNudge(approvalId: string) {
  const res = await fetch(`${API_URL}/approvals/${approvalId}/hold`, {
    method: "POST",
  });
  return res.json();
}

export async function triggerDemoDeal(payload: Record<string, unknown>) {
  const res = await fetch(`${API_URL}/webhooks/crm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}
