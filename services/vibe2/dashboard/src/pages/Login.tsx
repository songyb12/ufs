import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { setToken } from "../api.ts";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shaking, setShaking] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg = (body as Record<string, string>).detail || "로그인 실패";
        setError(msg);
        setShaking(true);
        setTimeout(() => setShaking(false), 600);
        return;
      }

      const data = (await res.json()) as { token: string };
      setToken(data.token);
      navigate("/", { replace: true });
    } catch {
      setError("서버 연결 실패");
      setShaking(true);
      setTimeout(() => setShaking(false), 600);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className={`bg-gray-800 rounded-xl p-8 w-full max-w-sm shadow-2xl ${shaking ? "animate-shake" : ""}`}
      >
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-600/20 mb-3">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="8" r="5" fill="#22c55e" />
              <circle cx="16" cy="16" r="5" fill="#eab308" opacity="0.3" />
              <circle cx="16" cy="24" r="5" fill="#ef4444" opacity="0.3" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">VIBE 2.0</h1>
          <p className="text-gray-400 text-sm mt-1">SOXL Investment Intelligence</p>
        </div>

        {error && (
          <div className="bg-red-900/50 border border-red-700 text-red-300 rounded-lg px-4 py-2 mb-4 text-sm">
            {error}
          </div>
        )}

        <label className="block text-gray-300 text-sm mb-1">ID</label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full bg-gray-700 text-white rounded-lg px-4 py-2 mb-4 outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />

        <label className="block text-gray-300 text-sm mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-gray-700 text-white rounded-lg px-4 py-2 mb-6 outline-none focus:ring-2 focus:ring-blue-500"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white font-semibold rounded-lg py-2.5 transition-colors flex items-center justify-center gap-2"
        >
          {loading && (
            <svg className="animate-spin-slow w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" strokeOpacity="0.3" />
              <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
            </svg>
          )}
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>
    </div>
  );
}
