interface Props {
  signal: "GREEN" | "YELLOW" | "RED";
  score: number;
}

const COLORS = {
  RED: "#ef4444",
  YELLOW: "#eab308",
  GREEN: "#22c55e",
} as const;

const DIM = "#374151";

export default function TrafficLight({ signal, score }: Props) {
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="60" height="160" viewBox="0 0 60 160">
        <rect x="5" y="5" width="50" height="150" rx="12" fill="#1f2937" stroke="#4b5563" strokeWidth="2" />
        {(["RED", "YELLOW", "GREEN"] as const).map((color, i) => (
          <circle
            key={color}
            cx="30"
            cy={35 + i * 45}
            r="16"
            fill={signal === color ? COLORS[color] : DIM}
            className={signal === color ? "animate-pulse-glow" : ""}
            style={{ transition: "fill 0.5s ease" }}
          />
        ))}
      </svg>
      <span className="text-2xl font-bold" style={{ color: COLORS[signal] }}>
        {score >= 0 ? "+" : ""}{score.toFixed(3)}
      </span>
      <span className="text-sm text-gray-400">{signal}</span>
    </div>
  );
}
