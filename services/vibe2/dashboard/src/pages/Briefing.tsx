import { useEffect, useState, useCallback } from "react";
// useRef removed — unused
import { useNavigate } from "react-router-dom";
import { authFetch, getToken } from "../api.ts";
import TrafficLight from "../components/TrafficLight.tsx";
import ScoreBar from "../components/ScoreBar.tsx";
import DetailPanel from "../components/DetailPanel.tsx";
import MiniChart from "../components/MiniChart.tsx";
import SignalHistory from "../components/SignalHistory.tsx";

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

function getMarketStatus(): { label: string; color: string } {
  const now = new Date();
  const etStr = now.toLocaleString("en-US", { timeZone: "America/New_York" });
  const et = new Date(etStr);
  const day = et.getDay();
  const h = et.getHours();
  const m = et.getMinutes();
  const hm = h * 60 + m;

  if (day === 0 || day === 6) return { label: "Closed", color: "bg-gray-600" };
  if (hm >= 570 && hm <= 960) return { label: "Open", color: "bg-green-500" };
  if (hm >= 240 && hm < 570) return { label: "Pre-Market", color: "bg-yellow-500" };
  if (hm > 960 && hm < 1200) return { label: "After-Hours", color: "bg-yellow-500" };
  return { label: "Closed", color: "bg-gray-600" };
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`bg-gray-700 rounded animate-skeleton ${className}`} />;
}

