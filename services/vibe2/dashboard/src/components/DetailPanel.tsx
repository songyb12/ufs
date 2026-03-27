import { useState } from "react";

interface Props {
  title: string;
  data: Record<string, unknown>;
  defaultOpen?: boolean;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "N/A";
  if (typeof v === "number") return v.toFixed(4);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function DetailPanel({ title, data, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex justify-between items-center px-4 py-3 hover:bg-gray-750 transition-colors"
      >
        <span className="font-semibold text-gray-200">{title}</span>
        <span className="text-gray-400 text-lg">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 border-t border-gray-700">
          <table className="w-full text-sm mt-2">
            <tbody>
              {Object.entries(data).map(([k, v]) => (
                <tr key={k} className="border-b border-gray-700/50 last:border-0">
                  <td className="py-1 text-gray-400 pr-4">{k}</td>
                  <td className="py-1 text-gray-200 text-right font-mono">
                    {formatValue(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
