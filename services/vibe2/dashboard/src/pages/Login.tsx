import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { setToken } from "../api.ts";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
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
        setError((body as Record<string, string>).detail || "로그인 실패");
        return;
      }

      const data = (await res.json()) as { token: string };
      setToken(data.token);
      navigate("/", { replace: true });
    } catch {
      setError("서버 연결 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-gray-800 rounded-xl p-8 w-full max-w-sm shadow-2xl"
      >
        <h1 className="text-2xl font-bold text-white text-center mb-6">
          VIBE 2.0
        </h1>
        <p className="text-gray-400 text-center text-sm mb-6">
          SOXL Investment Intelligence
        </p>

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
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white font-semibold rounded-lg py-2 transition-colors"
        >
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>
    </div>
  );
}