export default function Briefing() {
  const navigate = useNavigate();
  const [signal, setSignal] = useState<SignalResult | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [prevScore, setPrevScore] = useState<number | null>(null);
  const [clock, setClock] = useState(new Date());
  const [marketStatus, setMarketStatus] = useState(getMarketStatus());

  // Auth guard
  useEffect(() => {
    if (!getToken()) navigate("/login", { replace: true });
  }, [navigate]);

  // Real-time clock
  useEffect(() => {
    const timer = setInterval(() => {
      setClock(new Date());
      setMarketStatus(getMarketStatus());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchSignal = useCallback(async () => {
    try {
      const data = await authFetch<SignalResult>("/signal/current");
      setSignal((prev) => {
        if (prev) setPrevScore(prev.score);
        return data;
      });
      setUpdatedAt(new Date().toISOString());
      setError("");
    } catch (e) {
      if (e instanceof Error && e.message !== "Unauthorized") {
        setError("서버 연결 실패. 재시도하세요.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchBriefing = useCallback(async () => {
    try {
      const data = await authFetch<BriefingData>("/briefing/latest");
      setBriefing(data);
    } catch {
      // signal is primary
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
    if (refreshing) return;
    setRefreshing(true);
    try {
      const data = await authFetch<BriefingData>("/briefing/refresh", { method: "POST" });
      setBriefing(data);
      if (data.signal) {
        if (signal) setPrevScore(signal.score);
        setSignal(data.signal);
      }
      setUpdatedAt(new Date().toISOString());
      setError("");
    } catch {
      setError("새로고침 실패. 재시도하세요.");
    } finally {
      setRefreshing(false);
    }
  }

  function handleRetry() {
    setError("");
    setLoading(true);
    fetchSignal();
    fetchBriefing();
  }

  const kstTime = clock.toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const scoreDelta = signal && prevScore !== null ? signal.score - prevScore : null;

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <header className="bg-gray-800/80 backdrop-blur-sm border-b border-gray-700 sticky top-0 z-20">
        <div className="max-w-2xl mx-auto px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="5" r="3" fill="#22c55e" />
              <circle cx="10" cy="10" r="3" fill="#eab308" opacity="0.3" />
              <circle cx="10" cy="15" r="3" fill="#ef4444" opacity="0.3" />
            </svg>
            <span className="font-bold text-sm">VIBE 2.0</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 font-mono">{kstTime}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full text-white font-medium ${marketStatus.color}`}>
              {marketStatus.label}
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-6 space-y-5">
        {/* Error */}
        {error && (
          <div className="bg-red-900/40 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={handleRetry} className="text-red-200 underline hover:text-white text-xs ml-3">
              재시도
            </button>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !signal && (
          <div className="space-y-5">
            <div className="flex justify-center">
              <div className="flex flex-col items-center gap-3">
                <SkeletonBlock className="w-[60px] h-[160px] rounded-xl" />
                <SkeletonBlock className="w-24 h-8" />
              </div>
            </div>
            <SkeletonBlock className="w-full h-5" />
            <SkeletonBlock className="w-3/4 h-6 mx-auto" />
            <SkeletonBlock className="w-full h-12" />
            <SkeletonBlock className="w-full h-12" />
            <SkeletonBlock className="w-full h-12" />
            <SkeletonBlock className="w-full h-48" />
            <div className="text-center text-gray-500 text-sm">분석 중...</div>
          </div>
        )}

        {signal && (
          <>
            {/* Update time */}
            {updatedAt && (
              <div className="text-center text-xs text-gray-500">
                {new Date(updatedAt).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} KST
                <span className="ml-1">({formatRelativeTime(updatedAt)})</span>
              </div>
            )}

            {/* Traffic Light + Score */}
            <div className="flex justify-center">
              <div className="flex flex-col items-center gap-1">
                <TrafficLight signal={signal.signal} score={signal.score} />
                {scoreDelta !== null && scoreDelta !== 0 && (
                  <span className={`text-xs ${scoreDelta > 0 ? "text-green-400" : "text-red-400"}`}>
                    ({scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(3)})
                  </span>
                )}
              </div>
            </div>

            {/* Commentary */}
            {briefing?.commentary && (
              <p className="text-center text-gray-300 text-sm leading-relaxed">{briefing.commentary}</p>
            )}

            {/* Action */}
            <p className="text-center font-bold text-lg" style={{
              color: signal.signal === "GREEN" ? "#22c55e" : signal.signal === "RED" ? "#ef4444" : "#eab308"
            }}>
              {signal.action}
            </p>

            {/* Score Bars */}
            <div className="space-y-1">
              {signal.details.technical && <ScoreBar label="Technical" score={getSubScore(signal, "technical")} />}
              {signal.details.leverage && <ScoreBar label="Leverage" score={getSubScore(signal, "leverage")} />}
              {signal.details.macro && <ScoreBar label="Macro" score={getSubScore(signal, "macro")} />}
            </div>

            {/* Detail Panels */}
            <div className="space-y-2">
              <DetailPanel title="기술적 분석" data={signal.details.technical ?? {}} defaultOpen />
              <DetailPanel title="레버리지 분석" data={signal.details.leverage ?? {}} />
              <DetailPanel title="매크로 환경" data={signal.details.macro ?? {}} />
            </div>

            {/* Risks */}
            {signal.risks.length > 0 && (
              <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
                <h3 className="text-red-400 font-semibold text-sm mb-2">리스크</h3>
                <ul className="list-disc list-inside text-sm text-red-300 space-y-1">
                  {signal.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}

            {/* Mini Chart */}
            <MiniChart />

            {/* Signal History */}
            <SignalHistory />

            {/* Refresh Button */}
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="w-full bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800 disabled:text-gray-600 text-gray-300 rounded-lg py-3 transition-colors text-sm flex items-center justify-center gap-2"
            >
              {refreshing && (
                <svg className="animate-spin-slow w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.3" />
                  <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                </svg>
              )}
              {refreshing ? "파이프라인 실행중..." : "수동 새로고침"}
            </button>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-3">
        <p className="text-center text-[10px] text-gray-600">
          데이터 출처: Yahoo Finance | 투자 판단은 본인 책임
        </p>
      </footer>
    </div>
  );
}

function getSubScore(signal: SignalResult, engine: string): number {
  const map: Record<string, RegExp> = {
    technical: /[기技]술=([-+]?\d+\.?\d*)/,
    leverage: /레버리지=([-+]?\d+\.?\d*)/,
    macro: /매크로=([-+]?\d+\.?\d*)/,
  };
  const match = signal.summary.match(map[engine] ?? /$/);
  return match ? parseFloat(match[1]) : 0;
}
