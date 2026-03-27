import { useEffect, useState } from "react";
import { authFetch } from "../api.ts";

interface HistoryEntry {
  date: string;
  signal: {
    signal: "GREEN" | "YELLOW" | "RED";
    score: number;
    summary: string;
  };
  commentary: string | null;
}

const COLORS: Record<string, string> = {
  GREEN: "#22c55e",
  YELLOW: "#eab308",
  RED: "#ef4444",
};

export default function SignalHistory() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ entry: HistoryEntry; x: number; y: number } | null>(null);

  useEffect(() => {
    authFetch<HistoryEntry[]>("/briefing/history?days=14")
      .then((data) => setHistory(data.reverse()))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <div className="h-4 w-32 bg-gray-700 rounded animate-skeleton mb-3" />
        <div className="h-12 bg-gray-700 rounded animate-skeleton" />
      </div>
    );
  }

  if (history.length === 0) return null;

  const dotSize = 14;

  return (
    <div className="bg-gray-800 rounded-lg p-4 relative">
      <h3 className="text-sm text-gray-400 mb-3">최근 신호등 이력</h3>
      <div className="flex items-center justify-center gap-1.5 overflow-x-auto py-1">
        {history.map((entry) => (
          <div
            key={entry.date}
            className="flex flex-col items-center cursor-pointer"
            onMouseEnter={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              setTooltip({ entry, x: rect.left + rect.width / 2, y: rect.top });
            }}
            onMouseLeave={() => setTooltip(null)}
          >
            <svg width={dotSize} height={dotSize}>
              <circle
                cx={dotSize / 2}
                cy={dotSize / 2}
                r={dotSize / 2 - 1}
                fill={COLORS[entry.signal.signal] || "#374151"}
                opacity={0.9}
              />
            </svg>
            <span className="text-[9px] text-gray-500 mt-0.5">
              {entry.date.slice(5)}
            </span>
          </div>
        ))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="absolute z-10 bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-xs shadow-xl pointer-events-none"
          style={{
            bottom: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            marginBottom: "4px",
            minWidth: "160px",
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: COLORS[tooltip.entry.signal.signal] }}
            />
            <span className="text-gray-200 font-semibold">{tooltip.entry.date}</span>
          </div>
          <div className="text-gray-400">
            {tooltip.entry.signal.signal} ({tooltip.entry.signal.score >= 0 ? "+" : ""}{tooltip.entry.signal.score.toFixed(3)})
          </div>
          {tooltip.entry.commentary && (
            <div className="text-gray-500 mt-1 line-clamp-2">{tooltip.entry.commentary}</div>
          )}
        </div>
      )}
    </div>
  );
}
