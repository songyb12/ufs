import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { authFetch, getToken } from "../api.ts";
import TrafficLight from "../components/TrafficLight.tsx";
import ScoreBar from "../components/ScoreBar.tsx";
import DetailPanel from "../components/DetailPanel.tsx";
import MiniChart from "../components/MiniChart.tsx";

interface SignalResult {
  signal: "GREEN" | "YELLOW" | "RED";
  score: number;
  summary: string;
  action: string;
  risks: string[];
  details: {
    technical?: Record<string, unknown>;
    leverage?: Record<string, unknown>;
    macro?: Record<string, unknown>;
  };
}

interface BriefingData {
  date: string;
  signal: SignalResult;
  commentary: string | null;
  generated_at: string | null;
}

const POLL_INTERVAL = 30_000;

export default function Briefing() {
  const navigate = useNavigate();
  const [signal, setSignal] = useState<SignalResult | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  // Auth guard
  useEffect(() => {
    if (!getToken()) navigate("/login", { replace: true });
  }, [navigate]);

  const fetchSignal = useCallback(async () => {
    try {
      const data = await authFetch<SignalResult>("/signal/current");
      setSignal(data);
      setUpdatedAt(new Date().toLocaleTimeString("ko-KR"));
      setError("");
    } catch (e) {
      if (e instanceof Error && e.message !== "Unauthorized") {
        setError("시그널 조회 실패");
      }
    }
  }, []);

  const fetchBriefing = useCallback(async () => {
    try {
      const data = await authFetch<BriefingData>("/briefing/latest");
      setBriefing(data);
    } catch {
      // ignore — signal is primary
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (getToken()) {
      fetchSignal();
      fetchBriefing();
    }
  }, [fetchSignal, fetchBriefing]);

  // Polling
  useEffect(() => {
    const interval = setInterval(fetchSignal, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchSignal]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const data = await authFetch<BriefingData>("/briefing/refresh", {
        method: "POST",
      });
      setBriefing(data);
      if (data.signal) setSignal(data.signal);
      setUpdatedAt(new Date().toLocaleTimeString("ko-KR"));
    } catch {
      setError("새로고침 실패");
    } finally {
      setRefreshing(false);
    }
  }

  if (!signal) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center text-gray-400">
        시그널 로딩중...
      </div>
    );
  }

  const tech = signal.details.technical ?? {};
  const lev = signal.details.leverage ?? {};
  const mac = signal.details.macro ?? {};

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-md mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">VIBE 2.0</h1>
          <span className="text-xs text-gray-500">{updatedAt && `${updatedAt} 갱신`}</span>
        </div>

        {error && (
          <div className="bg-red-900/40 border border-red-800 text-red-300 rounded-lg px-3 py-2 text-sm">
            {error}
          </div>
        )}

        {/* Traffic Light + Score */}
        <div className="flex justify-center">
          <TrafficLight signal={signal.signal} score={signal.score} />
        </div>

        {/* Summary */}
        {briefing?.commentary && (
          <p className="text-center text-gray-300">{briefing.commentary}</p>
        )}

        {/* Action */}
        <p className="text-center font-bold text-lg" style={{
          color: signal.signal === "GREEN" ? "#22c55e" : signal.signal === "RED" ? "#ef4444" : "#eab308"
        }}>
          {signal.action}
        </p>

        {/* Score Bars */}
        <div className="space-y-1">
          <ScoreBar label="기술적 분석" score={Number((tech as Record<string, number>).rsi_value !== undefined ? signal.score : 0)} />
          {signal.details.technical && <ScoreBar label="Technical" score={getSubScore(signal, "technical")} />}
          {signal.details.leverage && <ScoreBar label="Leverage" score={getSubScore(signal, "leverage")} />}
          {signal.details.macro && <ScoreBar label="Macro" score={getSubScore(signal, "macro")} />}
        </div>

        {/* Detail Panels */}
        <div className="space-y-2">
          <DetailPanel title="Technical Details" data={tech} defaultOpen />
          <DetailPanel title="Leverage Details" data={lev} />
          <DetailPanel title="Macro Details" data={mac} />
        </div>

        {/* Risks */}
        {signal.risks.length > 0 && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
            <h3 className="text-red-400 font-semibold text-sm mb-2">리스크</h3>
            <ul className="list-disc list-inside text-sm text-red-300 space-y-1">
              {signal.risks.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Mini Chart */}
        <MiniChart />

        {/* Refresh Button */}
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="w-full bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800 disabled:text-gray-600 text-gray-300 rounded-lg py-3 transition-colors text-sm"
        >
          {refreshing ? "파이프라인 실행중..." : "수동 새로고침"}
        </button>
      </div>
    </div>
  );
}

/** Extract a sub-engine score from the signal summary string */
function getSubScore(signal: SignalResult, engine: string): number {
  // Parse from summary: "종합 -0.301 (기술=-0.290 레버리지=-0.567 매크로=-0.050)"
  const map: Record<string, RegExp> = {
    technical: /[기技]술=([-+]?\d+\.?\d*)/,
    leverage: /레버리지=([-+]?\d+\.?\d*)/,
    macro: /매크로=([-+]?\d+\.?\d*)/,
  };
  const match = signal.summary.match(map[engine] ?? /$/);
  return match ? parseFloat(match[1]) : 0;
}
