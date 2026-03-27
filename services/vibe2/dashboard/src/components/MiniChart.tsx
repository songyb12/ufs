import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { authFetch } from "../api.ts";

interface PricePoint {
  date: string;
  close: number;
}

interface PriceResponse {
  prices: PricePoint[];
}

export default function MiniChart() {
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authFetch<PriceResponse>("/data/price?symbol=SOXL&days=30")
      .then((res) => setData(res.prices))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-gray-500 text-center py-8">차트 로딩중...</div>;
  }

  if (data.length === 0) {
    return <div className="text-gray-500 text-center py-8">가격 데이터 없음</div>;
  }

  const prices = data.map((d) => d.close);
  const min = Math.floor(Math.min(...prices) * 0.98);
  const max = Math.ceil(Math.max(...prices) * 1.02);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-sm text-gray-400 mb-2">SOXL 30일 종가</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis
            dataKey="date"
            tick={{ fill: "#9ca3af", fontSize: 10 }}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis
            domain={[min, max]}
            tick={{ fill: "#9ca3af", fontSize: 10 }}
            width={45}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
            labelStyle={{ color: "#9ca3af" }}
            itemStyle={{ color: "#60a5fa" }}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#60a5fa"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
