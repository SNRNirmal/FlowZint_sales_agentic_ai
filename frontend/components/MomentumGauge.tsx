type Props = {
  score: number;
};

function band(score: number) {
  if (score >= 80) return { label: "Green", color: "#16a34a" };
  if (score >= 50) return { label: "Yellow", color: "#ca8a04" };
  return { label: "Red", color: "#dc2626" };
}

export default function MomentumGauge({ score }: Props) {
  const { label, color } = band(score);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
      <div style={{ fontSize: 14, color: "#6b7280" }}>Deal Momentum Score</div>
      <div style={{ fontSize: 40, fontWeight: 700, color }}>{score}</div>
      <div style={{ fontSize: 12, color }}>{label}</div>
    </div>
  );
}
