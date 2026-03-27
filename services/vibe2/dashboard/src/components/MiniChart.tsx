import { useEffect, useState } from "react";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
// ReferenceLine removed — unused
import { authFetch } from "../api.ts";

interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceResponse {
  prices: PricePoint[];
}

interface ChartRow {
  date: string;
  close: number;
  ma20: number | null;
  volume: number;
}

function computeMA(prices: PricePoint[], window: number): (number | null)[] {
  return prices.map((_, i) => {
    if (i < window - 1) return null;
    const slice = prices.slice(i - window + 1, i + 1);
    const sum = slice.reduce((acc, p) => acc + p.close, 0);
    return Math.round((sum / window) * 100) / 100;
  });
}

export default function MiniChart() {
  const [data, setData] = useState<ChartRow[]>([]);
  const [raw, setRaw] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authFetch<PriceResponse>("/data/price?symbol=SOXL&days=60")
      .then((res) => {
        const prices = res.prices;
        setRaw(prices);
        const ma20 = computeMA(prices, 20);
        setData(
          prices.map((p, i) => ({
            date: p.date,
            close: p.close,
            ma20: ma20[i],
            volume: p.volume,
          }))
        );
      })
      .catch(() => { setData([]); setRaw([]); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <div className="h-4 w-40 bg-gray-700 rounded animate-skeleton mb-3" />
        <div className="h-48 bg-gray-700 rounded animate-skeleton" />
      </div>
    );
  }

  if (data.length === 0) {
    return <div className="text-gray-500 text-center py-8">가격 데이터 없음</div>;
  }

  const prices = data.map((d) => d.close);
  const latest = prices[prices.length - 1];
  const prev = prices.length >= 2 ? prices[prices.length - 2] : latest;
  const changePct = prev !== 0 ? ((latest - prev) / prev) * 100 : 0;
  const high52 = Math.max(...raw.map((p) => p.high));
  const low52 = Math.min(...raw.map((p) => p.low));
  const positionPct = high52 !== low52 ? ((latest - low52) / (high52 - low52)) * 100 : 50;

  const priceMin = Math.floor(Math.min(...prices) * 0.97);
  const priceMax = Math.ceil(Math.max(...prices) * 1.03);
  const volMax = Math.max(...data.map((d) => d.volume));

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      {/* Header stats */}
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <span className="text-sm text-gray-400">SOXL </span>
          <span className="text-lg font-bold text-white">${latest.toFixed(2)}</span>
          <span className={`text-sm ml-2 ${changePct >= 0 ? "text-green-400" : "text-red-400"}`}>
            {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
          </span>
        </div>
        <div className="text-xs text-gray-500">
          H ${high52.toFixed(0)} / L ${low52.toFixed(0)}
          <span className="ml-1 text-gray-400">({positionPct.toFixed(0)}%)</span>
        </div>
      </div>

      {/* Price + MA chart */}
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fill: "#6b7280", fontSize: 9 }}
            tickFormatter={(v: string) => v.slice(5)}
            interval={Math.floor(data.length / 5)}
          />
          <YAxis
            yAxisId="price"
            domain={[priceMin, priceMax]}
            tick={{ fill: "#6b7280", fontSize: 9 }}
            width={40}
          />
          <YAxis yAxisId="vol" orientation="right" domain={[0, volMax * 4]} hide />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              border: "1px solid #374151",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelStyle={{ color: "#9ca3af" }}
            formatter={(value: number, name: string) => {
              if (name === "volume") return [value.toLocaleString(), "거래량"];
              return [`$${value.toFixed(2)}`, name === "close" ? "종가" : "MA20"];
            }}
          />
          <Bar
            yAxisId="vol"
            dataKey="volume"
            fill="#374151"
            opacity={0.5}
            barSize={3}
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke="#60a5fa"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="ma20"
            stroke="#f59e0b"
            strokeWidth={1}
            strokeDasharray="4 2"
            dot={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex gap-4 mt-2 text-xs text-gray-500 justify-center">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-blue-400" /> 종가
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-amber-400 border-dashed" style={{ borderTopWidth: 1 }} /> MA20
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 bg-gray-600 opacity-50" /> 거래량
        </span>
      </div>
    </div>
  );
}
