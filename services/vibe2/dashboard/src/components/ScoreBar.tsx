interface Props {
  score: number;
  label: string;
}

export default function ScoreBar({ score, label }: Props) {
  // Map score from [-1, 1] to [0, 100] percent
  const pct = Math.max(0, Math.min(100, ((score + 1) / 2) * 100));

  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-300">{label}</span>
        <span className="text-gray-400">{score >= 0 ? "+" : ""}{score.toFixed(3)}</span>
      </div>
      <div className="relative h-3 rounded-full overflow-hidden bg-gray-700">
        <div
          className="absolute inset-0"
          style={{
            background: "linear-gradient(to right, #ef4444, #eab308 50%, #22c55e)",
          }}
        />
        {/* Marker */}
        <div
          className="absolute top-0 h-full w-1 bg-white rounded-full shadow-lg"
          style={{
            left: `${pct}%`,
            transform: "translateX(-50%)",
            transition: "left 0.5s ease",
          }}
        />
      </div>
    </div>
  );
}
